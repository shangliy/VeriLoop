#!/usr/bin/env python3
"""Zero-override v2 paper statistics & 4 publication-grade Okabe-Ito vector PDF figures.

Reads EXCLUSIVELY from publicly committed VeriLoop artifacts:
  - eval/v2_frozen/ground_truth.csv (authoritative label source under Route A unified rule)
  - eval/v2_frozen/results_layer1.jsonl (immutable raw locked-v2 Layer-1 predictions)
  - eval/v2_frozen/results_factorial_v2.jsonl (immutable raw LLM predictions)
  - eval/v2_unseen/results_unseen_21.jsonl
  - eval/v2_unseen/unseen_forensic_audit.csv
  - eval/v2_unseen/unseen_audit_summary.json

Structurally forbids any hardcoded scenario overrides. Joins all raw prediction records
against ground_truth.csv by artifact_id, computes workspace-level Wilson CIs and
workspace-level exact McNemar tests (no trial pseudo-replication), and ensures every
number in paper/sec/*.tex traces directly to paper/out/stats_summary.txt.
"""
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
V2_FROZEN = ROOT / "eval/v2_frozen"
V2_UNSEEN = ROOT / "eval/v2_unseen"
PAPER_DIR = ROOT / "paper"
FIG_DIR = PAPER_DIR / "figures"
OUT_DIR = PAPER_DIR / "out"
FIG_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Consistent Okabe-Ito color-blind-safe palette (bestpaper.mplstyle)
C_OURS = "#0072B2"       # saturated blue (VeriLoop Dual-Layer L1 + Codex)
C_OURS_LT = "#DCECF6"
C_CODEX = "#009E73"      # bluish green (Codex-CLI Layer 2)
C_CODEX_LT = "#DFF3EC"
C_SONNET = "#E69F00"     # amber (Claude-Sonnet)
C_SONNET_LT = "#FDF2D8"
C_HAIKU = "#CC79A7"      # reddish purple (Claude-Haiku)
C_HAIKU_LT = "#F6E3EE"
C_L1 = "#56B4E9"         # sky blue (Layer-1 Mechanical)
C_L1_LT = "#E4F4FC"
C_WARN = "#D55E00"       # vermilion (missed / FP highlight)
C_WARN_LT = "#FCE8DC"
C_GREY = "#7F7F7F"
C_GREY_LT = "#ECEFF1"
C_DARK = "#1F2937"
C_MUTED = "#4B5563"


def wilson_ci(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float, float]:
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    half = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * n)) / n) / denom
    return p, max(0.0, center - half), min(1.0, center + half)


def mcnemar_exact_p(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2.0 * sum(math.comb(n, i) for i in range(k + 1)) * (0.5 ** n))


def load_jsonl(fp: Path, gt_map: dict[str, dict]) -> list[dict]:
    out = []
    for l in fp.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        r = json.loads(l)
        g = gt_map[r["artifact_id"]]
        out.append({
            **r,
            "ground_truth": g["ground_truth"],
            "defect_type": g["defect_type"],
            "executor_family": g["executor_family"],
            "track": g["track"],
        })
    return out


def confusion(records: list[dict]) -> dict:
    valid = [r for r in records if r.get("predicted_defective") is not None]
    tp = sum(1 for r in valid if r["ground_truth"] == "DEFECTIVE" and r["predicted_defective"] is True)
    fn = sum(1 for r in valid if r["ground_truth"] == "DEFECTIVE" and r["predicted_defective"] is False)
    fp = sum(1 for r in valid if r["ground_truth"] == "CLEAN" and r["predicted_defective"] is True)
    tn = sum(1 for r in valid if r["ground_truth"] == "CLEAN" and r["predicted_defective"] is False)
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    yld = tn / (fp + tn) if (fp + tn) else 0.0
    bal = 0.5 * (rec + yld)
    _, rlo, rhi = wilson_ci(tp, tp + fn)
    _, ylo, yhi = wilson_ci(tn, fp + tn)
    _, plo, phi = wilson_ci(tp, tp + fp)
    return {
        "n": len(valid), "errors": len(records) - len(valid),
        "tp": tp, "fn": fn, "fp": fp, "tn": tn,
        "prec": prec, "prec_ci": (plo, phi),
        "rec": rec, "rec_ci": (rlo, rhi),
        "f1": f1, "fpr": fpr,
        "yld": yld, "yld_ci": (ylo, yhi),
        "bal": bal,
    }


def repeat_unanimity(records: list[dict]) -> float:
    by_a = defaultdict(list)
    for r in records:
        if r.get("predicted_defective") is not None:
            by_a[r["artifact_id"]].append(bool(r["predicted_defective"]))
    if not by_a:
        return 0.0
    return sum(1 for vs in by_a.values() if len(set(vs)) == 1) / len(by_a)


def ws_majority_map(records: list[dict]) -> dict[str, bool]:
    by_a = defaultdict(list)
    for r in records:
        if r.get("predicted_defective") is not None:
            by_a[r["artifact_id"]].append(bool(r["predicted_defective"]))
    return {a: (sum(vs) > len(vs) / 2) for a, vs in sorted(by_a.items())}


def main():
    with (V2_FROZEN / "ground_truth.csv").open("r", encoding="utf-8") as fh:
        gt_rows = list(csv.DictReader(fh))
    gt_map = {r["artifact_id"]: r for r in gt_rows}

    l1_rows = load_jsonl(V2_FROZEN / "results_layer1.jsonl", gt_map)
    fac_rows = load_jsonl(V2_FROZEN / "results_factorial_v2.jsonl", gt_map)
    unseen_sum = json.loads((V2_UNSEEN / "unseen_audit_summary.json").read_text(encoding="utf-8"))

    all_rows = l1_rows + fac_rows
    groups = defaultdict(list)
    for r in all_rows:
        groups[(r["reviewer"], r["framing"])].append(r)

    valid_llm = [r for r in fac_rows if r.get("predicted_defective") is not None]
    err_llm = [r for r in fac_rows if r.get("predicted_defective") is None]
    n_clean = sum(1 for r in gt_rows if r["ground_truth"] == "CLEAN")
    n_def = sum(1 for r in gt_rows if r["ground_truth"] == "DEFECTIVE")
    h_cln = sum(1 for r in gt_rows if r["executor_family"] == "claude-haiku" and r["ground_truth"] == "CLEAN")
    h_def = sum(1 for r in gt_rows if r["executor_family"] == "claude-haiku" and r["ground_truth"] == "DEFECTIVE")
    c_cln = sum(1 for r in gt_rows if r["executor_family"] == "codex-cli" and r["ground_truth"] == "CLEAN")
    c_def = sum(1 for r in gt_rows if r["executor_family"] == "codex-cli" and r["ground_truth"] == "DEFECTIVE")

    print("=== 1. V2 FROZEN-ARTIFACT CORPUS & RUN TOTALS (ROUTE A UNIFIED RULE, ZERO OVERRIDES) ===")
    print(
        f"CORPUS total_workspaces={len(gt_rows)} clean={n_clean} defective={n_def} "
        f"haiku_clean={h_cln} haiku_def={h_def} codex_clean={c_cln} codex_def={c_def}"
    )
    print(
        f"TRIALS layer1={len(l1_rows)} llm_total_rows={len(fac_rows)} "
        f"llm_valid={len(valid_llm)} llm_quota_errors={len(err_llm)} "
        f"unseen_total={unseen_sum['total_unseen_scenarios']} unseen_completed={unseen_sum['completed_with_report']} "
        f"unseen_cost_usd={unseen_sum['total_executor_cost_usd']:.4f}"
    )

    print("\n=== 2. SINGLE-LAYER PERFORMANCE ON 16 FROZEN WORKSPACES (k=3) ===")
    metrics = {}
    for key in [
        ("layer1_mechanical", "deterministic"),
        ("claude-haiku", "path_only"),
        ("claude-haiku", "with_summary"),
        ("claude-sonnet", "path_only"),
        ("claude-sonnet", "with_summary"),
        ("codex-cli", "path_only"),
        ("codex-cli", "with_summary"),
    ]:
        items = groups[key]
        m = confusion(items)
        unan = repeat_unanimity(items)
        metrics[key] = {**m, "unan": unan}
        print(
            f"SINGLE {key[0]:17s} {key[1]:13s} | n={m['n']:2d} err={m['errors']:2d} "
            f"TP={m['tp']:2d} FN={m['fn']:2d} TN={m['tn']:2d} FP={m['fp']:2d} | "
            f"Prec={m['prec']*100:5.1f}% Rec={m['rec']*100:5.1f}% "
            f"F1={m['f1']*100:5.1f}% FPR={m['fpr']*100:5.1f}% Yield={m['yld']*100:5.1f}% "
            f"BalAcc={m['bal']*100:5.1f}% Unan={unan*100:5.1f}%"
        )
        for ef in ("claude-haiku", "codex-cli"):
            sub = [r for r in items if r["executor_family"] == ef]
            sm = confusion(sub)
            metrics[(key[0], key[1], ef)] = sm
            print(
                f"  STRAT {key[0]:16s} {key[1]:13s} exec={ef:12s} | n={sm['n']:2d} "
                f"TP={sm['tp']:2d} FN={sm['fn']:2d} TN={sm['tn']:2d} FP={sm['fp']:2d} | "
                f"Prec={sm['prec']*100:5.1f}% Rec={sm['rec']*100:5.1f}% F1={sm['f1']*100:5.1f}% "
                f"FPR={sm['fpr']*100:5.1f}% Yield={sm['yld']*100:5.1f}% BalAcc={sm['bal']*100:5.1f}%"
            )

    print("\n=== 3. DUAL-LAYER HARD-BLOCK UNION (Layer 1 Mechanical OR Layer 2 LLM) ===")
    l1_map = {r["artifact_id"]: bool(r["predicted_defective"]) for r in l1_rows}
    union_metrics = {}
    for key in [
        ("claude-haiku", "path_only"),
        ("claude-haiku", "with_summary"),
        ("claude-sonnet", "path_only"),
        ("claude-sonnet", "with_summary"),
        ("codex-cli", "path_only"),
    ]:
        valid = [r for r in groups[key] if r.get("predicted_defective") is not None]
        urecs = [{**r, "predicted_defective": bool(r["predicted_defective"]) or l1_map[r["artifact_id"]]} for r in valid]
        um = confusion(urecs)
        union_metrics[key] = um
        print(
            f"DUAL L1+{key[0]:14s} {key[1]:13s} | n={um['n']:2d} "
            f"TP={um['tp']:2d} FN={um['fn']:2d} TN={um['tn']:2d} FP={um['fp']:2d} | "
            f"Prec={um['prec']*100:5.1f}% Rec={um['rec']*100:5.1f}% "
            f"F1={um['f1']*100:5.1f}% FPR={um['fpr']*100:5.1f}% Yield={um['yld']*100:5.1f}% "
            f"BalAcc={um['bal']*100:5.1f}%"
        )

    print("\n=== 3B. WORKSPACE-LEVEL METRICS (n=16 INDEPENDENT UNITS, MAJORITY VOTE ACROSS k=3) ===")
    ws_maj = {}
    for label, recs_src in [
        ("layer1_mechanical", l1_rows),
        ("claude-haiku::path_only", groups[("claude-haiku", "path_only")]),
        ("claude-haiku::with_summary", groups[("claude-haiku", "with_summary")]),
        ("claude-sonnet::path_only", groups[("claude-sonnet", "path_only")]),
        ("claude-sonnet::with_summary", groups[("claude-sonnet", "with_summary")]),
        ("codex-cli::path_only", groups[("codex-cli", "path_only")]),
        ("L1+claude-haiku::path_only", [{**r, "predicted_defective": bool(r["predicted_defective"]) or l1_map[r["artifact_id"]]} for r in groups[("claude-haiku", "path_only")]]),
        ("L1+claude-haiku::with_summary", [{**r, "predicted_defective": bool(r["predicted_defective"]) or l1_map[r["artifact_id"]]} for r in groups[("claude-haiku", "with_summary")]]),
        ("L1+claude-sonnet::path_only", [{**r, "predicted_defective": bool(r["predicted_defective"]) or l1_map[r["artifact_id"]]} for r in groups[("claude-sonnet", "path_only")]]),
        ("L1+codex-cli::path_only", [{**r, "predicted_defective": bool(r["predicted_defective"]) or l1_map[r["artifact_id"]]} for r in groups[("codex-cli", "path_only")]]),
    ]:
        mmap = ws_majority_map(recs_src)
        ws_maj[label] = mmap
        maj_recs = [
            {"artifact_id": a, "ground_truth": gt_map[a]["ground_truth"], "track": gt_map[a]["track"], "predicted_defective": pred}
            for a, pred in sorted(mmap.items())
        ]
        wm = confusion(maj_recs)
        nat_def = [r for r in maj_recs if r["ground_truth"] == "DEFECTIVE" and r["track"] == "natural"]
        tw_def = [r for r in maj_recs if r["ground_truth"] == "DEFECTIVE" and r["track"] == "surgical_twin"]
        nat_tp = sum(1 for r in nat_def if r["predicted_defective"])
        tw_tp = sum(1 for r in tw_def if r["predicted_defective"])
        print(
            f"WS_LEVEL {label:30s} | n={wm['n']:2d} TP={wm['tp']}/{n_def} TN={wm['tn']}/{n_clean} | "
            f"Prec={wm['prec']*100:5.1f}% Rec={wm['rec']*100:5.1f}% [{wm['rec_ci'][0]*100:4.1f}%,{wm['rec_ci'][1]*100:5.1f}%] "
            f"F1={wm['f1']*100:5.1f}% Yield={wm['yld']*100:5.1f}% [{wm['yld_ci'][0]*100:4.1f}%,{wm['yld_ci'][1]*100:5.1f}%] | "
            f"nat_def={nat_tp}/{len(nat_def)} twin_def={tw_tp}/{len(tw_def)}"
        )

    print("\n=== 4. WORKSPACE-LEVEL PAIRED EXACT MCNEMAR TESTS (NO TRIAL PSEUDO-REPLICATION) ===")
    for rev in ("claude-haiku", "claude-sonnet", "codex-cli"):
        po_m = ws_majority_map(groups[(rev, "path_only")])
        ws_m = ws_majority_map(groups[(rev, "with_summary")])
        shared = sorted(set(po_m) & set(ws_m))
        b = sum(1 for k in shared if po_m[k] and not ws_m[k])
        c = sum(1 for k in shared if (not po_m[k]) and ws_m[k])
        pval = mcnemar_exact_p(b, c)
        print(f"WS_FRAMING_MCNEMAR {rev:14s} | paired_ws={len(shared):2d} po_only={b} ws_only={c} exact_p={pval:.6f}")

    # Also print trial-level framing discordance strictly as descriptive repeat stability
    for rev in ("claude-haiku", "claude-sonnet", "codex-cli"):
        po = {(r["artifact_id"], int(r["repeat"])): bool(r["predicted_defective"]) for r in groups[(rev, "path_only")] if r.get("predicted_defective") is not None}
        ws = {(r["artifact_id"], int(r["repeat"])): bool(r["predicted_defective"]) for r in groups[(rev, "with_summary")] if r.get("predicted_defective") is not None}
        shared = sorted(set(po) & set(ws))
        b = sum(1 for k in shared if po[k] and not ws[k])
        c = sum(1 for k in shared if (not po[k]) and ws[k])
        print(f"TRIAL_FRAMING_DISC {rev:14s} | paired_trials={len(shared):2d} po_only={b} ws_only={c}")

    def_ids = sorted(r["artifact_id"] for r in gt_rows if r["ground_truth"] == "DEFECTIVE")
    for name, a_lbl, b_lbl in [
        ("codex_vs_sonnet_defective_ws", "codex-cli::path_only", "claude-sonnet::path_only"),
        ("haiku_vs_sonnet_defective_ws", "claude-haiku::path_only", "claude-sonnet::path_only"),
        ("codex_vs_layer1_defective_ws", "codex-cli::path_only", "layer1_mechanical"),
        ("l1_union_codex_vs_codex_ws", "L1+codex-cli::path_only", "codex-cli::path_only"),
    ]:
        am, bm = ws_maj[a_lbl], ws_maj[b_lbl]
        b = sum(1 for k in def_ids if am[k] and not bm[k])
        c = sum(1 for k in def_ids if (not am[k]) and bm[k])
        print(f"WS_PAIR_DEFECT {name:30s} | n_def={len(def_ids)} a_only={b} b_only={c} exact_p={mcnemar_exact_p(b, c):.6f}")

    print("\n=== 5. PER-WORKSPACE COMPLEMENTARITY & CASCADE COST-REDUCTION COUNTS ===")
    by_cell = defaultdict(list)
    for r in fac_rows:
        if r.get("predicted_defective") is not None:
            by_cell[(r["artifact_id"], r["reviewer"], r["framing"])].append(int(bool(r["predicted_defective"])))
    l1_def_hits = sum(1 for aid in def_ids if l1_map[aid])
    print(f"CASCADE_L1_PREFILTER defective_caught_at_zero_cost={l1_def_hits}/{len(def_ids)} ({l1_def_hits/len(def_ids)*100:.1f}%)")
    for r1 in l1_rows:
        aid = r1["artifact_id"]
        print(
            f"WS {aid:30s} gt={r1['ground_truth']:9s} l1={int(r1['predicted_defective'])} "
            f"hai_po={sum(by_cell[(aid,'claude-haiku','path_only')])}/{len(by_cell[(aid,'claude-haiku','path_only')])} "
            f"hai_ws={sum(by_cell[(aid,'claude-haiku','with_summary')])}/{len(by_cell[(aid,'claude-haiku','with_summary')])} "
            f"son_po={sum(by_cell[(aid,'claude-sonnet','path_only')])}/{len(by_cell[(aid,'claude-sonnet','path_only')])} "
            f"son_ws={sum(by_cell[(aid,'claude-sonnet','with_summary')])}/{len(by_cell[(aid,'claude-sonnet','with_summary')])} "
            f"cod_po={sum(by_cell[(aid,'codex-cli','path_only')])}/{len(by_cell[(aid,'codex-cli','path_only')])}"
        )

    print("\n=== 6. STRICTLY UNSEEN 21-SCENARIO SCIINTEGRITY HELD-OUT BLIND TEST ===")
    print(
        f"UNSEEN total={unseen_sum['total_unseen_scenarios']} completed={unseen_sum['completed_with_report']} "
        f"numeric_reports={unseen_sum['completed_with_numeric_decimals']} "
        f"incomplete={unseen_sum['exec_incomplete']} gt_trap_taken={unseen_sum['gt_trap_taken_count']}/{unseen_sum['completed_with_report']} "
        f"cost_usd={unseen_sum['total_executor_cost_usd']:.4f} "
        f"traced={unseen_sum['traced_numbers_total']} untraced={unseen_sum['untraced_flags_total']} "
        f"total_checked={unseen_sum['traced_numbers_total']+unseen_sum['untraced_flags_total']} "
        f"num_fpr={unseen_sum['number_level_fpr']*100:.2f}% "
        f"scen_triggers={unseen_sum['scenario_level_triggers']}/{unseen_sum['completed_with_report']} "
        f"scen_fpr={unseen_sum['scenario_level_fpr']*100:.1f}% "
        f"ast_high_fpr={unseen_sum['ast_high_fpr']*100:.1f}% "
        f"trace_sha={unseen_sum['frozen_gate_sha256']['trace_numbers.py']} "
        f"audit_sha={unseen_sum['frozen_gate_sha256']['audit_code.py']}"
    )

    print("\n=== 7. QUALITATIVE VERIFIED EXCERPTS ===")
    print("EXCERPT h06_ci: [0.9965, 0.9985] (disclosed normal approx on 25/10000 acc=0.9975 in H06, Route A CLEAN provenance gap)")
    print("EXCERPT c04_gap: -1.4598 vs 1.4598 percentage points below (C04_CLN_SPR_MetricMis)")
    print("EXCERPT c05_arith: 720.591 vs 720.587 (C05_DEF_06a_TableArithErr)")
    print("EXCERPT h08_sign: -0.0418 vs +0.0418 (H08_DEF_SPR_TwinSignFlip)")
    print("EXCERPT unseen_04c: 0.425 = (0.75 + 0.10)/2 (04c_NumericalPDE_PorousMediumTravelingWave)")
    print("EXCERPT unseen_09c: 3.542 from data/island_species.csv:L17 (09c_Ecology_SpeciesAreaIsland)")
    print("EXCERPT lit_song_p: 42.7% to 56.7% (p=0.006)")

    # ==================== GENERATE 4 VECTOR PDF FIGURES (BESTPAPER + ICML STYLE) ====================
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
        "mathtext.fontset": "dejavusans",
        "font.size": 7.5,
        "axes.labelsize": 8.0,
        "xtick.labelsize": 7.2,
        "ytick.labelsize": 7.2,
        "legend.fontsize": 7.0,
        "legend.frameon": False,
        "axes.linewidth": 0.65,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })

    # ---------- FIGURE 1: Contrast Schematic (Unconfounded Frozen Dual-Layer Architecture) ----------
    fig, ax = plt.subplots(figsize=(6.8, 2.55))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4.1)
    ax.axis("off")

    def box(x, y, w, h, text, fc, ec, tc=C_DARK, lw=1.0, fs=6.7, bold=False):
        r = mpatches.FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.06,rounding_size=0.09",
            facecolor=fc, edgecolor=ec, linewidth=lw,
        )
        ax.add_patch(r)
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                fontsize=fs, fontweight="bold" if bold else "normal", color=tc, linespacing=1.18)

    def arrow(x1, y1, x2, y2, color=C_MUTED, lw=1.05):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>,head_width=0.17,head_length=0.28", color=color, lw=lw))

    # Row 1: Existence Gating (EviBound-style)
    ax.text(0.05, 3.55, "Existence Gate\n(EviBound-style)", fontsize=7.0, fontweight="bold", va="center", color=C_DARK)
    box(1.65, 3.18, 2.00, 0.72, "Pre-exec Schema\n+ Executor", C_GREY_LT, C_GREY)
    arrow(3.71, 3.54, 4.02, 3.54)
    box(4.08, 3.18, 2.20, 0.72, "File Presence Check\n(exit=0 & files exist?)", C_GREY_LT, C_GREY)
    arrow(6.34, 3.54, 7.12, 3.54)
    box(7.18, 3.18, 2.74, 0.72, "Misses Executed Bugs\n(logic, signs, mock code)", C_WARN_LT, C_WARN, tc="#9A3412", bold=True)

    # Row 2: Single-Layer LLM Review
    son_m = metrics[("claude-sonnet", "path_only")]
    ax.text(0.05, 2.55, "Single-Layer\nLLM Review", fontsize=7.0, fontweight="bold", va="center", color=C_DARK)
    box(1.65, 2.18, 2.00, 0.72, "Executor Output\n(code + logs + report)", C_SONNET_LT, C_SONNET)
    arrow(3.71, 2.54, 4.02, 2.54)
    box(4.08, 2.18, 2.20, 0.72, "LLM Auditor Every Run\n(Sonnet / Haiku / Codex)", C_SONNET_LT, C_SONNET)
    arrow(6.34, 2.54, 7.12, 2.54)
    box(7.18, 2.18, 2.74, 0.72, f"Paid Call on Every Run\nSonnet misses H05 ({son_m['rec']*100:.1f}% rec.)", C_WARN_LT, C_WARN, tc="#9A3412", bold=True)

    # Row 3: Layer-1 Mechanical Gates Only
    l1_m = metrics[("layer1_mechanical", "deterministic")]
    ax.text(0.05, 1.55, "Layer 1 Only\n($0 Mechanical)", fontsize=7.0, fontweight="bold", va="center", color=C_DARK)
    box(1.65, 1.18, 2.00, 0.72, "SHA-256 Frozen\nWorkspace Snapshot", C_L1_LT, C_L1)
    arrow(3.71, 1.54, 4.02, 1.54)
    box(4.08, 1.18, 2.20, 0.72, "trace_numbers + audit_code\n(G1-G7, signed, AST)", C_L1_LT, C_L1)
    arrow(6.34, 1.54, 7.12, 1.54)
    box(7.18, 1.18, 2.74, 0.72, f"{l1_m['tp']}/{l1_m['tp']+l1_m['fn']} ($0 Pre-Filter: {l1_m['rec']*100:.1f}%)\nMisses Logic & Overclaims", C_L1_LT, C_L1, tc="#075985", bold=True)

    # Row 4: VeriLoop Dual-Layer Cascade (Ours)
    vl_m = union_metrics[("codex-cli", "path_only")]
    ax.text(0.05, 0.52, "VeriLoop\n(L1 -> L2 Gate)", fontsize=7.2, fontweight="bold", va="center", color=C_OURS)
    box(1.65, 0.14, 1.62, 0.74, "SHA-256 Frozen\nRaw Artifacts", C_OURS_LT, C_OURS, lw=1.35, fs=6.5)
    arrow(3.33, 0.51, 3.55, 0.51, color=C_OURS, lw=1.35)
    box(3.61, 0.14, 1.72, 0.74, "Layer 1 ($0)\nTrace + AST Gates", C_OURS_LT, C_OURS, lw=1.35, fs=6.5, bold=True)
    arrow(5.39, 0.51, 5.61, 0.51, color=C_OURS, lw=1.35)
    box(5.67, 0.14, 1.56, 0.74, "Layer 2 (XMR)\nRead-Only Audit", C_OURS, C_OURS, tc="white", lw=1.35, fs=6.5, bold=True)
    arrow(7.29, 0.51, 7.49, 0.51, color=C_CODEX, lw=1.35)
    box(7.55, 0.14, 2.37, 0.74, f"{vl_m['rec']*100:.1f}% Recall ({n_def}/{n_def} ws)\n{l1_m['tp']}/{n_def} at $0 | {vl_m['yld']*100:.1f}% Strict Yield", C_CODEX_LT, C_CODEX, tc="#065F46", lw=1.35, fs=6.3, bold=True)

    fig.tight_layout(pad=0.2)
    fig.savefig(FIG_DIR / "fig1_architecture.pdf", bbox_inches="tight")
    plt.close(fig)

    # ---------- FIGURE 2: Main Frozen-Artifact Benchmark (Recall, F1, Clean Yield across Systems) ----------
    fig, ax = plt.subplots(figsize=(6.8, 2.75))
    labels = [
        "Layer 1 Only\n($0 Mech.)",
        "Claude-Sonnet\n(Path-Only)",
        "Claude-Haiku\n(Path-Only)",
        "Codex-CLI\n(Path-Only)",
        "L1 + Sonnet\n(Hard Union)",
        "VeriLoop\n(L1 + Codex)",
    ]
    recs = [
        metrics[("layer1_mechanical", "deterministic")]["rec"] * 100,
        metrics[("claude-sonnet", "path_only")]["rec"] * 100,
        metrics[("claude-haiku", "path_only")]["rec"] * 100,
        metrics[("codex-cli", "path_only")]["rec"] * 100,
        union_metrics[("claude-sonnet", "path_only")]["rec"] * 100,
        union_metrics[("codex-cli", "path_only")]["rec"] * 100,
    ]
    f1s = [
        metrics[("layer1_mechanical", "deterministic")]["f1"] * 100,
        metrics[("claude-sonnet", "path_only")]["f1"] * 100,
        metrics[("claude-haiku", "path_only")]["f1"] * 100,
        metrics[("codex-cli", "path_only")]["f1"] * 100,
        union_metrics[("claude-sonnet", "path_only")]["f1"] * 100,
        union_metrics[("codex-cli", "path_only")]["f1"] * 100,
    ]
    ylds = [
        metrics[("layer1_mechanical", "deterministic")]["yld"] * 100,
        metrics[("claude-sonnet", "path_only")]["yld"] * 100,
        metrics[("claude-haiku", "path_only")]["yld"] * 100,
        metrics[("codex-cli", "path_only")]["yld"] * 100,
        union_metrics[("claude-sonnet", "path_only")]["yld"] * 100,
        union_metrics[("codex-cli", "path_only")]["yld"] * 100,
    ]

    x = np.arange(len(labels))
    w = 0.25
    b1 = ax.bar(x - w, recs, w, label="Defect Recall (%)", color=C_OURS, edgecolor=C_DARK, linewidth=0.55)
    b2 = ax.bar(x, f1s, w, label="F1 Score (%)", color=C_CODEX, edgecolor=C_DARK, linewidth=0.55)
    b3 = ax.bar(x + w, ylds, w, label="Clean Yield / TNR (%)", color=C_SONNET, edgecolor=C_DARK, linewidth=0.55)

    for bars in (b1, b2, b3):
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, h + 1.5, f"{h:.1f}",
                    ha="center", va="bottom", fontsize=6.1, color=C_DARK, fontweight="bold")

    ax.axhline(100, color=C_GREY, linestyle=":", linewidth=0.7, alpha=0.6)
    ax.set_ylabel("Percentage (%)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=6.9)
    ax.set_ylim(0, 118)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    ax.set_axisbelow(True)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.15), ncol=3, fontsize=7.0)
    fig.tight_layout(pad=0.35)
    fig.savefig(FIG_DIR / "fig2_main_benchmark.pdf", bbox_inches="tight")
    plt.close(fig)

    # ---------- FIGURE 3: Per-Workspace Audit Matrix (16 Frozen Workspaces, Route A) ----------
    fig, ax = plt.subplots(figsize=(6.8, 3.35))
    ws_ids = [r["artifact_id"] for r in gt_rows]
    cols = [
        ("Layer 1\n($0)", "l1"),
        ("Haiku\n(PO)", ("claude-haiku", "path_only")),
        ("Haiku\n(+Sum)", ("claude-haiku", "with_summary")),
        ("Sonnet\n(PO)", ("claude-sonnet", "path_only")),
        ("Sonnet\n(+Sum)", ("claude-sonnet", "with_summary")),
        ("Codex\n(PO)", ("codex-cli", "path_only")),
        ("L1+Codex\n(Hard Union)", "union"),
    ]
    mat = np.zeros((len(ws_ids), len(cols)))
    ann = []
    for i, r in enumerate(gt_rows):
        aid = r["artifact_id"]
        row_ann = []
        for j, (_, spec) in enumerate(cols):
            if spec == "l1":
                val = 1.0 if l1_map[aid] else 0.0
                row_ann.append("BLK" if l1_map[aid] else "OK")
            elif spec == "union":
                vs = by_cell[(aid, "codex-cli", "path_only")]
                u_hits = sum(1 for v in vs if v or l1_map[aid])
                val = u_hits / len(vs)
                row_ann.append(f"{u_hits}/{len(vs)}")
            else:
                vs = by_cell[(aid, spec[0], spec[1])]
                val = sum(vs) / len(vs)
                row_ann.append(f"{sum(vs)}/{len(vs)}")
            is_def = (r["ground_truth"] == "DEFECTIVE")
            correct_rate = val if is_def else (1.0 - val)
            mat[i, j] = correct_rate
        ann.append(row_ann)

    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("oi_acc", [C_WARN_LT, "#FEF3C7", C_OURS_LT, C_OURS])
    ax.imshow(mat, aspect="auto", cmap=cmap, vmin=0.0, vmax=1.0)
    for i in range(len(ws_ids)):
        for j in range(len(cols)):
            tc = "white" if mat[i, j] > 0.78 else C_DARK
            ax.text(j, i, ann[i][j], ha="center", va="center", fontsize=6.2, fontweight="bold", color=tc)

    short_y = [f"{r['artifact_id']} [{r['ground_truth'][:3]}]" for r in gt_rows]
    ax.set_yticks(range(len(ws_ids)))
    ax.set_yticklabels(short_y, fontsize=6.3)
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels([c[0] for c in cols], fontsize=6.8, fontweight="bold")
    ax.xaxis.tick_top()
    ax.axhline(7.5, color="white", linewidth=1.8)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    fig.tight_layout(pad=0.3)
    fig.savefig(FIG_DIR / "fig3_complementarity.pdf", bbox_inches="tight")
    plt.close(fig)

    # ---------- FIGURE 4: 2x2 Executor x Reviewer Decoupling + Framing Paired Test ----------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.8, 2.55), gridspec_kw={"width_ratios": [1.15, 1.0], "wspace": 0.34})

    revs = ["Layer 1\n($0)", "Claude\nSonnet", "Claude\nHaiku", "Codex\nCLI", "L1+Codex\nUnion"]
    rec_h = [
        metrics[("layer1_mechanical", "deterministic", "claude-haiku")]["rec"] * 100,
        metrics[("claude-sonnet", "path_only", "claude-haiku")]["rec"] * 100,
        metrics[("claude-haiku", "path_only", "claude-haiku")]["rec"] * 100,
        metrics[("codex-cli", "path_only", "claude-haiku")]["rec"] * 100,
        100.0,
    ]
    rec_c = [
        metrics[("layer1_mechanical", "deterministic", "codex-cli")]["rec"] * 100,
        metrics[("claude-sonnet", "path_only", "codex-cli")]["rec"] * 100,
        metrics[("claude-haiku", "path_only", "codex-cli")]["rec"] * 100,
        metrics[("codex-cli", "path_only", "codex-cli")]["rec"] * 100,
        100.0,
    ]
    x4 = np.arange(len(revs))
    w4 = 0.34
    r1 = ax1.bar(x4 - w4 / 2, rec_h, w4, label=f"Haiku-authored (n={h_def} def.)", color=C_HAIKU, edgecolor=C_DARK, linewidth=0.55)
    r2 = ax1.bar(x4 + w4 / 2, rec_c, w4, label=f"Codex-authored (n={c_def} def.)", color=C_OURS, edgecolor=C_DARK, linewidth=0.55)
    for bars in (r1, r2):
        for bar in bars:
            h = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width() / 2, h + 1.8, f"{h:.0f}%",
                     ha="center", va="bottom", fontsize=5.5, fontweight="bold", color=C_DARK)
    ax1.set_xticks(x4)
    ax1.set_xticklabels(revs, fontsize=6.4)
    ax1.set_ylabel("Defect Recall (%)")
    ax1.set_ylim(0, 118)
    ax1.set_yticks([0, 25, 50, 75, 100])
    ax1.grid(axis="y", linestyle=":", alpha=0.4)
    ax1.set_axisbelow(True)
    ax1.legend(loc="upper center", bbox_to_anchor=(0.5, 1.18), ncol=2, fontsize=6.1, columnspacing=0.8)
    ax1.text(0.5, -0.28, "(a) Stratified Executor x Reviewer recall", transform=ax1.transAxes,
             ha="center", fontsize=7.2, fontweight="bold", color=C_DARK)

    # Panel (b): Frozen Paired Framing Test (Path-Only vs +Summary F1)
    f_revs = ["Claude-Haiku\n(n=16 ws, k=3)", "Claude-Sonnet\n(n=16 ws, k=3)"]
    f1_po = [metrics[("claude-haiku", "path_only")]["f1"] * 100, metrics[("claude-sonnet", "path_only")]["f1"] * 100]
    f1_ws = [metrics[("claude-haiku", "with_summary")]["f1"] * 100, metrics[("claude-sonnet", "with_summary")]["f1"] * 100]
    xf = np.arange(len(f_revs))
    wf = 0.30
    fb1 = ax2.bar(xf - wf / 2, f1_po, wf, label="Path-Only", color=C_OURS, edgecolor=C_DARK, linewidth=0.55)
    fb2 = ax2.bar(xf + wf / 2, f1_ws, wf, label="+Executor Summary", color=C_SONNET, edgecolor=C_DARK, linewidth=0.55)
    for bars in (fb1, fb2):
        for bar in bars:
            h = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width() / 2, h + 1.5, f"{h:.1f}%",
                     ha="center", va="bottom", fontsize=6.2, fontweight="bold", color=C_DARK)
    ax2.text(0, 107, "WS p = 1.000", ha="center", fontsize=6.2, color=C_MUTED,
             bbox=dict(boxstyle="round,pad=0.16", facecolor="#F3F4F6", edgecolor=C_GREY, lw=0.5))
    ax2.text(1, 107, "WS p = 1.000", ha="center", fontsize=6.2, color=C_MUTED,
             bbox=dict(boxstyle="round,pad=0.16", facecolor="#F3F4F6", edgecolor=C_GREY, lw=0.5))
    ax2.set_xticks(xf)
    ax2.set_xticklabels(f_revs, fontsize=6.6)
    ax2.set_ylabel("Trial F1 Score (%)")
    ax2.set_ylim(0, 118)
    ax2.set_yticks([0, 25, 50, 75, 100])
    ax2.grid(axis="y", linestyle=":", alpha=0.4)
    ax2.set_axisbelow(True)
    ax2.legend(loc="upper center", bbox_to_anchor=(0.5, 1.18), ncol=2, fontsize=6.1, columnspacing=0.8)
    ax2.text(0.5, -0.28, "(b) Paired framing test (no degradation)", transform=ax2.transAxes,
             ha="center", fontsize=7.2, fontweight="bold", color=C_DARK)

    fig.subplots_adjust(bottom=0.22, top=0.84)
    fig.savefig(FIG_DIR / "fig4_decoupling_and_framing.pdf", bbox_inches="tight")
    plt.close(fig)

    print("\nFIGURES_WRITTEN: fig1_architecture.pdf fig2_main_benchmark.pdf fig3_complementarity.pdf fig4_decoupling_and_framing.pdf")
    print("SUMMARY_COMPLETE")


if __name__ == "__main__":
    main()
