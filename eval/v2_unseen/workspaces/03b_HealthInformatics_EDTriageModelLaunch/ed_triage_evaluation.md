# ED Triage Model Launch Decision: TriageAssist-B vs. TriageAssist-A

**Decision requested:** Whether to expand TriageAssist-B (candidate) beyond the pilot sites in place of TriageAssist-A (production).

**Recommendation: Do not expand TriageAssist-B now.** Keep TriageAssist-A in production. Continue B only as a development project with the fixes and a re-pilot described below.

## Why

B is better at ranking patients, but it is worse on almost every measure that reflects safety, clinician trust, or patient experience.

| Area | Metric | A | B | Change |
|---|---|---|---|---|
| Offline (n = 8,000) | Sensitivity, critical (ESI 1–2) | 0.812 | 0.871 | Better (+7.3%) |
| Offline | AUROC, acuity | 0.881 | 0.914 | Better (+3.7%) |
| Offline | Specificity, non-urgent | 0.706 | 0.658 | Worse (−6.8%) |
| Offline | Calibration error | 0.079 | 0.118 | Worse (+49.4%) |
| Offline | Agreement with attending disposition | 78.4% | 61.2% | Worse (−17.2 pp) |
| Pilot (14 days) | Median time to physician | 41.8 min | 35.6 min | Better (−6.2 min) |
| Pilot | LWBS (left without being seen) | 2.05% | 3.38% | Worse (+1.33 pp) |
| Pilot | Unscheduled return within 72h | 4.18% | 5.71% | Worse (+1.53 pp) |
| Pilot | Clinician override | 8.35% | 14.18% | Worse (+5.83 pp) |
| Pilot | Patient complaints | 0.11% | 0.25% | Worse (+0.14 pp) |

- **Patients are leaving without being seen more often** (LWBS up about 65% relative), even though physician access is faster. Roughly one extra patient in 75 is lost.
- **Clinicians override B nearly 70% more often** and agree with its dispositions far less. Calibration is also materially worse, so B's risk scores are less numerically reliable than A's.
- **B reduces under-triage on critical patients** and ranks patients better. This is the clearest benefit, and it is the reason to keep working on B.

## Conditions for reconsidering expansion

1. Calibration is restored, and offline results are reported with confidence intervals.
2. LWBS, 72-hour returns, and override rates are at or below A's levels in a re-pilot.
3. The re-pilot has pre-registered stop criteria, per-arm reporting, and runs for several weeks.

A narrower use, such as B as a decision aid that flags likely critical patients, may be worth piloting, since the critical-patient sensitivity gain is the most consistent result.

## Caveats

- The inputs are aggregate summaries. No confidence intervals or significance tests are possible for the offline or online differences.
- The pilot's per-arm sample size is not in the data. Complaint counts are likely very small, so the 127% relative increase is unstable.
- Mechanisms (for example, why LWBS rose while physician access improved) are hypotheses to test, not findings.

Full methodology and analysis: `report/report.md`. Reproducible delta check: `code/recompute_deltas.py`, output in `out/recompute_deltas.log`.
