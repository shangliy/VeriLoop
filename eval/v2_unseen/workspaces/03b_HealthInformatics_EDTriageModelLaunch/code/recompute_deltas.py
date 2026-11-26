"""Recompute A->B absolute and relative deltas from the two source CSVs and
check the provided relative_change_pct column. Read-only on data/."""
import csv, os, sys

base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
# higher_is_better per metric, from clinical context
offline_dir = {
    "Sensitivity_critical_ESI12": True,
    "Specificity_non_urgent": True,
    "AUROC_acuity_score": True,
    "Mean_absolute_calibration_error": False,
    "Disposition_agreement_with_attending_pct": True,
}
online_dir = {
    "Median_time_to_physician_min": False,
    "LWBS_rate_pct": False,
    "Unscheduled_return_72h_pct": False,
    "Clinician_override_pct": False,
    "Patient_complaint_rate_pct": False,
}

def run(path, a_col, b_col, direction, unit):
    print(f"== {os.path.basename(path)} ==")
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            a, b = float(r[a_col]), float(r[b_col])
            diff = b - a
            rel = diff / a * 100
            stated = float(r["relative_change_pct"])
            hib = direction[r["metric"]]
            better = (diff > 0) == hib if diff != 0 else None
            verdict = "B better" if better else "B worse"
            print(f"{r['metric']:<42} A={a:<8} B={b:<8} "
                  f"abs={diff:+.3f}{unit} rel_recalc={rel:+.2f}% stated={stated:+.1f}% "
                  f"match={'yes' if abs(rel-stated) < 0.06 else 'NO'} -> {verdict}")
    print()

run(os.path.join(base, "offline_evaluation_metrics.csv"), "triage_a", "triage_b", offline_dir, "")
run(os.path.join(base, "online_ab_test_metrics.csv"), "triage_a_pct", "triage_b_pct", online_dir, "")
