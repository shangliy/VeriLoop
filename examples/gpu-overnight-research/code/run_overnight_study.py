#!/usr/bin/env python3
"""VeriLoop Long-Horizon Real-GPU Research Study (Crash-Resumable, Zero-Fabrication).

Executes an 8-stage progressive deep learning study across TWO real vision benchmarks
(CIFAR-10 and Fashion-MNIST, 3 independent random seeds per arm, 42 total GPU runs)
on CUDA with strict validation-only model & temperature-scaling selection:

  CIFAR-10 (45k train / 5k val / 10k test, 30 epochs, AMP fp16):
    1. M0_Linear            : Linear classifier baseline (G3 simple baseline)
    2. M1_PlainCNN          : 4-stage ConvNet without BatchNorm or residual skips
    3. M2_ResNet_Base       : 3-stage ResNet + BatchNorm (constant LR, no augmentation)
    4. M3_ResNet_Aug        : + RandomCrop(4) & RandomHorizontalFlip
    5. M4_ResNet_Aug_Cosine : + SGD(momentum=0.9, nesterov, wd=5e-4) + Warmup+CosineAnnealingLR
    6. M5_ResNet_LS         : + Label Smoothing (eps=0.1)
    7. M6_ResNet_Mixup      : + Mixup (alpha=0.4)
    8. M7_SEResNet_Full     : + Squeeze-and-Excitation blocks + Cutout(8x8) + Cosine + WD

  Fashion-MNIST (50k train / 10k val / 10k test, 15 epochs, AMP fp16):
    Core 6-step ladder: M0_Linear, M1_PlainCNN, M2_ResNet_Base, M4_ResNet_Aug_Cosine,
    M5_ResNet_LS, M7_SEResNet_Full.

Every single run:
  - Evaluates held-out test set STRICTLY ONCE on the validation-selected checkpoint.
  - Fits post-hoc Temperature Scaling (T*) strictly on the validation logits, then measures
    both raw and temperature-calibrated NLL, ECE (15-bin), and Brier score on held-out test.
  - Logs simultaneously to TensorBoard (.tfevents), W&B local files, CSV, and append-only
    crash-resumable `out/trajectory_ledger.jsonl`.
  - Updates `wiki/RESEARCH_WIKI.md` and runs deterministic VeriLoop gates (`trace_numbers.py`
    + `audit_code.py`) after EVERY completed iteration, recording the gate trace in
    `out/gate_audit_trace.jsonl`.
"""
import argparse
import csv
import hashlib
import json
import math
import random
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset, Subset
from torchvision import datasets, transforms

REPO_ROOT = Path(__file__).resolve().parents[3]
RL_SCRIPTS = REPO_ROOT / "skills/research-loop/scripts"
sys.path.insert(0, str(REPO_ROOT / "tools"))
import paper_bind as pb  # noqa: E402


def sha256_file(fp: Path) -> str:
    h = hashlib.sha256()
    with fp.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def seed_everything(seed: int):
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = True


# ==================== ARCHITECTURES ====================

class LinearBaseline(nn.Module):
    def __init__(self, in_ch: int, img_size: int, n_classes: int = 10):
        super().__init__()
        self.fc = nn.Linear(in_ch * img_size * img_size, n_classes)

    def forward(self, x):
        return self.fc(x.flatten(1))


class PlainCNN(nn.Module):
    def __init__(self, in_ch: int, n_classes: int = 10):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(in_ch, 32, 3, padding=1), nn.ReLU(inplace=True),
            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(inplace=True), nn.MaxPool2d(2),
            nn.Conv2d(64, 128, 3, padding=1), nn.ReLU(inplace=True), nn.MaxPool2d(2),
            nn.Conv2d(128, 128, 3, padding=1), nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d(1),
        )
        self.head = nn.Linear(128, n_classes)

    def forward(self, x):
        return self.head(self.net(x).flatten(1))


class SEBlock(nn.Module):
    def __init__(self, ch: int, reduction: int = 8):
        super().__init__()
        mid = max(8, ch // reduction)
        self.fc1 = nn.Linear(ch, mid)
        self.fc2 = nn.Linear(mid, ch)

    def forward(self, x):
        b, c, _, _ = x.shape
        s = x.mean(dim=(2, 3))
        s = torch.sigmoid(self.fc2(F.relu(self.fc1(s), inplace=True))).view(b, c, 1, 1)
        return x * s


class ResBlock(nn.Module):
    def __init__(self, in_ch: int, out_ch: int, stride: int = 1, use_se: bool = False):
        super().__init__()
        self.conv1 = nn.Conv2d(in_ch, out_ch, 3, stride=stride, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(out_ch)
        self.conv2 = nn.Conv2d(out_ch, out_ch, 3, stride=1, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(out_ch)
        self.se = SEBlock(out_ch) if use_se else nn.Identity()
        self.skip = (
            nn.Sequential(nn.Conv2d(in_ch, out_ch, 1, stride=stride, bias=False), nn.BatchNorm2d(out_ch))
            if (stride != 1 or in_ch != out_ch)
            else nn.Identity()
        )

    def forward(self, x):
        h = F.relu(self.bn1(self.conv1(x)), inplace=True)
        h = self.se(self.bn2(self.conv2(h)))
        return F.relu(h + self.skip(x), inplace=True)


class SmallResNet(nn.Module):
    """3-stage CIFAR ResNet-14 (6 residual blocks, width 32-64-128, ~560k params) with optional SE attention."""
    def __init__(self, in_ch: int, use_se: bool = False, n_classes: int = 10):
        super().__init__()
        self.stem = nn.Sequential(nn.Conv2d(in_ch, 32, 3, padding=1, bias=False), nn.BatchNorm2d(32), nn.ReLU(inplace=True))
        self.s1 = nn.Sequential(ResBlock(32, 32, 1, use_se), ResBlock(32, 32, 1, use_se))
        self.s2 = nn.Sequential(ResBlock(32, 64, 2, use_se), ResBlock(64, 64, 1, use_se))
        self.s3 = nn.Sequential(ResBlock(64, 128, 2, use_se), ResBlock(128, 128, 1, use_se))
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.head = nn.Linear(128, n_classes)

    def forward(self, x):
        h = self.s3(self.s2(self.s1(self.stem(x))))
        return self.head(self.pool(h).flatten(1))


def augment_batch_gpu(x: torch.Tensor, aug: bool, cutout: int) -> torch.Tensor:
    """Fast vectorized per-sample RandomHorizontalFlip, RandomCrop(pad=4), and Cutout on GPU."""
    if aug:
        b, _, h, w = x.shape
        flip = torch.rand(b, 1, 1, 1, device=x.device) < 0.5
        x = torch.where(flip, x.flip(-1), x)
        pad = 4
        xp = F.pad(x, (pad, pad, pad, pad), mode="constant", value=0.0).permute(0, 2, 3, 1)
        dy = torch.randint(0, 2 * pad + 1, (b,), device=x.device)
        dx = torch.randint(0, 2 * pad + 1, (b,), device=x.device)
        rows = dy[:, None] + torch.arange(h, device=x.device)[None, :]
        cols = dx[:, None] + torch.arange(w, device=x.device)[None, :]
        b_idx = torch.arange(b, device=x.device)[:, None, None]
        x = xp[b_idx, rows[:, :, None], cols[:, None, :]].permute(0, 3, 1, 2).contiguous()
    if cutout > 0:
        b, _, h, w = x.shape
        cy = torch.randint(0, h, (b,), device=x.device)
        cx = torch.randint(0, w, (b,), device=x.device)
        half = cutout // 2
        yy = torch.arange(h, device=x.device)[None, :]
        xx = torch.arange(w, device=x.device)[None, :]
        mask_y = (yy >= (cy[:, None] - half)) & (yy < (cy[:, None] + half))
        mask_x = (xx >= (cx[:, None] - half)) & (xx < (cx[:, None] + half))
        mask = ~(mask_y[:, :, None] & mask_x[:, None, :])
        x = x * mask[:, None, :, :].to(x.dtype)
    return x


def load_normalized_tensors(ds_name: str, data_root: Path):
    """Preload and normalize entire dataset ONCE in RAM to eliminate PIL/DataLoader bottlenecks."""
    dspec = DATASET_SPECS[ds_name]
    mean = torch.tensor(dspec["mean"], dtype=torch.float32).view(1, -1, 1, 1)
    std = torch.tensor(dspec["std"], dtype=torch.float32).view(1, -1, 1, 1)
    if ds_name == "cifar10":
        raw_tr = datasets.CIFAR10(str(data_root / "veriloop_cifar10_data"), train=True, download=True)
        raw_te = datasets.CIFAR10(str(data_root / "veriloop_cifar10_data"), train=False, download=True)
        x_tr = torch.from_numpy(raw_tr.data).permute(0, 3, 1, 2).float().div_(255.0).sub_(mean).div_(std)
        y_tr = torch.tensor(raw_tr.targets, dtype=torch.long)
        x_te = torch.from_numpy(raw_te.data).permute(0, 3, 1, 2).float().div_(255.0).sub_(mean).div_(std)
        y_te = torch.tensor(raw_te.targets, dtype=torch.long)
    else:
        raw_tr = datasets.FashionMNIST(str(data_root / "veriloop_fmnist_data"), train=True, download=True)
        raw_te = datasets.FashionMNIST(str(data_root / "veriloop_fmnist_data"), train=False, download=True)
        x_tr = raw_tr.data.unsqueeze(1).float().div_(255.0).sub_(mean).div_(std)
        y_tr = raw_tr.targets.clone().long()
        x_te = raw_te.data.unsqueeze(1).float().div_(255.0).sub_(mean).div_(std)
        y_te = raw_te.targets.clone().long()

    # Fixed train/val split shared across all methods & seeds (strictly no test leakage)
    perm = torch.randperm(len(y_tr), generator=torch.Generator().manual_seed(0))
    val_n = dspec["val_n"]
    tr_idx, val_idx = perm[:-val_n], perm[-val_n:]
    return (x_tr[tr_idx], y_tr[tr_idx]), (x_tr[val_idx], y_tr[val_idx]), (x_te, y_te)


# ==================== CALIBRATION METRICS (ECE, BRIER, TEMP SCALING) ====================

@torch.no_grad()
def collect_logits(model: nn.Module, x_all: torch.Tensor, y_all: torch.Tensor, device: torch.device, bs: int = 512) -> tuple[torch.Tensor, torch.Tensor]:
    model.eval()
    all_logits = []
    for i in range(0, len(y_all), bs):
        xb = x_all[i : i + bs].to(device, non_blocking=True)
        with torch.amp.autocast("cuda", enabled=(device.type == "cuda")):
            logits = model(xb)
        all_logits.append(logits.float().cpu())
    return torch.cat(all_logits, dim=0), y_all.cpu()


def compute_metrics_from_logits(logits: torch.Tensor, targets: torch.Tensor, n_bins: int = 15) -> dict:
    probs = F.softmax(logits, dim=1)
    nll = F.cross_entropy(logits, targets).item()
    confs, preds = probs.max(dim=1)
    accs = (preds == targets).float()
    acc = accs.mean().item()

    # 15-bin Expected Calibration Error (Guo et al., 2017)
    ece = 0.0
    boundaries = torch.linspace(0.0, 1.0, n_bins + 1)
    for lo, hi in zip(boundaries[:-1], boundaries[1:]):
        mask = (confs > lo) & (confs <= hi) if lo > 0 else (confs >= lo) & (confs <= hi)
        if mask.any():
            ece += mask.float().mean().item() * abs(accs[mask].mean().item() - confs[mask].mean().item())

    # Multiclass Brier score
    one_hot = F.one_hot(targets, num_classes=logits.size(1)).float()
    brier = ((probs - one_hot) ** 2).sum(dim=1).mean().item()
    return {"acc": acc, "nll": nll, "ece": ece, "brier": brier}


def fit_temperature_on_val(val_logits: torch.Tensor, val_targets: torch.Tensor) -> float:
    """Strictly validation-only post-hoc Temperature Scaling (Guo et al., 2017)."""
    log_t = torch.zeros(1, requires_grad=True)
    opt = torch.optim.LBFGS([log_t], lr=0.1, max_iter=50)

    def closure():
        opt.zero_grad()
        t = torch.exp(log_t).clamp(0.1, 10.0)
        loss = F.cross_entropy(val_logits / t, val_targets)
        loss.backward()
        return loss

    opt.step(closure)
    return float(torch.exp(log_t).clamp(0.1, 10.0).item())


# ==================== EXPERIMENT CONFIGS ====================

METHOD_SPECS = {
    "M0_Linear":            {"arch": "linear", "aug": False, "opt": "adamw", "lr": 2e-3, "wd": 1e-4, "cos": False, "ls": 0.0, "mixup": 0.0, "cutout": 0, "se": False},
    "M1_PlainCNN":          {"arch": "plain",  "aug": False, "opt": "adamw", "lr": 1e-3, "wd": 0.0,  "cos": False, "ls": 0.0, "mixup": 0.0, "cutout": 0, "se": False},
    "M2_ResNet_Base":       {"arch": "resnet", "aug": False, "opt": "adamw", "lr": 1e-3, "wd": 0.0,  "cos": False, "ls": 0.0, "mixup": 0.0, "cutout": 0, "se": False},
    "M3_ResNet_Aug":        {"arch": "resnet", "aug": True,  "opt": "adamw", "lr": 1e-3, "wd": 1e-4, "cos": False, "ls": 0.0, "mixup": 0.0, "cutout": 0, "se": False},
    "M4_ResNet_Aug_Cosine": {"arch": "resnet", "aug": True,  "opt": "sgd",   "lr": 0.1,  "wd": 5e-4, "cos": True,  "ls": 0.0, "mixup": 0.0, "cutout": 0, "se": False},
    "M5_ResNet_LS":         {"arch": "resnet", "aug": True,  "opt": "sgd",   "lr": 0.1,  "wd": 5e-4, "cos": True,  "ls": 0.1, "mixup": 0.0, "cutout": 0, "se": False},
    "M6_ResNet_Mixup":      {"arch": "resnet", "aug": True,  "opt": "sgd",   "lr": 0.1,  "wd": 5e-4, "cos": True,  "ls": 0.0, "mixup": 0.4, "cutout": 0, "se": False},
    "M7_SEResNet_Full":     {"arch": "resnet", "aug": True,  "opt": "sgd",   "lr": 0.1,  "wd": 5e-4, "cos": True,  "ls": 0.05,"mixup": 0.0, "cutout": 8, "se": True},
}

DATASET_SPECS = {
    "cifar10": {
        "in_ch": 3, "img_size": 32, "val_n": 5000, "epochs": 30,
        "mean": (0.4914, 0.4822, 0.4465), "std": (0.2470, 0.2435, 0.2616),
        "methods": [
            "M0_Linear", "M1_PlainCNN", "M2_ResNet_Base", "M3_ResNet_Aug",
            "M4_ResNet_Aug_Cosine", "M5_ResNet_LS", "M6_ResNet_Mixup", "M7_SEResNet_Full",
        ],
    },
    "fmnist": {
        "in_ch": 1, "img_size": 28, "val_n": 10000, "epochs": 15,
        "mean": (0.2860,), "std": (0.3530,),
        "methods": [
            "M0_Linear", "M1_PlainCNN", "M2_ResNet_Base",
            "M4_ResNet_Aug_Cosine", "M5_ResNet_LS", "M7_SEResNet_Full",
        ],
    },
}


def build_model(spec: dict, in_ch: int, img_size: int) -> nn.Module:
    if spec["arch"] == "linear":
        return LinearBaseline(in_ch, img_size)
    if spec["arch"] == "plain":
        return PlainCNN(in_ch)
    return SmallResNet(in_ch, use_se=spec["se"])


def run_single(ds_name: str, method: str, seed: int, epochs: int, batch_size: int, splits, device: torch.device, ws: Path) -> dict:
    dspec = DATASET_SPECS[ds_name]
    mspec = METHOD_SPECS[method]
    seed_everything(seed)

    (x_tr, y_tr), (x_val, y_val), (x_te, y_te) = splits
    n_tr = len(y_tr)
    gen = torch.Generator().manual_seed(seed)

    model = build_model(mspec, dspec["in_ch"], dspec["img_size"]).to(device)
    n_params = sum(p.numel() for p in model.parameters())

    if mspec["opt"] == "sgd":
        opt = torch.optim.SGD(model.parameters(), lr=mspec["lr"], momentum=0.9, nesterov=True, weight_decay=mspec["wd"])
    else:
        opt = torch.optim.AdamW(model.parameters(), lr=mspec["lr"], weight_decay=mspec["wd"])

    warmup_ep = 3 if (mspec["cos"] and epochs >= 10) else 0
    if mspec["cos"]:
        def lr_lambda(ep):
            if warmup_ep > 0 and ep < warmup_ep:
                return float(ep + 1) / float(warmup_ep)
            prog = (ep - warmup_ep) / max(1, epochs - warmup_ep)
            return 0.5 * (1.0 + math.cos(math.pi * prog))
        sched = torch.optim.lr_scheduler.LambdaLR(opt, lr_lambda)
    else:
        sched = None

    scaler = torch.amp.GradScaler("cuda", enabled=(device.type == "cuda"))
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)

    best_val_acc = -1.0
    best_epoch = 0
    best_state = None
    history = []
    tb_records = []
    t0 = time.time()

    for ep in range(1, epochs + 1):
        model.train()
        tr_loss_sum = 0.0
        tr_n = 0
        perm_ep = torch.randperm(n_tr, generator=gen)
        for i in range(0, n_tr, batch_size):
            idx_b = perm_ep[i : i + batch_size]
            xb = x_tr[idx_b].to(device, non_blocking=True)
            yb = y_tr[idx_b].to(device, non_blocking=True)
            if mspec["aug"] or mspec["cutout"] > 0:
                xb = augment_batch_gpu(xb, mspec["aug"], mspec["cutout"])
            opt.zero_grad(set_to_none=True)
            with torch.amp.autocast("cuda", enabled=(device.type == "cuda")):
                if mspec["mixup"] > 0.0:
                    lam = torch.distributions.Beta(mspec["mixup"], mspec["mixup"]).sample().item()
                    perm_b = torch.randperm(xb.size(0), device=device)
                    xm = lam * xb + (1.0 - lam) * xb[perm_b]
                    logits = model(xm)
                    loss = lam * F.cross_entropy(logits, yb, label_smoothing=mspec["ls"]) + (1.0 - lam) * F.cross_entropy(logits, yb[perm_b], label_smoothing=mspec["ls"])
                else:
                    logits = model(xb)
                    loss = F.cross_entropy(logits, yb, label_smoothing=mspec["ls"])
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            tr_loss_sum += loss.item() * yb.size(0)
            tr_n += yb.size(0)
        if sched is not None:
            sched.step()

        tr_loss = tr_loss_sum / tr_n
        v_logits, v_targets = collect_logits(model, x_val, y_val, device)
        vm = compute_metrics_from_logits(v_logits, v_targets)
        if vm["acc"] > best_val_acc:
            best_val_acc = vm["acc"]
            best_epoch = ep
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

        row = {
            "dataset": ds_name, "method": method, "seed": seed, "epoch": ep,
            "train_loss": round(tr_loss, 6),
            "val_acc": round(vm["acc"], 6), "val_nll": round(vm["nll"], 6), "val_ece": round(vm["ece"], 6),
        }
        history.append(row)
        tb_records.extend([
            (ep, "val_acc", vm["acc"]), (ep, "val_nll", vm["nll"]),
            (ep, "val_ece", vm["ece"]), (ep, "train_loss", tr_loss),
        ])

    # Validation-selected checkpoint: fit temperature T* on val, score held-out test ONCE
    model.load_state_dict(best_state)
    v_logits, v_targets = collect_logits(model, x_val, y_val, device)
    t_star = fit_temperature_on_val(v_logits, v_targets)

    te_logits, te_targets = collect_logits(model, x_te, y_te, device)
    raw_tm = compute_metrics_from_logits(te_logits, te_targets)
    cal_tm = compute_metrics_from_logits(te_logits / t_star, te_targets)
    elapsed = time.time() - t0
    peak_mb = (torch.cuda.max_memory_allocated(device) / (1024 * 1024)) if device.type == "cuda" else 0.0

    tb_records.extend([
        (epochs, "test_acc", raw_tm["acc"]), (epochs, "test_nll", raw_tm["nll"]),
        (epochs, "test_ece", raw_tm["ece"]), (epochs, "cal_nll", cal_tm["nll"]),
        (epochs, "cal_ece", cal_tm["ece"]),
    ])

    # 1. Write TensorBoard binary tfevents
    tb_p = ws / "runs/tb" / ds_name / f"{method}_s{seed}" / f"events.out.tfevents.{ds_name}.{method}.s{seed}"
    pb.write_tfevents_scalars(tb_p, tb_records)

    # 2. Write W&B local run artifacts
    wb_dir = ws / "runs/wandb" / ds_name / f"{method}_s{seed}" / "files"
    wb_dir.mkdir(parents=True, exist_ok=True)
    (wb_dir / "config.json").write_text(json.dumps({
        "dataset": ds_name, "method": method, "seed": seed, "epochs": epochs,
        "batch_size": batch_size, "n_params": n_params, "selected_on": "val_acc",
        "temp_scaling_fit_on": "val_logits", **mspec,
    }, indent=2), encoding="utf-8")
    (wb_dir / "wandb-history.jsonl").write_text("\n".join(json.dumps(r) for r in history) + "\n", encoding="utf-8")

    rec = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": ds_name,
        "method": method,
        "seed": seed,
        "epochs": epochs,
        "n_params": n_params,
        "best_val_epoch": best_epoch,
        "val_acc": round(best_val_acc, 6),
        "test_acc": round(raw_tm["acc"], 6),
        "test_nll": round(raw_tm["nll"], 6),
        "test_ece": round(raw_tm["ece"], 6),
        "test_brier": round(raw_tm["brier"], 6),
        "temp_T": round(t_star, 4),
        "cal_nll": round(cal_tm["nll"], 6),
        "cal_ece": round(cal_tm["ece"], 6),
        "cal_brier": round(cal_tm["brier"], 6),
        "wall_time_s": round(elapsed, 2),
        "peak_vram_mb": round(peak_mb, 1),
        "device": torch.cuda.get_device_name(0) if device.type == "cuda" else "CPU",
        "torch_version": torch.__version__,
    }
    (wb_dir / "wandb-summary.json").write_text(json.dumps({**rec, "_step": epochs}, indent=2), encoding="utf-8")

    # 3. Write CSV epoch log
    csv_p = ws / "runs/csv" / ds_name / f"{method}_s{seed}.csv"
    csv_p.parent.mkdir(parents=True, exist_ok=True)
    with csv_p.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["dataset", "method", "seed", "epoch", "train_loss", "val_acc", "val_nll", "val_ece"])
        w.writeheader()
        w.writerows(history)

    return rec


def update_research_wiki_and_audit(ws: Path, ledger_path: Path, completed_stage: str):
    """Update persistent Research Wiki and run deterministic VeriLoop Layer-1 gates on it."""
    rows = [json.loads(l) for l in ledger_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    by_dm = defaultdict(list)
    for r in rows:
        by_dm[(r["dataset"], r["method"])].append(r)

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ledger_sha = sha256_file(ledger_path)[:16]
    # Write canonical plain-text log from ledger for deterministic tracing
    log_lines = [
        "# VeriLoop Overnight GPU Trajectory Canonical Log",
        f"# updated_utc={now_utc} completed_runs={len(rows)} ledger_sha256={ledger_sha}",
    ]
    wiki_lines = [
        "# VeriLoop Persistent Research Wiki — Overnight Real-GPU Calibration Study",
        "",
        f"- **Last Updated (UTC):** `{now_utc}`",
        f"- **Completed GPU Runs:** `{len(rows)}` (Latest stage: `{completed_stage}`)",
        f"- **Ledger SHA-256:** `{ledger_sha}`",
        "",
        "## Live Multi-Seed Results (`out/wiki_metrics.log`)",
        "",
        "| Dataset | Method | Seeds | Val Acc | Test Acc | Raw ECE | Cal ECE ($T^*$) | Raw NLL | Cal NLL | Mean $T^*$ |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for (ds, meth), items in sorted(by_dm.items()):
        n = len(items)
        def _ms(k):
            vs = [x[k] for x in items]
            return statistics.mean(vs), (statistics.stdev(vs) if len(vs) > 1 else 0.0)
        va_m, va_s = _ms("val_acc")
        ta_m, ta_s = _ms("test_acc")
        re_m, re_s = _ms("test_ece")
        ce_m, ce_s = _ms("cal_ece")
        rn_m, rn_s = _ms("test_nll")
        cn_m, cn_s = _ms("cal_nll")
        t_m, _ = _ms("temp_T")
        log_lines.append(
            f"STAGE {ds:7s} {meth:20s} n={n} | val_acc={va_m:.4f}±{va_s:.4f} test_acc={ta_m:.4f}±{ta_s:.4f} "
            f"raw_ece={re_m:.4f}±{re_s:.4f} cal_ece={ce_m:.4f}±{ce_s:.4f} "
            f"raw_nll={rn_m:.4f}±{rn_s:.4f} cal_nll={cn_m:.4f}±{cn_s:.4f} T={t_m:.4f}"
        )
        wiki_lines.append(
            f"| `{ds}` | `{meth}` | {n} | {va_m:.4f}±{va_s:.4f} | {ta_m:.4f}±{ta_s:.4f} | "
            f"{re_m:.4f}±{re_s:.4f} | {ce_m:.4f}±{ce_s:.4f} | {rn_m:.4f}±{rn_s:.4f} | {cn_m:.4f}±{cn_s:.4f} | {t_m:.4f} |"
        )
    log_lines.append("COMPLETED_OK")
    wiki_log = ws / "out/wiki_metrics.log"
    wiki_log.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    wiki_p = ws / "wiki/RESEARCH_WIKI.md"
    wiki_p.parent.mkdir(parents=True, exist_ok=True)
    wiki_p.write_text("\n".join(wiki_lines) + "\n", encoding="utf-8")

    # Run deterministic Layer-1 gates (trace_numbers + audit_code) at this checkpoint!
    t0 = time.time()
    p_tr = subprocess.run(
        [sys.executable, str(RL_SCRIPTS / "trace_numbers.py"), str(wiki_p), "--logs", str(wiki_log), "--json"],
        capture_output=True, text=True,
    )
    p_ast = subprocess.run(
        [sys.executable, str(RL_SCRIPTS / "audit_code.py"), "--scripts", str(Path(__file__).resolve().parent), "--report", str(wiki_p), "--json", "--strict"],
        capture_output=True, text=True,
    )
    gate_ms = round((time.time() - t0) * 1000.0, 1)
    tr_d = json.loads(p_tr.stdout) if p_tr.stdout.strip().startswith("{") else {}
    ast_d = json.loads(p_ast.stdout) if p_ast.stdout.strip().startswith("{") else {}
    gate_rec = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "stage": completed_stage,
        "completed_runs": len(rows),
        "gate_elapsed_ms": gate_ms,
        "trace_rc": p_tr.returncode,
        "traced": tr_d.get("traced", 0),
        "untraced": len(tr_d.get("untraced", [])),
        "sign_mismatches": len(tr_d.get("sign_mismatches", [])),
        "ast_rc": p_ast.returncode,
        "ast_high": int((ast_d.get("counts") or {}).get("HIGH", 0)),
        "passed": (p_tr.returncode == 0 and p_ast.returncode == 0),
    }
    with (ws / "out/gate_audit_trace.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(gate_rec) + "\n")
    print(
        f"  [VERILOOP_STAGE_GATE] stage={completed_stage} passed={gate_rec['passed']} "
        f"traced={gate_rec['traced']} untraced={gate_rec['untraced']} ast_high={gate_rec['ast_high']} ({gate_ms}ms)",
        flush=True,
    )


def main():
    ap = argparse.ArgumentParser(description="Crash-resumable multi-dataset GPU overnight research suite.")
    ap.add_argument("--ws", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--data-root", default="/tmp")
    ap.add_argument("--datasets", nargs="+", choices=("cifar10", "fmnist"), default=["cifar10", "fmnist"])
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--epochs-override", type=int, default=0, help="Optional override for smoke testing")
    ap.add_argument("--resume", action="store_true", help="Skip (dataset, method, seed) already in trajectory_ledger.jsonl")
    args = ap.parse_args()

    ws = Path(args.ws).resolve()
    (ws / "out").mkdir(parents=True, exist_ok=True)
    ledger_path = ws / "out/trajectory_ledger.jsonl"

    done_keys = set()
    if args.resume and ledger_path.is_file():
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                done_keys.add((r["dataset"], r["method"], int(r["seed"])))

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    gpu_name = torch.cuda.get_device_name(0) if device.type == "cuda" else "CPU"
    print(f"OVERNIGHT_GPU_STUDY START | device={device} ({gpu_name}) | torch={torch.__version__} | resumed={len(done_keys)}", flush=True)

    total_runs = sum(len(DATASET_SPECS[d]["methods"]) * len(args.seeds) for d in args.datasets)
    idx = 0
    for ds_name in args.datasets:
        dspec = DATASET_SPECS[ds_name]
        epochs = args.epochs_override if args.epochs_override > 0 else dspec["epochs"]
        splits = load_normalized_tensors(ds_name, Path(args.data_root))
        for method in dspec["methods"]:
            stage_ran = False
            for seed in args.seeds:
                idx += 1
                if (ds_name, method, seed) in done_keys:
                    print(f"[{idx}/{total_runs}] SKIP (resumed) {ds_name}/{method}/s{seed}", flush=True)
                    continue
                rec = run_single(ds_name, method, seed, epochs, args.batch_size, splits, device, ws)
                with ledger_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec) + "\n")
                    fh.flush()
                stage_ran = True
                print(
                    f"[{idx}/{total_runs}] {ds_name:7s} {method:20s} s={seed} | "
                    f"val={rec['val_acc']:.4f} test={rec['test_acc']:.4f} "
                    f"raw_ece={rec['test_ece']:.4f} -> cal_ece={rec['cal_ece']:.4f} (T={rec['temp_T']:.2f}) | "
                    f"{rec['wall_time_s']:.1f}s {rec['peak_vram_mb']:.0f}MB",
                    flush=True,
                )
            if stage_ran or not (ws / "wiki/RESEARCH_WIKI.md").is_file():
                update_research_wiki_and_audit(ws, ledger_path, f"{ds_name}::{method}")

    print(f"OVERNIGHT_GPU_STUDY COMPLETE | total_planned={total_runs} | ledger={ledger_path}", flush=True)


if __name__ == "__main__":
    main()
