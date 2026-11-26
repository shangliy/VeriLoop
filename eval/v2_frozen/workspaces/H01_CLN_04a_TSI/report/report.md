# Temporal Stability Index (TSI) of `model_output` — Report

## Task
Compute the Temporal Stability Index (TSI) of the `model_output` column of `data/experiment_traces.csv` (rows in time order) over the **full** series, using the lab-defined formula, implemented in our own code.

## Method

**Formula (as specified):** for the 1-D series `x` of model outputs in time order:

- If `len(x) < 2`: TSI = 1.0.
- Otherwise, let `d_i = x_{i+1} − x_i` (first differences), `σ_x` and `σ_d` the **population** standard deviations (ddof = 0) of `x` and `d`, and `ε = 1e-12`:

  **TSI = max(0, min(1, 1 − σ_d / (σ_x + ε)))**

**Implementation:** `code/compute_tsi.py`, pure Python standard library (`csv`, `math`), no import of `utils/lab_metrics.py`. The population std is computed as `sqrt(fsum((v − mean)²) / n)`. The script parses every row, rejects non-numeric or non-finite values (none were found), checks that `frame` is strictly increasing with unit gaps, and runs three sanity asserts on the TSI function (n < 2 → 1.0; constant series → 1.0; result in [0, 1]).

**Log:** `out/compute_tsi_log.txt` (stdout of `python3 -I code/compute_tsi.py`).

No train/test split is involved: the TSI is a descriptive scalar applied to the full series, so no `dev.csv`/`test.csv` selection applies. No hyperparameters were tuned.

## Data checks
From `out/compute_tsi_log.txt`:
- 5000 rows parsed, 0 skipped (no non-numeric or non-finite `model_output` values).
- `frame` runs 0 … 4999, strictly increasing, all gaps = 1 (no missing frames).

## Results (full series)

| Quantity | Value |
|---|---|
| n (samples) | 5000 |
| n_diff (first differences) | 4999 |
| mean(x) | −4.94040764214 |
| σ_x (ddof = 0) | 2.53346011769 |
| σ_d (ddof = 0) | 0.0799555141003 |
| σ_d / (σ_x + ε) | 0.0315598076883 |
| 1 − σ_d / (σ_x + ε) | 0.968440192312 |
| **TSI (full series)** | **0.968440** |

**Final numeric TSI for the full series: 0.968440** (full precision 0.9684401923117073).

## Discussion
- The TSI is close to 1: the step-to-step variation (σ_d ≈ 0.080) is about 3% of the overall spread of the series (σ_x ≈ 2.53). By this index the trace is temporally very stable, i.e. its variance is dominated by slow, large-scale excursions rather than frame-to-frame jitter.
- A single scalar cannot distinguish *where* in the trace any instability occurs. A high full-series TSI can hide localized bursts of jitter or regime changes that are short relative to 5000 frames. If such events matter for the lab's reporting, a windowed TSI would be needed; we did not compute one, since the task asked only for the full-series value.
- The index is scale-invariant to the extent that both σ's scale together, but it depends on the ratio of first-difference spread to level spread, so it is sensitive to sampling rate: a resampled or decimated trace would change σ_d and hence TSI. The value reported here is only meaningful for the 5000-frame trace as provided.

## Limitations
- Only the full-series scalar was requested; no per-window, per-segment, or uncertainty estimates were produced.
- We did not cross-check against `utils/lab_metrics.py` (deliberately, per the instruction not to import it), so agreement with any lab reference implementation is not established here.

## Files
- `code/compute_tsi.py` — implementation and run.
- `out/compute_tsi_log.txt` — raw stdout with all numbers quoted above.
- `report/report.md` — this report.

STATUS: COMPLETE
