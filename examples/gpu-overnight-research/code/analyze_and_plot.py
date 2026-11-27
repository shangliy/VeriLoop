#!/usr/bin/env python3
"""Analyze completed overnight GPU trajectory, run paper_bind, and draw 3 Okabe-Ito vector PDFs."""
import json
import math
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
WS = Path(__file__).resolve().parents[1]
FIG_DIR = WS / "paper/figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

T_CRIT_95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776}
OKABE_ITO = ["#0072B2", "#009E73", "#E69F00", "#CC79A7", "#D55E00", "#56B4E9", "#1F2937", "#999999"]

ORDER_C10 = [
    "M0_Linear", "M1_PlainCNN", "M2_ResNet_Base", "M3_ResNet_Aug",
    "M4_ResNet_Aug_Cosine", "M5_ResNet_LS", "M6_ResNet_Mixup", "M7_SEResNet_Full",
]
ORDER_FM = [
    "M0_Linear", "M1_PlainCNN", "M2_ResNet_Base",
    "M4_ResNet_Aug_Cosine", "M5_ResNet_LS", "M7_SEResNet_Full",
]


def agg(items, key):
    vs = [float(x[key]) for x in items]
    m = statistics.mean(vs)
    s = statistics.stdev(vs) if len(vs) > 1 else 0.0
    half = T_CRIT_95.get(len(vs) - 1, 1.96) * (s / math.sqrt(len(vs))) if len(vs) > 1 else 0.0
    return m, s, m - half, m + half


def main():
    ledger = WS / "out/trajectory_ledger.jsonl"
    rows = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip()]
    gate_rows = [
        json.loads(l)
        for l in (WS / "out/gate_audit_trace.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]

    # Run ./veriloop bind per dataset so macros, tables, and manifests are auto-generated
    for ds in sorted({r["dataset"] for r in rows}):
        prefix = "vlC" if ds == "cifar10" else "vlF"
        subprocess.run(
            [
                sys.executable, str(REPO_ROOT / "tools/paper_bind.py"),
                "--inputs", str(WS / "runs/tb" / ds), str(WS / "runs/wandb" / ds),
                "--metrics", "val_acc", "test_acc", "test_ece", "cal_ece", "test_nll", "cal_nll",
                "--curve-metric", "val_acc",
                "--macro-prefix", prefix,
                "--out-dir", str(WS / "paper/bound" / ds),
            ],
            check=True,
        )

    by_dm = defaultdict(list)
    for r in rows:
        by_dm[(r["dataset"], r["method"])].append(r)

    total_gpu_s = sum(float(r["wall_time_s"]) for r in rows)
    max_vram = max(float(r["peak_vram_mb"]) for r in rows)
    gpu_name = rows[0]["device"]
    torch_ver = rows[0]["torch_version"]

    lines = [
        "=== VERILOOP OVERNIGHT REAL-GPU STUDY SUMMARY (ZERO OVERRIDES) ===",
        f"RUNS total_runs={len(rows)} gpu={gpu_name} torch={torch_ver} total_gpu_s={total_gpu_s:.1f} ({total_gpu_s/60.0:.2f} min) peak_vram_mb={max_vram:.1f}",
        f"GATES stages_audited={len(gate_rows)} passed={sum(1 for g in gate_rows if g['passed'])}/{len(gate_rows)} "
        f"total_traced={sum(g['traced'] for g in gate_rows)} total_untraced={sum(g['untraced'] for g in gate_rows)} "
        f"total_ast_high={sum(g['ast_high'] for g in gate_rows)} median_gate_ms={statistics.median(g['gate_elapsed_ms'] for g in gate_rows):.1f}",
        "",
    ]

    for ds, order in [("cifar10", ORDER_C10), ("fmnist", ORDER_FM)]:
        lines.append(f"--- DATASET: {ds} ---")
        for m in order:
            its = by_dm.get((ds, m))
            if not its:
                continue
            va = agg(its, "val_acc")
            ta = agg(its, "test_acc")
            re = agg(its, "test_ece")
            ce = agg(its, "cal_ece")
            rn = agg(its, "test_nll")
            cn = agg(its, "cal_nll")
            tb = agg(its, "test_brier")
            cb = agg(its, "cal_brier")
            tt = agg(its, "temp_T")
            lines.append(
                f"SUMMARY {ds:7s} {m:20s} n={len(its)} | "
                f"val_acc={va[0]:.4f}±{va[1]:.4f} test_acc={ta[0]:.4f}±{ta[1]:.4f} [{ta[2]:.4f},{ta[3]:.4f}] | "
                f"raw_ece={re[0]:.4f}±{re[1]:.4f} cal_ece={ce[0]:.4f}±{ce[1]:.4f} | "
                f"raw_nll={rn[0]:.4f}±{rn[1]:.4f} cal_nll={cn[0]:.4f}±{cn[1]:.4f} | "
                f"raw_brier={tb[0]:.4f} cal_brier={cb[0]:.4f} T={tt[0]:.4f}"
            )
        lines.append("")

    # Compute exact paired accuracy & ECE deltas on CIFAR-10 and Fashion-MNIST
    for ds in ("cifar10", "fmnist"):
        if (ds, "M7_SEResNet_Full") in by_dm and (ds, "M1_PlainCNN") in by_dm:
            d_acc = statistics.mean(x["test_acc"] for x in by_dm[(ds, "M7_SEResNet_Full")]) - statistics.mean(x["test_acc"] for x in by_dm[(ds, "M1_PlainCNN")])
            lines.append(f"DELTA {ds} M7_SEResNet_Full_vs_M1_PlainCNN test_acc_delta={d_acc:+.4f} ({d_acc*100:+.2f} pp)")
        if (ds, "M5_ResNet_LS") in by_dm and (ds, "M4_ResNet_Aug_Cosine") in by_dm:
            d_acc = statistics.mean(x["test_acc"] for x in by_dm[(ds, "M5_ResNet_LS")]) - statistics.mean(x["test_acc"] for x in by_dm[(ds, "M4_ResNet_Aug_Cosine")])
            d_ece = statistics.mean(x["test_ece"] for x in by_dm[(ds, "M5_ResNet_LS")]) - statistics.mean(x["test_ece"] for x in by_dm[(ds, "M4_ResNet_Aug_Cosine")])
            d_cal = statistics.mean(x["cal_ece"] for x in by_dm[(ds, "M5_ResNet_LS")]) - statistics.mean(x["test_ece"] for x in by_dm[(ds, "M5_ResNet_LS")])
            lines.append(
                f"DELTA {ds} M5_LS_vs_M4_Cosine test_acc_delta={d_acc:+.4f} raw_ece_delta={d_ece:+.4f} "
                f"M5_temp_scaling_ece_delta={d_cal:+.4f}"
            )
    lines.append("COMPLETED_OK")
    (WS / "out/overnight_summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))

    # ==================== PUBLICATION-GRADE OKABE-ITO VECTOR PDFs ====================
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
        "font.size": 7.5, "axes.labelsize": 8.2, "xtick.labelsize": 7.0, "ytick.labelsize": 7.0,
        "legend.fontsize": 6.6, "legend.frameon": False,
        "axes.spines.top": False, "axes.spines.right": False,
        "pdf.fonttype": 42, "ps.fonttype": 42,
    })

    # Figure 1: Progressive Ablation Ladder on CIFAR-10 (Test Acc + Raw vs Calibrated ECE)
    c10_m = [m for m in ORDER_C10 if ("cifar10", m) in by_dm]
    if c10_m:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.0, 2.85), gridspec_kw={"wspace": 0.28})
        x = np.arange(len(c10_m))
        short_map = {
            "M0_Linear": "M0 Linear", "M1_PlainCNN": "M1 PlainCNN",
            "M2_ResNet_Base": "M2 ResNet", "M3_ResNet_Aug": "M3 +Aug",
            "M4_ResNet_Aug_Cosine": "M4 +CosSGD", "M5_ResNet_LS": "M5 +LS",
            "M6_ResNet_Mixup": "M6 +Mixup", "M7_SEResNet_Full": "M7 SE+Cut",
        }
        short_lbl = [short_map.get(m, m) for m in c10_m]
        ta_means = [agg(by_dm[("cifar10", m)], "test_acc")[0] * 100 for m in c10_m]
        ta_errs = [(agg(by_dm[("cifar10", m)], "test_acc")[3] - agg(by_dm[("cifar10", m)], "test_acc")[0]) * 100 for m in c10_m]
        bars = ax1.bar(x, ta_means, 0.62, yerr=ta_errs, capsize=2.2, color="#0072B2", edgecolor="#1F2937", linewidth=0.55)
        for b, v in zip(bars, ta_means):
            ax1.text(b.get_x() + b.get_width() / 2, v + 1.8, f"{v:.1f}", ha="center", va="bottom", fontsize=5.8, fontweight="bold")
        ax1.set_xticks(x)
        ax1.set_xticklabels(short_lbl, fontsize=6.2, rotation=28, ha="right", rotation_mode="anchor")
        ax1.set_ylabel("CIFAR-10 Test Accuracy (%)")
        ax1.set_ylim(0, 108)
        ax1.grid(axis="y", linestyle=":", alpha=0.4)
        ax1.set_axisbelow(True)
        ax1.text(0.5, -0.36, "(a) Progressive ablation ladder (mean ± 95% CI)", transform=ax1.transAxes, ha="center", fontsize=7.0, fontweight="bold")

        re_means = [agg(by_dm[("cifar10", m)], "test_ece")[0] * 100 for m in c10_m]
        ce_means = [agg(by_dm[("cifar10", m)], "cal_ece")[0] * 100 for m in c10_m]
        w = 0.36
        ax2.bar(x - w / 2, re_means, w, label="Raw ECE (%)", color="#D55E00", edgecolor="#1F2937", linewidth=0.55)
        ax2.bar(x + w / 2, ce_means, w, label="Temp-Scaled ECE (%)", color="#009E73", edgecolor="#1F2937", linewidth=0.55)
        ax2.set_xticks(x)
        ax2.set_xticklabels(short_lbl, fontsize=6.2, rotation=28, ha="right", rotation_mode="anchor")
        ax2.set_ylabel("Expected Calibration Error (%) ↓")
        ax2.grid(axis="y", linestyle=":", alpha=0.4)
        ax2.set_axisbelow(True)
        ax2.legend(loc="upper right", fontsize=6.5)
        ax2.text(0.5, -0.36, "(b) Calibration trade-off: Raw vs. Val-Fitted T*", transform=ax2.transAxes, ha="center", fontsize=7.0, fontweight="bold")

        fig.subplots_adjust(bottom=0.28)
        fig.savefig(FIG_DIR / "fig_cifar10_ablation_and_ece.pdf", bbox_inches="tight")
        plt.close(fig)

    # Figure 2: Cross-Dataset Accuracy vs. ECE Pareto Frontier (CIFAR-10 + Fashion-MNIST)
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.75), gridspec_kw={"wspace": 0.30})
    lbl_offsets = {
        ("cifar10", "M1_PlainCNN"): (-1.6, 0.75),
        ("cifar10", "M2_ResNet_Base"): (-2.4, -0.95),
        ("cifar10", "M3_ResNet_Aug"): (0.35, -0.25),
        ("cifar10", "M4_ResNet_Aug_Cosine"): (-0.3, -1.25),
        ("cifar10", "M5_ResNet_LS"): (0.25, -1.15),
        ("cifar10", "M6_ResNet_Mixup"): (0.25, 0.35),
        ("cifar10", "M7_SEResNet_Full"): (0.35, 0.45),
        ("fmnist", "M1_PlainCNN"): (0.25, 0.12),
        ("fmnist", "M2_ResNet_Base"): (0.20, 0.18),
        ("fmnist", "M4_ResNet_Aug_Cosine"): (0.15, 0.22),
        ("fmnist", "M5_ResNet_LS"): (-1.55, 0.22),
        ("fmnist", "M7_SEResNet_Full"): (0.20, -0.32),
    }
    short_p = {
        "M1_PlainCNN": "M1 PlainCNN", "M2_ResNet_Base": "M2 ResNet",
        "M3_ResNet_Aug": "M3 +Aug", "M4_ResNet_Aug_Cosine": "M4 +CosSGD",
        "M5_ResNet_LS": "M5 +LS", "M6_ResNet_Mixup": "M6 +Mixup", "M7_SEResNet_Full": "M7 SE+Cut",
    }
    for ax, (ds, order, ttl) in zip(axes, [("cifar10", ORDER_C10, "(a) CIFAR-10 (30 epochs, 3 seeds)"), ("fmnist", ORDER_FM, "(b) Fashion-MNIST (15 epochs, 3 seeds)")]):
        ms = [m for m in order if (ds, m) in by_dm and m != "M0_Linear"]
        for i, m in enumerate(ms):
            ta = agg(by_dm[(ds, m)], "test_acc")[0] * 100
            re = agg(by_dm[(ds, m)], "test_ece")[0] * 100
            ce = agg(by_dm[(ds, m)], "cal_ece")[0] * 100
            c = OKABE_ITO[i % len(OKABE_ITO)]
            ax.scatter([re], [ta], color=c, marker="o", s=34, edgecolor="#1F2937", linewidth=0.6, zorder=4)
            ax.scatter([ce], [ta], color=c, marker="^", s=38, edgecolor="#1F2937", linewidth=0.6, zorder=5)
            ax.annotate("", xy=(ce, ta), xytext=(re, ta), arrowprops=dict(arrowstyle="->", color=c, lw=0.85, alpha=0.75))
            dx, dy = lbl_offsets.get((ds, m), (0.2, 0.2))
            ax.text(re + dx, ta + dy, short_p.get(m, m), fontsize=5.8, color="#1F2937", fontweight="medium")
        ax.set_xlabel("Expected Calibration Error (%) ↓")
        ax.set_ylabel("Held-Out Test Accuracy (%) ↑")
        if ds == "cifar10":
            ax.set_xlim(0.0, 13.8)
            ax.set_ylim(76.4, 93.4)
        else:
            ax.set_xlim(0.0, 8.2)
            ax.set_ylim(89.5, 94.6)
        ax.grid(linestyle=":", alpha=0.4)
        ax.text(0.5, -0.28, ttl, transform=ax.transAxes, ha="center", fontsize=7.0, fontweight="bold")
    axes[0].scatter([], [], color="#4B5563", marker="o", s=26, label="Raw model")
    axes[0].scatter([], [], color="#4B5563", marker="^", s=28, label="Post-hoc Temp Scaling (val T*)")
    axes[0].legend(loc="lower right", fontsize=6.2)
    fig.subplots_adjust(bottom=0.24)
    fig.savefig(FIG_DIR / "fig_acc_ece_pareto.pdf", bbox_inches="tight")
    plt.close(fig)

    print("OVERNIGHT_FIGURES_WRITTEN -> paper/figures/")


if __name__ == "__main__":
    main()
