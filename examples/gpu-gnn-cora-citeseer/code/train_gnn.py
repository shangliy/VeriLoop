#!/usr/bin/env python3
"""VeriLoop Level-2 GNN Real-GPU Study: Oversmoothing & Residual Propagation on Cora and CiteSeer.

Implements 5 progressive models across standard Planetoid splits (Cora & CiteSeer)
over 5 seeds on CUDA/CPU with strict validation-only checkpoint selection:
  - M0_MLP          : Feature-only 2-layer MLP baseline
  - M1_GCN_2L       : 2-layer Kipf & Welling (2017) normalized adjacency GCN
  - M2_GCN_8L_Deep  : 8-layer plain GCN (demonstrates oversmoothing collapse)
  - M3_APPNP_PPR    : Decoupled MLP + K-step Personalized PageRank propagation (Gasteiger et al. 2019)
  - M4_GCNII_8L     : 8-layer GCNII with initial residual + identity mapping (Chen et al. 2020)

Outputs per-seed CSVs under runs/{cora,citeseer}/csv/ (consumed directly by `./veriloop bind`),
append-only out/trajectory_ledger.jsonl, and aggregate out/gnn_summary.txt.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import pickle
import random
import statistics
import time
import urllib.request
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import torch
import torch.nn as nn
import torch.nn.functional as F

PLANETOID_BASE = "https://github.com/kimiyoung/planetoid/raw/master/data"
PLANETOID_FILES = ["x", "tx", "allx", "y", "ty", "ally", "graph", "test.index"]


def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _download_planetoid(dataset: str, cache_dir: Path) -> Path:
    ds_dir = cache_dir / dataset
    ds_dir.mkdir(parents=True, exist_ok=True)
    for ext in PLANETOID_FILES:
        fname = f"ind.{dataset}.{ext}"
        fp = ds_dir / fname
        if not fp.is_file() or fp.stat().st_size == 0:
            url = f"{PLANETOID_BASE}/{fname}"
            req = urllib.request.Request(url, headers={"User-Agent": "VeriLoop/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                fp.write_bytes(resp.read())
    return ds_dir


def _load_pickle(fp: Path):
    with fp.open("rb") as fh:
        return pickle.load(fh, encoding="latin1")


def load_planetoid_dataset(dataset: str, cache_dir: Path, device: torch.device) -> dict:
    """Load standard Planetoid Cora/CiteSeer split (train/val/test masks, features, adjacency)."""
    ds_dir = _download_planetoid(dataset, cache_dir)
    objs = [_load_pickle(ds_dir / f"ind.{dataset}.{ext}") for ext in ("x", "y", "tx", "ty", "allx", "ally", "graph")]
    x, y, tx, ty, allx, ally, graph = objs
    test_idx_reorder = [int(l.strip()) for l in (ds_dir / f"ind.{dataset}.test.index").read_text().splitlines() if l.strip()]
    test_idx_range = np.sort(test_idx_reorder)

    if dataset == "citeseer":
        test_idx_full = range(min(test_idx_reorder), max(test_idx_reorder) + 1)
        tx_ext = sp.lil_matrix((len(test_idx_full), x.shape[1]))
        tx_ext[test_idx_range - min(test_idx_range), :] = tx
        tx = tx_ext
        ty_ext = np.zeros((len(test_idx_full), y.shape[1]))
        ty_ext[test_idx_range - min(test_idx_range), :] = ty
        ty = ty_ext

    features = sp.vstack((allx, tx)).tolil()
    features[test_idx_reorder, :] = features[test_idx_range, :]
    rowsum = np.array(features.sum(1), dtype=np.float32)
    r_inv = np.where(rowsum > 0, 1.0 / np.maximum(rowsum, 1e-12), 0.0).flatten()
    features = sp.diags(r_inv).dot(features).toarray().astype(np.float32)

    labels_onehot = np.vstack((ally, ty))
    labels_onehot[test_idx_reorder, :] = labels_onehot[test_idx_range, :]
    labels = np.argmax(labels_onehot, axis=1).astype(np.int64)
    labeled_mask = labels_onehot.sum(axis=1) > 0

    n_nodes = features.shape[0]
    rows, cols = [], []
    for src, nbrs in graph.items():
        for dst in nbrs:
            rows.append(src)
            cols.append(dst)
    adj_sp = sp.coo_matrix((np.ones(len(rows), dtype=np.float32), (rows, cols)), shape=(n_nodes, n_nodes))
    adj_sp = adj_sp + adj_sp.T.multiply(adj_sp.T > adj_sp) - adj_sp.multiply(adj_sp.T > adj_sp)

    idx_train = np.arange(len(y))
    idx_val = np.arange(len(y), len(y) + 500)
    idx_test = test_idx_range

    train_mask = np.zeros(n_nodes, dtype=bool)
    val_mask = np.zeros(n_nodes, dtype=bool)
    test_mask = np.zeros(n_nodes, dtype=bool)
    train_mask[idx_train] = True
    val_mask[idx_val] = True
    test_mask[idx_test] = True
    train_mask &= labeled_mask
    val_mask &= labeled_mask
    test_mask &= labeled_mask

    adj_norm = gcn_normalized_adjacency(adj_sp, device)
    edge_index = torch.tensor(np.vstack([adj_sp.tocoo().row, adj_sp.tocoo().col]), dtype=torch.long, device=device)

    return {
        "name": dataset,
        "x": torch.tensor(features, dtype=torch.float32, device=device),
        "y": torch.tensor(labels, dtype=torch.long, device=device),
        "adj_norm": adj_norm,
        "edge_index": edge_index,
        "train_mask": torch.tensor(train_mask, dtype=torch.bool, device=device),
        "val_mask": torch.tensor(val_mask, dtype=torch.bool, device=device),
        "test_mask": torch.tensor(test_mask, dtype=torch.bool, device=device),
        "num_features": features.shape[1],
        "num_classes": int(labels_onehot.shape[1]),
        "num_nodes": n_nodes,
        "num_edges": int(adj_sp.nnz // 2),
    }


def gcn_normalized_adjacency(adj_sp: sp.spmatrix, device: torch.device) -> torch.Tensor:
    """Compute symmetric normalized adjacency A_hat = D^{-1/2} (A + I) D^{-1/2} (Kipf & Welling 2017)."""
    a_tilde = (adj_sp + sp.eye(adj_sp.shape[0], dtype=np.float32)).tocoo()
    deg = np.array(a_tilde.sum(1), dtype=np.float32).flatten()
    d_inv_sqrt = np.power(np.maximum(deg, 1e-12), -0.5)
    norm_vals = d_inv_sqrt[a_tilde.row] * a_tilde.data * d_inv_sqrt[a_tilde.col]
    indices = torch.tensor(np.vstack([a_tilde.row, a_tilde.col]), dtype=torch.long, device=device)
    values = torch.tensor(norm_vals, dtype=torch.float32, device=device)
    return torch.sparse_coo_tensor(indices, values, a_tilde.shape, device=device).coalesce()


def compute_dirichlet_energy(h: torch.Tensor, edge_index: torch.Tensor) -> float:
    """Measure node representation smoothness (Dirichlet energy across edges; lower = more oversmoothed)."""
    with torch.no_grad():
        h_norm = F.normalize(h, p=2, dim=-1)
        src, dst = edge_index[0], edge_index[1]
        diff = h_norm[src] - h_norm[dst]
        energy = 0.5 * (diff.pow(2).sum(dim=-1).mean().item())
    return float(energy)


def compute_ece(logits: torch.Tensor, targets: torch.Tensor, n_bins: int = 15) -> float:
    with torch.no_grad():
        probs = F.softmax(logits, dim=-1)
        confs, preds = probs.max(dim=-1)
        accs = preds.eq(targets).float()
        ece = torch.zeros(1, device=logits.device)
        bounds = torch.linspace(0.0, 1.0, n_bins + 1, device=logits.device)
        for lo, hi in zip(bounds[:-1], bounds[1:]):
            in_bin = (confs > lo) & (confs <= hi)
            prop = in_bin.float().mean()
            if prop.item() > 0:
                ece += torch.abs(accs[in_bin].mean() - confs[in_bin].mean()) * prop
        return float(ece.item())


class MLPBaseline(nn.Module):
    def __init__(self, in_dim: int, hid: int, out_dim: int, dropout: float = 0.5):
        super().__init__()
        self.fc1 = nn.Linear(in_dim, hid)
        self.fc2 = nn.Linear(hid, out_dim)
        self.dropout = dropout

    def forward(self, x: torch.Tensor, adj_norm: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        h = F.dropout(F.relu(self.fc1(x)), p=self.dropout, training=self.training)
        return self.fc2(h), h


class GCNModel(nn.Module):
    """Multi-layer Kipf & Welling Graph Convolutional Network: H^(l+1) = sigma(A_hat H^(l) W^(l))."""
    def __init__(self, in_dim: int, hid: int, out_dim: int, num_layers: int = 2, dropout: float = 0.5):
        super().__init__()
        self.layers = nn.ModuleList()
        if num_layers == 1:
            self.layers.append(nn.Linear(in_dim, out_dim))
        else:
            self.layers.append(nn.Linear(in_dim, hid))
            for _ in range(num_layers - 2):
                self.layers.append(nn.Linear(hid, hid))
            self.layers.append(nn.Linear(hid, out_dim))
        self.dropout = dropout

    def forward(self, x: torch.Tensor, adj_norm: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        h = x
        for layer in self.layers[:-1]:
            h = F.dropout(h, p=self.dropout, training=self.training)
            h = torch.sparse.mm(adj_norm, layer(h))
            h = F.relu(h)
        last_h = h
        h = F.dropout(h, p=self.dropout, training=self.training)
        logits = torch.sparse.mm(adj_norm, self.layers[-1](h))
        return logits, last_h


def appnp_ppr_propagate(z0: torch.Tensor, adj_norm: torch.Tensor, alpha: float = 0.1, steps: int = 10) -> torch.Tensor:
    """Personalized PageRank propagation: Z^(k+1) = (1 - alpha) A_hat Z^(k) + alpha Z^(0) (Gasteiger et al. 2019)."""
    z = z0
    for _ in range(steps):
        z = (1.0 - alpha) * torch.sparse.mm(adj_norm, z) + alpha * z0
    return z


class APPNPModel(nn.Module):
    def __init__(self, in_dim: int, hid: int, out_dim: int, alpha: float = 0.1, steps: int = 10, dropout: float = 0.5):
        super().__init__()
        self.fc1 = nn.Linear(in_dim, hid)
        self.fc2 = nn.Linear(hid, out_dim)
        self.alpha = alpha
        self.steps = steps
        self.dropout = dropout

    def forward(self, x: torch.Tensor, adj_norm: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        h = F.dropout(x, p=self.dropout, training=self.training)
        h = F.relu(self.fc1(h))
        h = F.dropout(h, p=self.dropout, training=self.training)
        z0 = self.fc2(h)
        logits = appnp_ppr_propagate(z0, adj_norm, alpha=self.alpha, steps=self.steps)
        return logits, logits


class GCNIILayer(nn.Module):
    """GCNII layer with initial residual alpha and identity mapping beta (Chen et al. 2020)."""
    def __init__(self, hid: int):
        super().__init__()
        self.weight = nn.Parameter(torch.empty(hid, hid))
        nn.init.xavier_uniform_(self.weight)

    def forward(self, h: torch.Tensor, h0: torch.Tensor, adj_norm: torch.Tensor, alpha: float, beta: float) -> torch.Tensor:
        support = (1.0 - alpha) * torch.sparse.mm(adj_norm, h) + alpha * h0
        return (1.0 - beta) * support + beta * (support @ self.weight)


class GCNIIModel(nn.Module):
    def __init__(self, in_dim: int, hid: int, out_dim: int, num_layers: int = 8, alpha: float = 0.15, lam: float = 0.5, dropout: float = 0.5):
        super().__init__()
        self.in_proj = nn.Linear(in_dim, hid)
        self.convs = nn.ModuleList([GCNIILayer(hid) for _ in range(num_layers)])
        self.out_proj = nn.Linear(hid, out_dim)
        self.alpha = alpha
        self.lam = lam
        self.dropout = dropout

    def forward(self, x: torch.Tensor, adj_norm: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        h = F.dropout(x, p=self.dropout, training=self.training)
        h0 = F.relu(self.in_proj(h))
        h = h0
        for idx, conv in enumerate(self.convs, start=1):
            beta = math.log(self.lam / idx + 1.0)
            h = F.dropout(h, p=self.dropout, training=self.training)
            h = F.relu(conv(h, h0, adj_norm, alpha=self.alpha, beta=beta))
        last_h = h
        logits = self.out_proj(F.dropout(h, p=self.dropout, training=self.training))
        return logits, last_h


def build_model(name: str, in_dim: int, out_dim: int, device: torch.device) -> nn.Module:
    if name == "M0_MLP":
        return MLPBaseline(in_dim, 64, out_dim, dropout=0.5).to(device)
    if name == "M1_GCN_2L":
        return GCNModel(in_dim, 64, out_dim, num_layers=2, dropout=0.5).to(device)
    if name == "M2_GCN_8L_Deep":
        return GCNModel(in_dim, 64, out_dim, num_layers=8, dropout=0.5).to(device)
    if name == "M3_APPNP_PPR":
        return APPNPModel(in_dim, 64, out_dim, alpha=0.1, steps=10, dropout=0.5).to(device)
    if name == "M4_GCNII_8L":
        return GCNIIModel(in_dim, 64, out_dim, num_layers=8, alpha=0.15, lam=0.5, dropout=0.5).to(device)
    if name == "M4b_GCNII_SplitWD":
        return GCNIIModel(in_dim, 64, out_dim, num_layers=8, alpha=0.1, lam=0.5, dropout=0.6).to(device)
    raise ValueError(f"Unknown model: {name}")


def evaluate_node_classification(model: nn.Module, data: dict, mask: torch.Tensor) -> tuple[float, float, float]:
    model.eval()
    with torch.no_grad():
        logits, hidden = model(data["x"], data["adj_norm"])
        preds = logits[mask].argmax(dim=-1)
        acc = float(preds.eq(data["y"][mask]).float().mean().item())
        ece = compute_ece(logits[mask], data["y"][mask])
        energy = compute_dirichlet_energy(hidden, data["edge_index"])
    return acc, ece, energy


def train_one_run(model_name: str, data: dict, seed: int, epochs: int, device: torch.device) -> dict:
    """Train with strict validation-only checkpoint selection; score test split once on best val epoch."""
    set_seed(seed)
    t0 = time.perf_counter()
    model = build_model(model_name, data["num_features"], data["num_classes"], device)
    if model_name == "M4b_GCNII_SplitWD":
        # Per Chen et al. (2020): apply higher weight decay ONLY to deep conv weights, low decay on input/output projections
        opt = torch.optim.Adam([
            {"params": list(model.convs.parameters()), "weight_decay": 1e-2},
            {"params": list(model.in_proj.parameters()) + list(model.out_proj.parameters()), "weight_decay": 5e-4},
        ], lr=0.01)
    else:
        wd = 1e-2 if model_name == "M4_GCNII_8L" else 5e-4
        opt = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=wd)

    best_val_acc = -1.0
    best_val_loss = float("inf")
    best_state = None
    best_epoch = 0

    for ep in range(1, epochs + 1):
        model.train()
        opt.zero_grad()
        logits, _ = model(data["x"], data["adj_norm"])
        loss = F.cross_entropy(logits[data["train_mask"]], data["y"][data["train_mask"]])
        loss.backward()
        opt.step()

        model.eval()
        with torch.no_grad():
            v_logits, _ = model(data["x"], data["adj_norm"])
            v_loss = float(F.cross_entropy(v_logits[data["val_mask"]], data["y"][data["val_mask"]]).item())
            v_acc = float(v_logits[data["val_mask"]].argmax(dim=-1).eq(data["y"][data["val_mask"]]).float().mean().item())
            if (v_acc > best_val_acc) or (v_acc == best_val_acc and v_loss < best_val_loss):
                best_val_acc = v_acc
                best_val_loss = v_loss
                best_epoch = ep
                best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)

    val_acc, val_ece, _ = evaluate_node_classification(model, data, data["val_mask"])
    test_acc, test_ece, dirichlet_e = evaluate_node_classification(model, data, data["test_mask"])
    elapsed = round(time.perf_counter() - t0, 3)

    return {
        "dataset": data["name"],
        "method": model_name,
        "seed": seed,
        "best_epoch": best_epoch,
        "val_acc": round(val_acc, 4),
        "test_acc": round(test_acc, 4),
        "test_ece": round(test_ece, 4),
        "dirichlet_energy": round(dirichlet_e, 4),
        "elapsed_s": elapsed,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workspace", "-w", default=".", help="Workspace root directory")
    ap.add_argument("--datasets", nargs="+", default=["cora", "citeseer"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[42, 43, 44, 45, 46])
    ap.add_argument("--epochs", type=int, default=200)
    ap.add_argument("--cache-dir", default="/tmp/veriloop_gnn_data")
    a = ap.parse_args()

    ws = Path(a.workspace).resolve()
    (ws / "out").mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    gpu_name = torch.cuda.get_device_name(0) if device.type == "cuda" else "CPU"
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats()

    methods = ["M0_MLP", "M1_GCN_2L", "M2_GCN_8L_Deep", "M3_APPNP_PPR", "M4_GCNII_8L", "M4b_GCNII_SplitWD"]
    ledger_path = ws / "out/trajectory_ledger.jsonl"
    ledger_path.write_text("", encoding="utf-8")

    t_all = time.perf_counter()
    summary_lines = ["=== VERILOOP LEVEL-2 GNN REAL-GPU STUDY SUMMARY (ZERO OVERRIDES) ==="]
    all_rows = []

    for ds_name in a.datasets:
        data = load_planetoid_dataset(ds_name, Path(a.cache_dir), device)
        csv_dir = ws / "runs" / ds_name / "csv"
        csv_dir.mkdir(parents=True, exist_ok=True)
        summary_lines.append("")
        summary_lines.append(
            f"--- DATASET: {ds_name} (nodes={data['num_nodes']} edges={data['num_edges']} "
            f"feats={data['num_features']} classes={data['num_classes']}) ---"
        )
        for m in methods:
            m_rows = []
            for s in a.seeds:
                rec = train_one_run(m, data, s, a.epochs, device)
                m_rows.append(rec)
                all_rows.append(rec)
                with ledger_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec) + "\n")
                csv_p = csv_dir / f"{m}_s{s}.csv"
                with csv_p.open("w", newline="", encoding="utf-8") as fh:
                    w = csv.DictWriter(fh, fieldnames=["epoch", "val_acc", "test_acc", "test_ece", "dirichlet_energy"])
                    w.writeheader()
                    w.writerow({
                        "epoch": rec["best_epoch"],
                        "val_acc": rec["val_acc"],
                        "test_acc": rec["test_acc"],
                        "test_ece": rec["test_ece"],
                        "dirichlet_energy": rec["dirichlet_energy"],
                    })
            vals = [r["test_acc"] for r in m_rows]
            v_accs = [r["val_acc"] for r in m_rows]
            eces = [r["test_ece"] for r in m_rows]
            engs = [r["dirichlet_energy"] for r in m_rows]
            mean_t = statistics.mean(vals)
            sd_t = statistics.stdev(vals) if len(vals) > 1 else 0.0
            ci_half = 2.776 * sd_t / math.sqrt(len(vals)) if len(vals) == 5 else 1.96 * sd_t / math.sqrt(max(1, len(vals)))
            line = (
                f"SUMMARY {ds_name} {m:15s} n={len(vals)} | "
                f"val_acc={statistics.mean(v_accs):.4f}±{statistics.stdev(v_accs):.4f} | "
                f"test_acc={mean_t:.4f}±{sd_t:.4f} [{mean_t - ci_half:.4f},{mean_t + ci_half:.4f}] | "
                f"test_ece={statistics.mean(eces):.4f}±{statistics.stdev(eces):.4f} | "
                f"dirichlet_energy={statistics.mean(engs):.4f}±{statistics.stdev(engs):.4f}"
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
    (ws / "out/gnn_summary.txt").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print(header_meta, flush=True)


if __name__ == "__main__":
    main()
