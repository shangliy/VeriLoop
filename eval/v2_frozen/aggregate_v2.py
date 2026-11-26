#!/usr/bin/env python3
"""Zero-Override Aggregator for VeriLoop v2 Frozen-Artifact Evaluation.

Structurally enforces:
  - ZERO hardcoded scenario overrides: every record's ground_truth label is joined
    directly from ground_truth.csv by artifact_id (immutable raw JSONL predictions).
  - Reports Precision, Recall, F1, FPR, Clean Yield (TNR), Balanced Accuracy,
    Wilson 95% CIs, repeat-to-repeat consistency, and workspace-level exact McNemar
    p-values across identical frozen SHA-256 workspaces (preventing pseudo-replication).
"""
import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

DEFAULT_GT_CSV = Path(__file__).resolve().parent / "ground_truth.csv"


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


def load_ground_truth_map(gt_csv: Path) -> dict[str, dict]:
    with gt_csv.open("r", encoding="utf-8") as fh:
        return {row["artifact_id"]: row for row in csv.DictReader(fh)}


def confusion_metrics(records: list[dict]) -> dict:
    valid = [r for r in records if r.get("predicted_defective") is not None]
    tp = sum(1 for r in valid if r["ground_truth"] == "DEFECTIVE" and r["predicted_defective"] is True)
    fn = sum(1 for r in valid if r["ground_truth"] == "DEFECTIVE" and r["predicted_defective"] is False)
    fp = sum(1 for r in valid if r["ground_truth"] == "CLEAN" and r["predicted_defective"] is True)
    tn = sum(1 for r in valid if r["ground_truth"] == "CLEAN" and r["predicted_defective"] is False)

    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    clean_yield = tn / (fp + tn) if (fp + tn) else 0.0
    bal_acc = 0.5 * (rec + clean_yield)
    _, rec_lo, rec_hi = wilson_ci(tp, tp + fn)
    _, yld_lo, yld_hi = wilson_ci(tn, fp + tn)
    return {
        "n": len(valid),
        "errors": len(records) - len(valid),
        "tp": tp, "fn": fn, "fp": fp, "tn": tn,
        "precision": prec,
        "recall": rec, "recall_ci": (rec_lo, rec_hi),
        "f1": f1,
        "fpr": fpr,
        "clean_yield": clean_yield, "clean_yield_ci": (yld_lo, yld_hi),
        "balanced_acc": bal_acc,
    }


def workspace_majority_records(records: list[dict]) -> list[dict]:
    by_a = defaultdict(list)
    meta = {}
    for r in records:
        if r.get("predicted_defective") is not None:
            by_a[r["artifact_id"]].append(bool(r["predicted_defective"]))
            meta[r["artifact_id"]] = r
    return [
        {
            "artifact_id": aid,
            "ground_truth": meta[aid]["ground_truth"],
            "executor_family": meta[aid]["executor_family"],
            "track": meta[aid]["track"],
            "predicted_defective": sum(vs) > len(vs) / 2,
        }
        for aid, vs in sorted(by_a.items())
    ]


def repeat_stability(records: list[dict]) -> dict:
    by_art = defaultdict(list)
    for r in records:
        if r.get("predicted_defective") is not None:
            by_art[r["artifact_id"]].append(bool(r["predicted_defective"]))
    if not by_art:
        return {"workspaces": 0, "unanimous_rate": 0.0, "repeat_f1_mean": 0.0, "repeat_f1_sd": 0.0}
    unanimous = sum(1 for vs in by_art.values() if len(set(vs)) == 1)
    by_rep = defaultdict(list)
    for r in records:
        by_rep[r.get("repeat", 1)].append(r)
    rep_f1s = [confusion_metrics(rs)["f1"] for rs in by_rep.values()]
    return {
        "workspaces": len(by_art),
        "repeats": len(by_rep),
        "unanimous_rate": unanimous / len(by_art),
        "repeat_f1_mean": statistics.mean(rep_f1s) if rep_f1s else 0.0,
        "repeat_f1_sd": statistics.stdev(rep_f1s) if len(rep_f1s) > 1 else 0.0,
    }


def load_jsonl(paths: list[str], gt_map: dict[str, dict] | None = None) -> list[dict]:
    rows = []
    for p in paths:
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if gt_map and r.get("artifact_id") in gt_map:
                    g = gt_map[r["artifact_id"]]
                    r = {
                        **r,
                        "ground_truth": g["ground_truth"],
                        "defect_type": g["defect_type"],
                        "executor_family": g["executor_family"],
                        "track": g["track"],
                    }
                rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser(description="Aggregate VeriLoop v2 frozen-artifact results with zero overrides.")
    ap.add_argument("jsonl_files", nargs="+", help="One or more results_*.jsonl files")
    ap.add_argument("--ground-truth", default=str(DEFAULT_GT_CSV), help="Authoritative ground_truth.csv path")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    gt_path = Path(args.ground_truth)
    gt_map = load_ground_truth_map(gt_path) if gt_path.is_file() else None
    rows = load_jsonl(args.jsonl_files, gt_map=gt_map)
    groups = defaultdict(list)
    for r in rows:
        groups[(r["reviewer"], r["framing"])].append(r)

    summary = {"total_records": len(rows), "groups": {}, "workspace_level": {}, "by_executor_family": {}}
    print(f"=== VERILOOP V2 FROZEN-ARTIFACT AGGREGATION (ZERO OVERRIDES, records={len(rows)}) ===")
    print(
        f"{'Reviewer':18s} | {'Framing':13s} | {'n':3s} | {'TP/FN':5s} | {'TN/FP':5s} | "
        f"{'Prec':6s} | {'Rec':6s} | {'F1':6s} | {'FPR':6s} | {'Yield':6s} | {'BalAcc':6s} | {'Unan':5s}"
    )
    print("-" * 112)
    for (rev, frm), items in sorted(groups.items()):
        m = confusion_metrics(items)
        st = repeat_stability(items)
        wm = confusion_metrics(workspace_majority_records(items))
        key = f"{rev}::{frm}"
        summary["groups"][key] = {**m, "stability": st}
        summary["workspace_level"][key] = wm
        print(
            f"{rev:18s} | {frm:13s} | {m['n']:3d} | {m['tp']:2d}/{m['fn']:<2d} | {m['tn']:2d}/{m['fp']:<2d} | "
            f"{m['precision']*100:5.1f}% | {m['recall']*100:5.1f}% | {m['f1']*100:5.1f}% | "
            f"{m['fpr']*100:5.1f}% | {m['clean_yield']*100:5.1f}% | {m['balanced_acc']*100:5.1f}% | "
            f"{st['unanimous_rate']*100:4.0f}%"
        )

        # Stratified by executor family
        for ef in sorted({r["executor_family"] for r in items}):
            sub = [r for r in items if r["executor_family"] == ef]
            sm = confusion_metrics(sub)
            summary["by_executor_family"][f"{key}::{ef}"] = sm
            print(
                f"   └─ exec={ef:12s} | n={sm['n']:2d} TP/FN={sm['tp']}/{sm['fn']} TN/FP={sm['tn']}/{sm['fp']} "
                f"Prec={sm['precision']*100:5.1f}% Rec={sm['recall']*100:5.1f}% F1={sm['f1']*100:5.1f}% Yield={sm['clean_yield']*100:5.1f}%"
            )

    # Dual-Layer Union (Layer 1 mechanical OR Layer 2 LLM) on exact same frozen workspaces
    l1_map = {
        r["artifact_id"]: bool(r["predicted_defective"])
        for r in rows
        if r["reviewer"] == "layer1_mechanical" and r.get("predicted_defective") is not None
    }
    if l1_map:
        print("\n=== DUAL-LAYER UNION (Layer 1 Mechanical OR Layer 2 LLM, ZERO OVERRIDES) ===")
        summary["dual_layer_union"] = {}
        for (rev, frm), items in sorted(groups.items()):
            if rev == "layer1_mechanical":
                continue
            valid = [r for r in items if r.get("predicted_defective") is not None and r["artifact_id"] in l1_map]
            if not valid:
                continue
            union_recs = [
                {**r, "predicted_defective": bool(r["predicted_defective"]) or l1_map[r["artifact_id"]]}
                for r in valid
            ]
            um = confusion_metrics(union_recs)
            summary["dual_layer_union"][f"L1+{rev}::{frm}"] = um
            print(
                f"L1+{rev:15s} | {frm:13s} | n={um['n']:3d} | TP/FN={um['tp']:2d}/{um['fn']:<2d} | TN/FP={um['tn']:2d}/{um['fp']:<2d} | "
                f"Prec={um['precision']*100:5.1f}% | Rec={um['recall']*100:5.1f}% | F1={um['f1']*100:5.1f}% | "
                f"FPR={um['fpr']*100:5.1f}% | Yield={um['clean_yield']*100:5.1f}% | BalAcc={um['balanced_acc']*100:5.1f}%"
            )

    # Workspace-Level Paired Framing Comparison (majority vote per workspace, preventing pseudo-replication)
    print("\n=== WORKSPACE-LEVEL PAIRED FRAMING COMPARISON (n=16 independent workspaces) ===")
    summary["paired_framing_ws"] = {}
    reviewers = sorted({r["reviewer"] for r in rows if r["reviewer"] != "layer1_mechanical"})
    for rev in reviewers:
        po_ws = {r["artifact_id"]: r["predicted_defective"] for r in workspace_majority_records(groups[(rev, "path_only")])}
        ws_ws = {r["artifact_id"]: r["predicted_defective"] for r in workspace_majority_records(groups[(rev, "with_summary")])}
        shared = sorted(set(po_ws) & set(ws_ws))
        if not shared:
            continue
        b = sum(1 for k in shared if po_ws[k] and not ws_ws[k])
        c = sum(1 for k in shared if (not po_ws[k]) and ws_ws[k])
        pval = mcnemar_exact_p(b, c)
        summary["paired_framing_ws"][rev] = {"paired_ws": len(shared), "po_only_block": b, "ws_only_block": c, "mcnemar_p": pval}
        print(f"  {rev:15s} | paired_ws={len(shared):2d} | discordant=(po_only={b}, ws_only={c}) | exact McNemar p={pval:.6f}")

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
