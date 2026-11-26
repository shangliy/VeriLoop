# Report: pi_new vs pi_base on Pick-and-Place

Deliverable: `report/policy_comparison.md` (deployment recommendation). This file gives the methodology, results and discussion behind it.

## Data

`data/pick_place_metrics.csv` is long-form: 16 rows, one per (arm, metric), with columns `simulation` and `real_world`. Arms are `pi_base` and `pi_new`. Metrics are success_rate, cycle_time_s, collision_count, energy_kwh, line_stop_events, safety_intervention_rate, edge_case_fail_rate and human_rating_1_5. The file contains no sample sizes, trial-level data, variance or metadata. It was not modified.

## Method

1. Each metric was given a polarity (higher is better for success_rate and human_rating; lower is better for the other six).
2. For each metric and environment, the absolute delta (new − base), the relative change (delta / base) and a verdict (improvement, regression or neutral) were computed. The verdict follows from the sign of the delta and the polarity.
3. Ratios new/base were reported for the three metrics where regressions are largest.

Script: `code/analyze_policy_comparison.py`. Stdout: `out/analysis_stdout.log`. Both are reproducible with `python3 -I code/analyze_policy_comparison.py`.

No statistical test is possible: the data contains one point estimate per cell. The analysis is therefore descriptive. The verdicts describe the point estimates only.

## Results

- **Verdicts:** 10 of 16 comparisons are improvements and 6 are regressions. Neutral: 0.
- **Improvements** (both environments): success_rate (+2.5–3.2%), cycle_time_s (−11%), collision_count (−8 to −11%), energy_kwh (−4 to −8%), human_rating (+0.1 to +0.2).
- **Regressions** (both environments): safety_intervention_rate (×4.5 sim, ×3.4 real), edge_case_fail_rate (×1.8–1.9), line_stop_events (×1.5–1.6).

The full table is in `out/analysis_stdout.log`.

## Discussion

The two arms trade off. pi_new is faster, uses less energy, collides a little less and succeeds a little more often. It also intervenes more often, fails more on edge cases and stops the line more often. The safety-related regressions are much larger in relative terms (3–4.5×) than the efficiency gains (roughly 10%).

Two patterns are worth noting:

- **The direction is consistent across environments.** Every metric that improves in simulation also improves in the real world, and every regression appears in both. This makes a simulation-only artifact less likely, though it does not rule out a shared evaluation-set effect.
- **Real-world values are worse than simulation for both arms**, and pi_new's safety gap is partly closed in relative terms (×4.5 → ×3.4). This suggests the gap is not an artifact of the simulator, but the data cannot establish the cause.

## Limitations

- No uncertainty estimates. A 0.02 change in a rate near 0.01 may be within noise, and the data cannot show whether it is.
- Units for collision_count and line_stop_events are unspecified.
- It is unknown whether the arms were evaluated on the same episodes or edge-case sets.
- The data shows that pi_new regresses on safety. It does not show why.

## Conclusion

pi_new is not ready to replace pi_base. Its efficiency and success gains are real in the point estimates but small, and its safety-intervention and edge-case regressions are large and consistent. The recommendation is a no-go for full deployment and a gated pilot only after the safety regression is diagnosed and a larger, uncertainty-quantified evaluation is run. See `report/policy_comparison.md` for the decision criteria.
