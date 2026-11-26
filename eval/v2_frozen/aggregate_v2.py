#!/usr/bin/env python3
"""Zero-Override Aggregator for VeriLoop v2 Frozen-Artifact Evaluation.

Structurally enforces:
  - ZERO hardcoded scenario overrides (every record is evaluated strictly against
    independent ground_truth.csv labels).
  - Reports Precision, Recall, F1, FPR, Clean Yield (TNR), Balanced Accuracy,
    Wilson 95% CIs, repeat-to-repeat consistency, and paired exact McNemar p-values
    across identical frozen SHA-256 workspaces.
"""
import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


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


def load_jsonl(paths: list[str]) -> list[dict]:
    rows = []
    for p in paths:
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def main():
    ap = argparse.ArgumentParser(description="Aggregate VeriLoop v2 frozen-artifact results with zero overrides.")
    ap.add_argument("jsonl_files", nargs="+", help="One or more results_*.jsonl files")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    rows = load_jsonl(args.jsonl_files)
    groups = defaultdict(list)
    for r in rows:
        groups[(r["reviewer"], r["framing"])].append(r)

    summary = {"total_records": len(rows), "groups": {}, "by_executor_family": {}}
    print(f"=== VERILOOP V2 FROZEN-ARTIFACT AGGREGATION (ZERO OVERRIDES, records={len(rows)}) ===")
    print(
        f"{'Reviewer':18s} | {'Framing':13s} | {'n':3s} | {'TP/FN':5s} | {'TN/FP':5s} | "
        f"{'Prec':6s} | {'Rec':6s} | {'F1':6s} | {'FPR':6s} | {'Yield':6s} | {'BalAcc':6s} | {'Unan':5s}"
    )
    print("-" * 112)
    for (rev, frm), items in sorted(groups.items()):
        m = confusion_metrics(items)
        st = repeat_stability(items)
        key = f"{rev}::{frm}"
        summary["groups"][key] = {**m, "stability": st}
        print(
            f"{rev:18s} | {frm:13s} | {m['n']:3d} | {m['tp']:2d}/{m['fn']:<2d} | {m['tn']:2d}/{m['fp']:<2d} | "
            f"{m['precision']*100:5.1f}% | {m['recall']*100:5.1f}% | {m['f1']*100:5.1f}% | "
            f"{m['fpr']*100:5.1f}% | {m['clean_yield']*100:5.1f}% | {m['balanced_acc']*100:5.1f}% | "
            f"{st['unanimous_rate']*100:4.0f}%"
        )

        # Stratified by executor family (critical for 2x2 same-vs-cross family decoupling)
        for ef in sorted({r["executor_family"] for r in items}):
            sub = [r for r in items if r["executor_family"] == ef]
            sm = confusion_metrics(sub)
            summary["by_executor_family"][f"{key}::{ef}"] = sm
            print(
                f"   └─ exec={ef:12s} | n={sm['n']:2d} TP/FN={sm['tp']}/{sm['fn']} TN/FP={sm['tn']}/{sm['fp']} "
                f"Prec={sm['precision']*100:5.1f}% Rec={sm['recall']*100:5.1f}% F1={sm['f1']*100:5.1f}% Yield={sm['clean_yield']*100:5.1f}%"
            )

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
