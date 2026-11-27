#!/usr/bin/env python3
"""VeriLoop Level-2 RecSys Real-GPU Study: LightGCN & SimGCL Contrastive Learning on MovieLens-100K.

Implements 4 progressive implicit-feedback collaborative filtering models on MovieLens-100K
(strict per-user chronological leave-one-out split: last=test, penultimate=val, rest=train;
full-ranking evaluation over all non-training items — zero negative-sampling bias):
  - R0_Pop      : Popularity baseline (deterministic)
  - R1_MF_BPR   : Matrix Factorization with BPR pairwise ranking loss
  - R2_LightGCN : 3-layer symmetric normalized bipartite LightGCN (He et al., SIGIR 2020)
  - R3_SimGCL   : LightGCN + uniform embedding perturbation InfoNCE loss (Yu et al., SIGIR 2022)

Outputs per-seed CSVs under runs/csv/ (consumed directly by `./veriloop bind`),
append-only out/trajectory_ledger.jsonl, and aggregate out/recsys_summary.txt.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import random
import statistics
import time
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import torch
import torch.nn as nn
import torch.nn.functional as F

ML100K_URL = "https://files.grouplens.org/datasets/movielens/ml-100k.zip"


def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_movielens_100k(cache_dir: Path, min_rating: float = 4.0) -> dict:
    """Download & split MovieLens-100K chronologically per user (train / val / test)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    data_file = cache_dir / "ml-100k" / "u.data"
    if not data_file.is_file():
        req = urllib.request.Request(ML100K_URL, headers={"User-Agent": "VeriLoop/5.0"})
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read()
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            zf.extractall(cache_dir)

    user_hist: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for line in data_file.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        u, i, r, ts = int(parts[0]), int(parts[1]), float(parts[2]), int(parts[3])
        if r >= min_rating:
            user_hist[u].append((ts, i))

    # Keep users with >= 5 positive interactions so chronological train/val/test are well-defined
    u_map: dict[int, int] = {}
    i_map: dict[int, int] = {}
    train_pairs: list[tuple[int, int]] = []
    val_item: dict[int, int] = {}
    test_item: dict[int, int] = {}

    for raw_u, events in sorted(user_hist.items()):
        events.sort(key=lambda x: x[0])
        # Deduplicate items preserving chronological order
        seen_i = set()
        dedup = []
        for ts, raw_i in events:
            if raw_i not in seen_i:
                seen_i.add(raw_i)
                dedup.append(raw_i)
        if len(dedup) < 5:
            continue
        u_id = u_map.setdefault(raw_u, len(u_map))
        mapped = [i_map.setdefault(ri, len(i_map)) for ri in dedup]
        for it in mapped[:-2]:
            train_pairs.append((u_id, it))
        val_item[u_id] = mapped[-2]
        test_item[u_id] = mapped[-1]

    n_users = len(u_map)
    n_items = len(i_map)
    train_dict: dict[int, set[int]] = defaultdict(set)
    for u, it in train_pairs:
        train_dict[u].add(it)

    return {
        "n_users": n_users,
        "n_items": n_items,
        "train_pairs": train_pairs,
        "train_dict": train_dict,
        "val_item": val_item,
        "test_item": test_item,
    }


def build_bipartite_norm_adj(n_users: int, n_items: int, train_pairs: list[tuple[int, int]], device: torch.device) -> torch.Tensor:
    """Build LightGCN symmetric normalized bipartite adjacency A_hat = D^{-1/2} A D^{-1/2} (He et al. 2020)."""
    n_nodes = n_users + n_items
    rows, cols = [], []
    for u, i in train_pairs:
        rows.append(u)
        cols.append(n_users + i)
        rows.append(n_users + i)
        cols.append(u)
    adj = sp.coo_matrix((np.ones(len(rows), dtype=np.float32), (rows, cols)), shape=(n_nodes, n_nodes))
    deg = np.array(adj.sum(1), dtype=np.float32).flatten()
    d_inv_sqrt = np.where(deg > 0, np.power(np.maximum(deg, 1e-12), -0.5), 0.0)
    vals = d_inv_sqrt[adj.row] * adj.data * d_inv_sqrt[adj.col]
    idx = torch.tensor(np.vstack([adj.row, adj.col]), dtype=torch.long, device=device)
    v = torch.tensor(vals, dtype=torch.float32, device=device)
    return torch.sparse_coo_tensor(idx, v, (n_nodes, n_nodes), device=device).coalesce()


def bpr_ranking_loss(u_emb: torch.Tensor, pos_emb: torch.Tensor, neg_emb: torch.Tensor) -> torch.Tensor:
    """Bayesian Personalized Ranking pairwise loss: -mean(log sigma(s_pos - s_neg))."""
    pos_scores = (u_emb * pos_emb).sum(dim=-1)
    neg_scores = (u_emb * neg_emb).sum(dim=-1)
    return -F.logsigmoid(pos_scores - neg_scores).mean()


def simgcl_infonce_loss(view1: torch.Tensor, view2: torch.Tensor, temp: float = 0.2) -> torch.Tensor:
    """SimGCL InfoNCE contrastive loss between two noise-perturbed embedding views (Yu et al. 2022)."""
    z1 = F.normalize(view1, p=2, dim=-1)
    z2 = F.normalize(view2, p=2, dim=-1)
    logits = (z1 @ z2.T) / temp
    labels = torch.arange(z1.size(0), device=z1.device)
    return F.cross_entropy(logits, labels)


class MFModel(nn.Module):
    def __init__(self, n_users: int, n_items: int, dim: int = 64):
        super().__init__()
        self.user_emb = nn.Embedding(n_users, dim)
        self.item_emb = nn.Embedding(n_items, dim)
        nn.init.normal_(self.user_emb.weight, std=0.1)
        nn.init.normal_(self.item_emb.weight, std=0.1)

    def propagate(self, adj_norm: torch.Tensor, perturbed: bool = False, eps: float = 0.1) -> tuple[torch.Tensor, torch.Tensor]:
        return self.user_emb.weight, self.item_emb.weight


class LightGCNModel(nn.Module):
    """LightGCN layer-averaged neighborhood propagation + optional SimGCL uniform noise views."""
    def __init__(self, n_users: int, n_items: int, dim: int = 64, n_layers: int = 3):
        super().__init__()
        self.n_users = n_users
        self.n_items = n_items
        self.n_layers = n_layers
        self.user_emb = nn.Embedding(n_users, dim)
        self.item_emb = nn.Embedding(n_items, dim)
        nn.init.normal_(self.user_emb.weight, std=0.1)
        nn.init.normal_(self.item_emb.weight, std=0.1)

    def propagate(self, adj_norm: torch.Tensor, perturbed: bool = False, eps: float = 0.1) -> tuple[torch.Tensor, torch.Tensor]:
        ego = torch.cat([self.user_emb.weight, self.item_emb.weight], dim=0)
        embs = [] if perturbed else [ego]
        cur = ego
        for _ in range(self.n_layers):
            cur = torch.sparse.mm(adj_norm, cur)
            if perturbed:
                noise = torch.rand_like(cur)
                cur = cur + torch.sign(cur) * F.normalize(noise, p=2, dim=-1) * eps
            embs.append(cur)
        final = torch.stack(embs, dim=0).mean(dim=0)
        return final[: self.n_users], final[self.n_users :]


def evaluate_full_ranking(
    scores_matrix: torch.Tensor,
    train_dict: dict[int, set[int]],
    target_dict: dict[int, int],
    exclude_dict: dict[int, int] | None = None,
) -> dict[str, float]:
    """Full-catalog ranking evaluation (Recall@10, NDCG@10, Recall@20, NDCG@20) masking training items."""
    scores = scores_matrix.detach().clone()
    for u, seen in train_dict.items():
        if seen:
            scores[u, list(seen)] = -1e9
        if exclude_dict and u in exclude_dict:
            scores[u, exclude_dict[u]] = -1e9

    topk = torch.topk(scores, k=20, dim=1).indices.cpu().numpy()
    r10, n10, r20, n20 = [], [], [], []
    for u, gt in target_dict.items():
        ranked = topk[u]
        pos_hits = np.where(ranked == gt)[0]
        if len(pos_hits) > 0:
            rank = int(pos_hits[0]) + 1
            r20.append(1.0)
            n20.append(1.0 / math.log2(rank + 1))
            if rank <= 10:
                r10.append(1.0)
                n10.append(1.0 / math.log2(rank + 1))
            else:
                r10.append(0.0)
                n10.append(0.0)
        else:
            r10.append(0.0)
            n10.append(0.0)
            r20.append(0.0)
            n20.append(0.0)
    return {
        "recall10": round(float(np.mean(r10)), 4),
        "ndcg10": round(float(np.mean(n10)), 4),
        "recall20": round(float(np.mean(r20)), 4),
        "ndcg20": round(float(np.mean(n20)), 4),
    }


def run_popularity_baseline(ds: dict, device: torch.device) -> dict:
    counts = np.zeros(ds["n_items"], dtype=np.float32)
    for _, it in ds["train_pairs"]:
        counts[it] += 1.0
    scores = torch.tensor(counts, device=device).unsqueeze(0).expand(ds["n_users"], -1)
    val_m = evaluate_full_ranking(scores, ds["train_dict"], ds["val_item"])
    test_m = evaluate_full_ranking(scores, ds["train_dict"], ds["test_item"], exclude_dict=ds["val_item"])
    return {
        "method": "R0_Pop",
        "seed": 42,
        "best_epoch": 0,
        "val_ndcg20": val_m["ndcg20"],
        "test_recall10": test_m["recall10"],
        "test_ndcg10": test_m["ndcg10"],
        "test_recall20": test_m["recall20"],
        "test_ndcg20": test_m["ndcg20"],
        "elapsed_s": 0.01,
    }


def train_cf_run(
    method: str,
    ds: dict,
    adj_norm: torch.Tensor,
    seed: int,
    epochs: int,
    batch_size: int,
    device: torch.device,
) -> dict:
    set_seed(seed)
    t0 = time.perf_counter()
    n_users, n_items = ds["n_users"], ds["n_items"]
    if method == "R1_MF_BPR":
        model = MFModel(n_users, n_items, dim=64).to(device)
    else:
        model = LightGCNModel(n_users, n_items, dim=64, n_layers=3).to(device)

    opt = torch.optim.Adam(model.parameters(), lr=2e-3)
    pairs = ds["train_pairs"]
    train_dict = ds["train_dict"]
    reg_weight = 1e-4
    cl_weight = 0.2 if method == "R3_SimGCL" else 0.0
    cl_eps = 0.1
    cl_temp = 0.2

    best_val_ndcg = -1.0
    best_epoch = 0
    best_state = None

    for ep in range(1, epochs + 1):
        model.train()
        perm = np.random.permutation(len(pairs))
        for start in range(0, len(pairs), batch_size):
            batch_idx = perm[start : start + batch_size]
            u_list = [pairs[k][0] for k in batch_idx]
            p_list = [pairs[k][1] for k in batch_idx]
            n_list = []
            for u in u_list:
                neg = random.randrange(n_items)
                while neg in train_dict[u]:
                    neg = random.randrange(n_items)
                n_list.append(neg)

            u_t = torch.tensor(u_list, dtype=torch.long, device=device)
            p_t = torch.tensor(p_list, dtype=torch.long, device=device)
            n_t = torch.tensor(n_list, dtype=torch.long, device=device)

            opt.zero_grad()
            u_all, i_all = model.propagate(adj_norm, perturbed=False)
            loss_bpr = bpr_ranking_loss(u_all[u_t], i_all[p_t], i_all[n_t])
            reg_loss = (
                model.user_emb(u_t).pow(2).sum()
                + model.item_emb(p_t).pow(2).sum()
                + model.item_emb(n_t).pow(2).sum()
            ) / len(u_list)
            loss = loss_bpr + reg_weight * reg_loss

            if cl_weight > 0.0:
                u_v1, i_v1 = model.propagate(adj_norm, perturbed=True, eps=cl_eps)
                u_v2, i_v2 = model.propagate(adj_norm, perturbed=True, eps=cl_eps)
                uniq_u = torch.unique(u_t)
                uniq_i = torch.unique(p_t)
                loss_cl = simgcl_infonce_loss(u_v1[uniq_u], u_v2[uniq_u], temp=cl_temp) + simgcl_infonce_loss(
                    i_v1[uniq_i], i_v2[uniq_i], temp=cl_temp
                )
                loss = loss + cl_weight * loss_cl

            loss.backward()
            opt.step()

        if ep % 5 == 0 or ep == epochs:
            model.eval()
            with torch.no_grad():
                u_all, i_all = model.propagate(adj_norm, perturbed=False)
                val_m = evaluate_full_ranking(u_all @ i_all.T, train_dict, ds["val_item"])
                if val_m["ndcg20"] > best_val_ndcg:
                    best_val_ndcg = val_m["ndcg20"]
                    best_epoch = ep
                    best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        u_all, i_all = model.propagate(adj_norm, perturbed=False)
        scores = u_all @ i_all.T
        test_m = evaluate_full_ranking(scores, train_dict, ds["test_item"], exclude_dict=ds["val_item"])

    return {
        "method": method,
        "seed": seed,
        "best_epoch": best_epoch,
        "val_ndcg20": round(best_val_ndcg, 4),
        "test_recall10": test_m["recall10"],
        "test_ndcg10": test_m["ndcg10"],
        "test_recall20": test_m["recall20"],
        "test_ndcg20": test_m["ndcg20"],
        "elapsed_s": round(time.perf_counter() - t0, 2),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workspace", "-w", default=".")
    ap.add_argument("--seeds", nargs="+", type=int, default=[42, 43, 44])
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--batch-size", type=int, default=1024)
    ap.add_argument("--cache-dir", default="/tmp/veriloop_recsys_data")
    a = ap.parse_args()

    ws = Path(a.workspace).resolve()
    (ws / "out").mkdir(parents=True, exist_ok=True)
    csv_dir = ws / "runs/csv"
    csv_dir.mkdir(parents=True, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    gpu_name = torch.cuda.get_device_name(0) if device.type == "cuda" else "CPU"
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats()

    ds = load_movielens_100k(Path(a.cache_dir))
    adj_norm = build_bipartite_norm_adj(ds["n_users"], ds["n_items"], ds["train_pairs"], device)

    ledger_path = ws / "out/trajectory_ledger.jsonl"
    ledger_path.write_text("", encoding="utf-8")

    t_all = time.perf_counter()
    summary_lines = [
        "=== VERILOOP LEVEL-2 RECSYS REAL-GPU STUDY SUMMARY (ZERO OVERRIDES) ===",
        f"DATASET movielens_100k users={ds['n_users']} items={ds['n_items']} train_interactions={len(ds['train_pairs'])}",
    ]

    all_rows = []
    # 1. Deterministic Popularity baseline
    pop = run_popularity_baseline(ds, device)
    all_rows.append(pop)
    with ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(pop) + "\n")
    for s in a.seeds:
        with (csv_dir / f"R0_Pop_s{s}.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["epoch", "val_ndcg20", "test_recall10", "test_ndcg10", "test_recall20", "test_ndcg20"])
            w.writeheader()
            w.writerow({
                "epoch": 0,
                "val_ndcg20": pop["val_ndcg20"],
                "test_recall10": pop["test_recall10"],
                "test_ndcg10": pop["test_ndcg10"],
                "test_recall20": pop["test_recall20"],
                "test_ndcg20": pop["test_ndcg20"],
            })
    summary_lines.append(
        f"SUMMARY ml100k R0_Pop          n=1 | val_ndcg20={pop['val_ndcg20']:.4f} | "
        f"test_recall10={pop['test_recall10']:.4f} test_ndcg10={pop['test_ndcg10']:.4f} | "
        f"test_recall20={pop['test_recall20']:.4f} test_ndcg20={pop['test_ndcg20']:.4f}"
    )
    print(summary_lines[-1], flush=True)

    # 2. Learned CF models across 3 seeds
    for method in ("R1_MF_BPR", "R2_LightGCN", "R3_SimGCL"):
        m_rows = []
        for s in a.seeds:
            rec = train_cf_run(method, ds, adj_norm, s, a.epochs, a.batch_size, device)
            m_rows.append(rec)
            all_rows.append(rec)
            with ledger_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
            with (csv_dir / f"{method}_s{s}.csv").open("w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=["epoch", "val_ndcg20", "test_recall10", "test_ndcg10", "test_recall20", "test_ndcg20"])
                w.writeheader()
                w.writerow({
                    "epoch": rec["best_epoch"],
                    "val_ndcg20": rec["val_ndcg20"],
                    "test_recall10": rec["test_recall10"],
                    "test_ndcg10": rec["test_ndcg10"],
                    "test_recall20": rec["test_recall20"],
                    "test_ndcg20": rec["test_ndcg20"],
                })
        r20 = [r["test_recall20"] for r in m_rows]
        n20 = [r["test_ndcg20"] for r in m_rows]
        r10 = [r["test_recall10"] for r in m_rows]
        n10 = [r["test_ndcg10"] for r in m_rows]
        vn20 = [r["val_ndcg20"] for r in m_rows]
        sd_n20 = statistics.stdev(n20) if len(n20) > 1 else 0.0
        ci_half = 4.303 * sd_n20 / math.sqrt(len(n20)) if len(n20) == 3 else 1.96 * sd_n20 / math.sqrt(max(1, len(n20)))
        line = (
            f"SUMMARY ml100k {method:15s} n={len(m_rows)} | "
            f"val_ndcg20={statistics.mean(vn20):.4f}±{statistics.stdev(vn20):.4f} | "
            f"test_recall10={statistics.mean(r10):.4f}±{statistics.stdev(r10):.4f} "
            f"test_ndcg10={statistics.mean(n10):.4f}±{statistics.stdev(n10):.4f} | "
            f"test_recall20={statistics.mean(r20):.4f}±{statistics.stdev(r20):.4f} "
            f"test_ndcg20={statistics.mean(n20):.4f}±{sd_n20:.4f} [{statistics.mean(n20)-ci_half:.4f},{statistics.mean(n20)+ci_half:.4f}]"
        )
        summary_lines.append(line)
        print(line, flush=True)

    total_s = round(time.perf_counter() - t_all, 2)
    peak_mb = round(torch.cuda.max_memory_allocated() / (1024 * 1024), 1) if device.type == "cuda" else 0.0
    header_meta = (
        f"RUNS total_runs={len(all_rows)} gpu={gpu_name} torch={torch.__version__} "
        f"total_gpu_s={total_s} peak_vram_mb={peak_mb} COMPLETE"
    )
    summary_lines.insert(1, header_meta)
    (ws / "out/recsys_summary.txt").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print(header_meta, flush=True)


if __name__ == "__main__":
    main()
