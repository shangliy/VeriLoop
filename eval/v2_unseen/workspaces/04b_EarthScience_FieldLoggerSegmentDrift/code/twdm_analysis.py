"""TWDM soil-moisture QA: golden self-check, ordered per-segment table, figure.

Run from workspace root:  python3 code/twdm_analysis.py
"""
import csv
import json
import math
import os
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "soil_logger_readings.csv")
MANIFEST = os.path.join(ROOT, "data", "twdm_audit_manifest.json")
REPORT_DIR = os.path.join(ROOT, "report")
IMG_DIR = os.path.join(REPORT_DIR, "images")
TABLE_CSV = os.path.join(ROOT, "out", "twdm_table.csv")
GOLDEN_CSV = os.path.join(ROOT, "out", "golden_check.csv")
FIG_SEGMENT = "FM_HEAD"  # segment plotted in the figure


def twdm(values, eps):
    """Return (n, TWDM) or (n, None) when n < 3."""
    x = np.asarray(values, dtype=float)
    n = len(x)
    if n < 3:
        return n, None
    n1 = n // 3
    n2 = n // 3
    means = [
        x[:n1].mean(),
        x[n1:n1 + n2].mean(),
        x[n1 + n2:].mean(),
    ]
    delta = max(means) - min(means)
    sigma = x.std(ddof=0)
    return n, float(delta / (sigma + eps))


def classify(t, threshold):
    if t is None:
        return "N/A", "INSUFFICIENT_LENGTH"
    return f"{t:.6f}", ("PASS" if t <= threshold else "FAIL")


def main():
    with open(MANIFEST, encoding="utf-8") as fh:
        man = json.load(fh)
    eps = float(man["epsilon"])
    threshold = float(man["twdm_pass_threshold"])
    order = list(man["segment_report_order"])
    golden = man["golden_cases"]

    # 1) Golden self-check
    print("== Golden-case check ==")
    max_err = 0.0
    golden_rows = []
    for case in golden:
        _, got = twdm(case["readings"], eps)
        exp = float(case["expected_twdm"])
        err = abs(got - exp)
        max_err = max(max_err, err)
        golden_rows.append((case["name"], len(case["readings"]), exp, got, err))
        print(f"{case['name']:10s} n={len(case['readings']):3d} "
              f"expected={exp!r} got={got!r} abs_err={err:.3e}")
    print(f"MAX ABS ERROR over golden cases: {max_err:.3e} "
          f"(requirement <= 1e-9: {'PASS' if max_err <= 1e-9 else 'FAIL'})")

    with open(GOLDEN_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["case", "n", "expected_twdm", "computed_twdm", "abs_error"])
        for r in golden_rows:
            w.writerow([r[0], r[1], repr(r[2]), repr(r[3]), f"{r[4]:.3e}"])

    # 2) Load series, grouped by segment, sorted by frame ascending
    groups = defaultdict(list)
    with open(DATA, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            groups[row["segment_id"]].append((int(row["frame"]), float(row["vwc_pct"])))
    series = {}
    for seg, pts in groups.items():
        pts.sort(key=lambda p: p[0])
        series[seg] = ([p[0] for p in pts], [p[1] for p in pts])

    # 3) Ordered table, one row per segment in manifest order
    print("\n== Per-segment TWDM table ==")
    header = ["segment_id", "n_frames", "TWDM", "pass_fail"]
    table = []
    for seg in order:
        if seg not in series:
            raise SystemExit(f"segment {seg!r} from manifest not found in data")
        _, vals = series[seg]
        n, t = twdm(vals, eps)
        t_str, status = classify(t, threshold)
        table.append([seg, str(n), t_str, status])
    print("  ".join(f"{h:>14s}" for h in header))
    for r in table:
        print("  ".join(f"{c:>14s}" for c in r))

    with open(TABLE_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(table)

    # 4) Figure: vwc_pct vs frame for one segment
    frames, vals = series[FIG_SEGMENT]
    os.makedirs(IMG_DIR, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.plot(frames, vals, marker=".", linewidth=1)
    ax.set_xlabel("frame")
    ax.set_ylabel("vwc_pct (%)")
    ax.set_title(f"Volumetric water content vs frame: {FIG_SEGMENT}")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig_path = os.path.join(IMG_DIR, f"vwc_vs_frame_{FIG_SEGMENT}.png")
    fig.savefig(fig_path, dpi=150)
    plt.close(fig)
    print(f"\nFigure written: {fig_path}")


if __name__ == "__main__":
    main()
