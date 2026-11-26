#!/usr/bin/env python3
"""Real Multi-Seed GPU Deep Learning Benchmark for VeriLoop End-to-End Showcase.

Trains 4 PyTorch architectures across 3 independent random seeds (12 runs total)
on Fashion-MNIST with strict train (50k) / val (10k) / held-out test (10k) separation:
  1. MLP_Baseline  : 2-hidden-layer MLP (non-convolutional baseline)
  2. PlainCNN      : 3-stage ConvNet without residual skips or cosine annealing
  3. ResCNN_NoReg  : Residual ConvNet + BatchNorm (ablation: no dropout, no label smoothing, constant LR)
  4. ResCNN_Full   : Residual ConvNet + BatchNorm + Dropout(0.2) + LabelSmoothing(0.1) + CosineAnnealingLR

Model checkpoint selection uses validation accuracy ONLY; the held-out test split is
scored strictly once on the validation-selected checkpoint.

Simultaneously emits three industry-standard log formats for `./veriloop bind`:
  - TensorBoard binary event files (`runs/tb/<method>_s<seed>/events.out.tfevents.*`)
  - Weights & Biases local run files (`runs/wandb/<method>_s<seed>/files/wandb-{summary.json,history.jsonl}`)
  - Per-epoch CSV logs (`runs/csv/<method>_s<seed>.csv`) and canonical stdout (`out/gpu_runs.log`)
"""
import argparse
import csv
import json
import math
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, transforms

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "tools"))
import paper_bind as pb  # noqa: E402


def seed_everything(seed: int):
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


class MLPBaseline(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Flatten(),
            nn.Linear(28 * 28, 256),
            nn.ReLU(inplace=True),
            nn.Linear(256, 128),
            nn.ReLU(inplace=True),
            nn.Linear(128, 10),
        )

    def forward(self, x):
        return self.net(x)


class PlainCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 32, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(64, 128, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d(1),
        )
        self.head = nn.Linear(128, 10)

    def forward(self, x):
        return self.head(self.features(x).flatten(1))


class ResBlock(nn.Module):
    def __init__(self, in_ch: int, out_ch: int, stride: int = 1):
        super().__init__()
        self.conv1 = nn.Conv2d(in_ch, out_ch, 3, stride=stride, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(out_ch)
        self.conv2 = nn.Conv2d(out_ch, out_ch, 3, stride=1, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(out_ch)
        self.skip = (
            nn.Sequential(nn.Conv2d(in_ch, out_ch, 1, stride=stride, bias=False), nn.BatchNorm2d(out_ch))
            if (stride != 1 or in_ch != out_ch)
            else nn.Identity()
        )

    def forward(self, x):
        h = F.relu(self.bn1(self.conv1(x)), inplace=True)
        h = self.bn2(self.conv2(h))
        return F.relu(h + self.skip(x), inplace=True)


class ResCNN(nn.Module):
    def __init__(self, dropout: float = 0.0):
        super().__init__()
        self.stem = nn.Sequential(nn.Conv2d(1, 32, 3, padding=1, bias=False), nn.BatchNorm2d(32), nn.ReLU(inplace=True))
        self.b1 = ResBlock(32, 32, stride=1)
        self.b2 = ResBlock(32, 64, stride=2)
        self.b3 = ResBlock(64, 128, stride=2)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.drop = nn.Dropout(dropout)
        self.head = nn.Linear(128, 10)

    def forward(self, x):
        h = self.b3(self.b2(self.b1(self.stem(x))))
        h = self.drop(self.pool(h).flatten(1))
        return self.head(h)


def build_model(method: str) -> nn.Module:
    if method == "MLP_Baseline":
        return MLPBaseline()
    if method == "PlainCNN":
        return PlainCNN()
    if method == "ResCNN_NoReg":
        return ResCNN(dropout=0.0)
    if method == "ResCNN_Full":
        return ResCNN(dropout=0.2)
    raise ValueError(f"Unknown method: {method}")


@torch.no_grad()
def evaluate_split(model: nn.Module, loader: DataLoader, device: torch.device) -> tuple[float, float]:
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0
    for xb, yb in loader:
        xb, yb = xb.to(device, non_blocking=True), yb.to(device, non_blocking=True)
        logits = model(xb)
        total_loss += F.cross_entropy(logits, yb, reduction="sum").item()
        correct += (logits.argmax(dim=1) == yb).sum().item()
        total += yb.size(0)
    return correct / total, total_loss / total


def train_one(method: str, seed: int, epochs: int, batch_size: int, train_ds, val_ds, test_ds, device: torch.device, out_root: Path):
    seed_everything(seed)
    gen = torch.Generator().manual_seed(seed)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, generator=gen, num_workers=2, pin_memory=(device.type == "cuda"))
    val_loader = DataLoader(val_ds, batch_size=512, shuffle=False, num_workers=2, pin_memory=(device.type == "cuda"))
    test_loader = DataLoader(test_ds, batch_size=512, shuffle=False, num_workers=2, pin_memory=(device.type == "cuda"))

    model = build_model(method).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    lr = 1.5e-3 if method != "MLP_Baseline" else 2.0e-3
    wd = 1e-4 if method == "ResCNN_Full" else 0.0
    label_smooth = 0.1 if method == "ResCNN_Full" else 0.0
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=wd)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs) if method == "ResCNN_Full" else None

    best_val_acc = -1.0
    best_epoch = 0
    best_state = None
    history = []
    tb_records = []
    t0 = time.time()

    for ep in range(1, epochs + 1):
        model.train()
        tr_loss_sum = 0.0
        tr_correct = 0
        tr_n = 0
        for xb, yb in train_loader:
            xb, yb = xb.to(device, non_blocking=True), yb.to(device, non_blocking=True)
            opt.zero_grad(set_to_none=True)
            logits = model(xb)
            loss = F.cross_entropy(logits, yb, label_smoothing=label_smooth)
            loss.backward()
            opt.step()
            tr_loss_sum += loss.item() * yb.size(0)
            tr_correct += (logits.argmax(dim=1) == yb).sum().item()
            tr_n += yb.size(0)
        if sched is not None:
            sched.step()

        tr_acc = tr_correct / tr_n
        tr_loss = tr_loss_sum / tr_n
        val_acc, val_loss = evaluate_split(model, val_loader, device)
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_epoch = ep
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

        row = {
            "method": method, "seed": seed, "epoch": ep,
            "train_acc": round(tr_acc, 6), "train_loss": round(tr_loss, 6),
            "val_acc": round(val_acc, 6), "val_loss": round(val_loss, 6),
        }
        history.append(row)
        tb_records.append((ep, "val_acc", val_acc))
        tb_records.append((ep, "val_loss", val_loss))
        tb_records.append((ep, "train_loss", tr_loss))

    # Strict validation-only selection: score held-out test set ONCE using best_val_acc checkpoint
    model.load_state_dict(best_state)
    test_acc, test_loss = evaluate_split(model, test_loader, device)
    elapsed = time.time() - t0
    tb_records.append((epochs, "test_acc", test_acc))
    tb_records.append((epochs, "test_loss", test_loss))

    # 1. Write TensorBoard tfevents
    tb_path = out_root / "runs/tb" / f"{method}_s{seed}" / f"events.out.tfevents.{method}.s{seed}"
    pb.write_tfevents_scalars(tb_path, tb_records)

    # 2. Write W&B local run files
    wb_dir = out_root / "runs/wandb" / f"{method}_s{seed}" / "files"
    wb_dir.mkdir(parents=True, exist_ok=True)
    (wb_dir / "config.json").write_text(json.dumps({
        "method": method, "seed": seed, "epochs": epochs, "batch_size": batch_size,
        "lr": lr, "weight_decay": wd, "label_smoothing": label_smooth, "n_params": n_params,
        "selected_on": "val_acc", "device": str(device),
    }, indent=2), encoding="utf-8")
    (wb_dir / "wandb-history.jsonl").write_text(
        "\n".join(json.dumps(r) for r in history) + "\n", encoding="utf-8"
    )
    summary = {
        "method": method, "seed": seed, "_step": epochs,
        "best_val_epoch": best_epoch,
        "best_val_acc": round(best_val_acc, 6),
        "val_acc": round(best_val_acc, 6),
        "test_acc": round(test_acc, 6),
        "test_loss": round(test_loss, 6),
        "wall_time_s": round(elapsed, 2),
        "n_params": n_params,
    }
    (wb_dir / "wandb-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # 3. Write CSV epoch log
    csv_p = out_root / "runs/csv" / f"{method}_s{seed}.csv"
    csv_p.parent.mkdir(parents=True, exist_ok=True)
    with csv_p.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["method", "seed", "epoch", "train_acc", "train_loss", "val_acc", "val_loss"])
        w.writeheader()
        w.writerows(history)

    return summary


def main():
    ap = argparse.ArgumentParser(description="Run real multi-seed PyTorch GPU benchmark on Fashion-MNIST.")
    ap.add_argument("--out-root", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--data-dir", default="/tmp/veriloop_fmnist_data")
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    args = ap.parse_args()

    out_root = Path(args.out_root).resolve()
    (out_root / "out").mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    gpu_name = torch.cuda.get_device_name(0) if device.type == "cuda" else "CPU"

    tf = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.2860,), (0.3530,))])
    full_train = datasets.FashionMNIST(args.data_dir, train=True, download=True, transform=tf)
    test_ds = datasets.FashionMNIST(args.data_dir, train=False, download=True, transform=tf)

    # Fixed 50,000 train / 10,000 validation split (seed 0) shared across all models
    perm = torch.randperm(len(full_train), generator=torch.Generator().manual_seed(0)).tolist()
    train_ds = Subset(full_train, perm[:50000])
    val_ds = Subset(full_train, perm[50000:])

    methods = ["MLP_Baseline", "PlainCNN", "ResCNN_NoReg", "ResCNN_Full"]
    log_lines = [
        f"# VeriLoop Real GPU Deep Learning Showcase — Fashion-MNIST (50k train / 10k val / 10k test)",
        f"# timestamp_utc={datetime.now(timezone.utc).isoformat()} device={device} gpu={gpu_name} torch={torch.__version__} epochs={args.epochs}",
    ]
    print(log_lines[0], flush=True)
    print(log_lines[1], flush=True)

    for method in methods:
        for seed in args.seeds:
            res = train_one(method, seed, args.epochs, args.batch_size, train_ds, val_ds, test_ds, device, out_root)
            line = (
                f"RUN method={method:14s} seed={seed} params={res['n_params']:7d} best_ep={res['best_val_epoch']} "
                f"val_acc={res['val_acc']:.4f} test_acc={res['test_acc']:.4f} test_loss={res['test_loss']:.4f} "
                f"wall_s={res['wall_time_s']:.2f}"
            )
            log_lines.append(line)
            print(line, flush=True)

    log_lines.append("COMPLETED_OK")
    (out_root / "out/gpu_runs.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    print("GPU_BENCHMARK_DONE -> out/gpu_runs.log", flush=True)


if __name__ == "__main__":
    main()
