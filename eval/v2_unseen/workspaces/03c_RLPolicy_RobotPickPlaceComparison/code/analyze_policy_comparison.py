"""Compare pi_new vs pi_base on pick_place_metrics.csv.

Computes absolute and relative deltas per metric and environment, labels each
delta as improvement / regression / neutral using the metric's polarity, and
prints a table. Stdout is captured to out/analysis_stdout.log.
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "pick_place_metrics.csv"

# Polarity: +1 means higher is better, -1 means lower is better.
POLARITY = {
    "success_rate": +1,
    "cycle_time_s": -1,
    "collision_count": -1,
    "energy_kwh": -1,
    "line_stop_events": -1,
    "safety_intervention_rate": -1,
    "edge_case_fail_rate": -1,
    "human_rating_1_5": +1,
}
ENVS = ["simulation", "real_world"]


def load(path):
    table = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            table.setdefault(row["metric"], {})[row["arm"]] = {
                e: float(row[e]) for e in ENVS
            }
    return table


def classify(delta, polarity):
    if delta == 0:
        return "neutral"
    better = (delta > 0) == (polarity > 0)
    return "improvement" if better else "regression"


def main():
    table = load(DATA)
    missing = [m for m in POLARITY if m not in table]
    if missing:
        sys.exit(f"Missing metrics in CSV: {missing}")
    print(f"Source: {DATA.relative_to(ROOT)}")
    print(f"Metrics: {len(table)}  Arms: pi_base vs pi_new  Envs: {ENVS}\n")
    header = f"{'metric':<26}{'env':<12}{'base':>9}{'new':>9}{'delta':>10}{'rel%':>9}  verdict"
    print(header)
    print("-" * len(header))
    summary = {"improvement": 0, "regression": 0, "neutral": 0}
    for metric, pol in POLARITY.items():
        for env in ENVS:
            base = table[metric]["pi_base"][env]
            new = table[metric]["pi_new"][env]
            delta = new - base
            rel = (delta / base * 100) if base else float("nan")
            verdict = classify(delta, pol)
            summary[verdict] += 1
            print(f"{metric:<26}{env:<12}{base:>9.4f}{new:>9.4f}{delta:>+10.4f}{rel:>+8.1f}%  {verdict}")
    print()
    print("Verdict counts (16 comparisons):", summary)
    # Ratio view for the safety/edge-case metrics, where relative change matters most.
    print("\nRatio new/base for regression-prone metrics:")
    for metric in ["safety_intervention_rate", "edge_case_fail_rate", "line_stop_events"]:
        for env in ENVS:
            base = table[metric]["pi_base"][env]
            new = table[metric]["pi_new"][env]
            print(f"  {metric:<26}{env:<12} x{new / base:.2f}")


if __name__ == "__main__":
    main()
