"""Temporal Stability Index (TSI) on the model_output column of data/experiment_traces.csv.

Implemented from the task definition (no import of utils/lab_metrics.py):
  x   : 1-D series of model_output values, in row (time) order
  if len(x) < 2: TSI = 1.0
  else:
    d        = first differences of x  (d_i = x_{i+1} - x_i)
    sigma_x  = population std of x  (ddof = 0)
    sigma_d  = population std of d  (ddof = 0)
    eps      = 1e-12
    TSI      = max(0, min(1, 1 - sigma_d / (sigma_x + eps)))

Pure standard library so it runs without extra packages.
"""
import csv
import math
import os
import sys

EPS = 1e-12
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data", "experiment_traces.csv")


def pop_std(values):
    """Population standard deviation (ddof = 0)."""
    n = len(values)
    if n == 0:
        raise ValueError("std of empty sequence")
    mean = math.fsum(values) / n
    var = math.fsum((v - mean) ** 2 for v in values) / n
    return math.sqrt(var)


def first_differences(x):
    return [x[i + 1] - x[i] for i in range(len(x) - 1)]


def tsi(x):
    """Temporal Stability Index of a 1-D sequence x (in time order)."""
    x = list(x)
    if len(x) < 2:
        return 1.0
    d = first_differences(x)
    sigma_x = pop_std(x)
    sigma_d = pop_std(d)
    raw = 1.0 - sigma_d / (sigma_x + EPS)
    return max(0.0, min(1.0, raw))


def load_model_output(path):
    frames, values, bad = [], [], []
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        for lineno, row in enumerate(reader, start=2):
            raw = row["model_output"]
            try:
                v = float(raw)
            except (TypeError, ValueError):
                bad.append((lineno, raw))
                continue
            if not math.isfinite(v):
                bad.append((lineno, raw))
                continue
            frames.append(int(row["frame"]))
            values.append(v)
    return frames, values, bad


def main():
    frames, x, bad = load_model_output(DATA)
    print(f"file: {DATA}")
    print(f"rows parsed: {len(x)}; unparseable/non-finite rows skipped: {len(bad)}")
    if bad:
        print(f"skipped rows (line, raw): {bad[:10]}")
    print(f"frame range: {frames[0]} .. {frames[-1]}; "
          f"monotone increasing: {all(frames[i] < frames[i + 1] for i in range(len(frames) - 1))}")
    gaps = [frames[i + 1] - frames[i] for i in range(len(frames) - 1)]
    print(f"frame gaps: min={min(gaps)} max={max(gaps)} (gaps>1 means missing frames)")
    print()

    d = first_differences(x)
    sigma_x = pop_std(x)
    sigma_d = pop_std(d)
    print("formula: TSI = max(0, min(1, 1 - sigma_d / (sigma_x + 1e-12)))")
    print(f"n = {len(x)}")
    print(f"mean(x) = {math.fsum(x) / len(x):.12g}")
    print(f"sigma_x (ddof=0) = {sigma_x:.12g}")
    print(f"n_diff = {len(d)}")
    print(f"sigma_d (ddof=0) = {sigma_d:.12g}")
    ratio = sigma_d / (sigma_x + EPS)
    print(f"sigma_d / (sigma_x + eps) = {ratio:.12g}")
    print(f"1 - ratio = {1.0 - ratio:.12g}")
    value = tsi(x)
    print(f"TSI (full series) = {value:.6f}")
    print(f"TSI (full series, full precision) = {value!r}")

    # Sanity checks on the implementation
    assert tsi([5.0]) == 1.0, "n<2 rule"
    assert tsi([]) == 1.0, "n=0 rule"
    assert abs(tsi([1.0, 1.0, 1.0]) - 1.0) < 1e-9, "constant series -> sigma_d=0 -> 1"
    assert 0.0 <= value <= 1.0
    print("sanity checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
