# TriageAssist-B vs. TriageAssist-A: Evaluation Report

## 1. Question

Should the ED informatics group expand the pilot of **TriageAssist-B** (candidate) beyond the pilot sites, replacing the production **TriageAssist-A**?

## 2. Data

| File | Content | Scale |
|---|---|---|
| `data/offline_evaluation_metrics.csv` | Chart-review acuity, calibration, disposition agreement | Held-out test set, n = 8,000 |
| `data/online_ab_test_metrics.csv` | 14-day randomized-by-shift pilot: time to physician, LWBS, 72h returns, clinician overrides, complaints | Per-arm counts not provided |

Units: `_pct` metrics are percentage points. `Median_time_to_physician_min` is minutes. The `relative_change_pct` column was recomputed as (B − A) / A × 100 and matches the stated value to rounding for all 10 rows (`out/recompute_deltas.log`). Absolute changes are reported alongside, because relative change overstates the effect for small base rates (e.g. complaints).

"Better" direction was set from clinical context: higher is better for sensitivity, specificity, AUROC, and attending agreement; lower is better for calibration error, time to physician, LWBS, returns, overrides, and complaints.

## 3. Results

### 3.1 Offline evaluation (n = 8,000)

| Metric | A | B | Absolute Δ | Relative Δ | Direction | Verdict |
|---|---|---|---|---|---|---|
| Sensitivity, critical (ESI 1–2) | 0.812 | 0.871 | +0.059 | +7.3% | higher better | B better |
| Specificity, non-urgent | 0.706 | 0.658 | −0.048 | −6.8% | higher better | B worse |
| AUROC, acuity score | 0.881 | 0.914 | +0.033 | +3.7% | higher better | B better |
| Mean absolute calibration error | 0.079 | 0.118 | +0.039 | +49.4% | lower better | B worse |
| Disposition agreement with attending | 78.4% | 61.2% | −17.2 pp | −21.9% | higher better | B worse |

### 3.2 Online pilot (14 days, randomized by shift)

| Metric | A | B | Absolute Δ | Relative Δ | Direction | Verdict |
|---|---|---|---|---|---|---|
| Median time to physician (min) | 41.8 | 35.6 | −6.2 min | −14.8% | lower better | B better |
| LWBS rate | 2.05% | 3.38% | +1.33 pp | +64.9% | lower better | B worse |
| Unscheduled return within 72h | 4.18% | 5.71% | +1.53 pp | +36.6% | lower better | B worse |
| Clinician override rate | 8.35% | 14.18% | +5.83 pp | +69.8% | lower better | B worse |
| Patient complaint rate | 0.11% | 0.25% | +0.14 pp | +127.3% | lower better | B worse |

### 3.3 Scorecard

- Favorable for B: 3 of 10 metrics (sensitivity for critical patients, AUROC, median time to physician).
- Unfavorable for B: 7 of 10 metrics. Four of these are patient-safety or patient-experience outcomes measured online (LWBS, 72h returns, complaints) plus clinician overrides.

## 4. Interpretation

**What B does better.** B ranks patients better (AUROC 0.914 vs. 0.881) and catches more critical ESI 1–2 patients (sensitivity 0.871 vs. 0.812). In the pilot, median time to physician fell by 6.2 minutes. These are real signals and are the reason to keep investigating B.

**Why the gains do not, by themselves, justify expansion.**

1. **Safety-relevant online outcomes worsened on every measure.** LWBS rose from 2.05% to 3.38%, meaning roughly one extra patient in 75 leaves without being seen. 72h unscheduled returns rose by 1.5 pp. Both are direct markers of under-triage or lost patients. Faster physician access did not translate into fewer walkouts, which suggests the queue is being reshaped in ways the time-to-physician metric does not capture. This is a hypothesis to test, not an established mechanism.
2. **Clinicians are overriding B far more often.** Override rate went from 8.35% to 14.18%, a 70% relative increase. Consistent with this, attending disposition agreement fell by 17.2 pp (78.4% to 61.2%) offline. Together these say that clinicians do not trust B's dispositions in a large share of cases, and that the trust gap is visible both in the chart review and at the bedside.
3. **Calibration got materially worse.** Mean absolute calibration error rose 49% (0.079 to 0.118). A better AUROC with worse calibration means B's risk scores are more ranked-correct but less numerically reliable. For a triage tool whose outputs drive decisions and staff expectations, miscalibration is a deployment risk in its own right.
4. **Specificity for non-urgent patients fell** (0.706 to 0.658). Non-urgent patients are being more often flagged as more urgent. This is consistent with the sensitivity gain being bought partly with over-triage, which adds load and may contribute to the override and LWBS signals. This is an inference from the metric pattern; the data do not contain the confusion matrices to confirm it.
5. **Patient complaints more than doubled** (0.11% to 0.25%). The absolute number is small, but the relative increase is large and points in the same direction as the other patient-experience metrics.

**Overall.** B's gains are concentrated in ranking metrics and one throughput metric. Its losses are concentrated in calibration, agreement with clinicians, and patient-facing safety outcomes. The pattern does not support a system-wide replacement of A.

## 5. Limitations

- **No uncertainty estimates.** The inputs are aggregate summaries. Without per-case predictions, the AUROC and sensitivity differences cannot be tested for significance, and no confidence intervals can be computed.
- **Online pilot sample size is not reported.** Per-arm patient or shift counts are absent. Shift-level randomization also makes the effective sample size smaller than the patient count. Without counts, the significance of the LWBS, returns, override, and complaint differences cannot be established from this file. For reference only: a two-arm comparison of LWBS near 2.7% with a 1.33 pp difference needs roughly 2,300 patients per arm at 80% power and α = 0.05. The actual pilot may be larger or smaller; the file does not say.
- **Complaint counts are very small.** 0.11% vs. 0.25% implies low event counts, so the 127% relative change is highly unstable.
- **Offline and online populations differ.** The offline set is chart-review labels on a held-out set; the online pilot is live operations over 14 days, possibly including seasonal or site effects. The two are not directly comparable, and the online pilot does not include the offline acuity metrics.
- **The 14-day window is short** and may not capture learning effects, workflow adaptation, or weekly volume cycles.
- **No subgroup data.** Site, shift, acuity mix, and demographic breakdowns are not provided, so effects that differ across sites or populations cannot be detected.
- **Mechanism claims are inferential.** The explanations for the LWBS rise and the specificity drop are plausible readings of the metric pattern, not findings from the data.

## 6. Recommendation

**Do not expand TriageAssist-B now.** Keep A as the production system.

The evidence supports continued development of B, not expansion:

1. **Fix calibration** and re-run the offline evaluation with confidence intervals and per-case predictions available for significance testing.
2. **Investigate the LWBS and override signals** before any expansion: review LWBS and override cases by acuity and shift, and check whether B's recommendations are being reversed in patients who then do well or poorly.
3. **Re-pilot with pre-specified safety guardrails.** Name LWBS, 72h returns, and override rate as stop criteria, with pre-registered thresholds. Report per-arm counts and confidence intervals. Run for longer (at least several weeks) to cover volume cycles.
4. **Consider a narrower use case** if the re-pilot is positive, e.g. B as a decision aid for critical-patient flagging rather than full acuity assignment, since sensitivity for ESI 1–2 is the one clearly stronger result.

Expansion should be reconsidered only if the re-pilot shows LWBS, returns, and overrides at or below A's levels, with calibration and attending agreement restored.
