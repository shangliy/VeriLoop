# pi_new vs pi_base: Deployment Recommendation

**Recommendation: Do not deploy pi_new as a full replacement for pi_base. Proceed only with a gated pilot, and only after the safety and edge-case regressions are investigated.**

## Basis

Source: `data/pick_place_metrics.csv` (8 metrics × 2 arms × simulation and real-world). Full method and caveats are in `report.md`.

| Metric (polarity) | Sim base → new | Real base → new | Verdict |
|---|---|---|---|
| success_rate (↑) | 0.912 → 0.941 (+3.2%) | 0.883 → 0.905 (+2.5%) | better |
| cycle_time_s (↓) | 2.31 → 2.05 (−11.3%) | 2.45 → 2.18 (−11.0%) | better |
| collision_count (↓) | 0.12 → 0.11 (−8.3%) | 0.19 → 0.17 (−10.5%) | better |
| energy_kwh (↓) | 0.45 → 0.43 (−4.4%) | 0.52 → 0.48 (−7.7%) | better |
| human_rating_1_5 (↑) | 4.1 → 4.3 (+0.2) | 3.9 → 4.0 (+0.1) | better |
| line_stop_events (↓) | 0.02 → 0.03 (×1.5) | 0.05 → 0.08 (×1.6) | **worse** |
| safety_intervention_rate (↓) | 0.004 → 0.018 (×4.5) | 0.009 → 0.031 (×3.4) | **worse** |
| edge_case_fail_rate (↓) | 0.061 → 0.112 (×1.8) | 0.074 → 0.138 (×1.9) | **worse** |

## Reasoning

1. **pi_new is better on throughput, efficiency and success.** Success rate, cycle time, collisions, energy and human rating all improve in both environments, with the same direction in sim and real.
2. **pi_new is worse on safety, the metric that should gate deployment.** Safety intervention rate rises roughly 3.4× in the real world (0.009 → 0.031) and 4.5× in simulation. Edge-case failure roughly doubles in both environments. Line-stop events are also 50–60% higher. These regressions are consistent across sim and real, so they are not a single-environment artifact.
3. **The safety regression is the binding constraint.** A 2–3 percentage-point gain in success does not offset a several-fold increase in human interventions. The success gain is also small in absolute terms.
4. **Sim-to-real transfer does not rescue the decision.** Real-world values are worse than simulation for both arms, and the regressions persist in real-world data, which is the setting that matters for deployment.

## Conditions for revisiting

Move to a gated pilot (limited cell, human supervision, automatic rollback) only if all of the following hold:

- The source of the safety-intervention increase is identified, and the real-world rate is brought to at or below pi_base (≈0.009).
- Edge-case failure is reduced toward pi_base levels (≈0.07 real world), or the failing cases are characterized and covered by a mitigation.
- Line-stop events are not higher than pi_base in a pilot run.
- The evaluation is re-run with per-trial counts and uncertainty intervals, so the significance of these deltas can be assessed. The current CSV reports point values only.

If the safety regression is confirmed at larger sample size, the recommendation is to keep pi_base in production.

## Limitations

- The CSV gives one value per cell. It has no trial counts, variance or confidence intervals, so no statistical significance can be claimed for any delta. The verdicts describe the direction and magnitude of the point estimates.
- Units for collision_count and line_stop_events are not stated. Their ratios are reliable; their absolute meaning is not.
- The data does not say how the safety_intervention_rate or edge_case sets were constructed, so it is unknown whether the two arms were evaluated on the same episodes.
