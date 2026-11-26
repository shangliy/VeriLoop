# Flame Speed vs. Chamber Pressure: Model Fit and Analysis

## 1. Summary

- The dataset (`data/flame_pressure_series.csv`, n = 68) shows flame speed decreasing with chamber pressure over 38–97.5 kPa, but it is **not described by a single smooth curve**. There is an abrupt upward jump of about +13 cm/s between 81.52 kPa (19.57 cm/s) and 82.40 kPa (32.58 cm/s).
- Smooth single-curve models fit poorly: linear R² = 0.117, power law R² = 0.217, exponential R² = 0.135. A quadratic reaches R² = 0.765 only by approximating the jump with curvature.
- A **two-segment (piecewise) power law** with a breakpoint at **≈ 81.96 kPa** fits the data almost exactly (RMSE = 0.174 cm/s, leave-one-out RMSE = 0.184 cm/s). Each segment is well described by a power law or a line.
- Recommendation: treat the two pressure regimes as separate relations. Before using the model for engineering decisions, check the lab records for a cause of the discontinuity (see §5). The data alone cannot tell whether it is physical or a logging/test-campaign artifact.

## 2. Data and Method

**Data.** Two columns: `pressure_kPa` and `flame_speed_cm_s`. Pressure is strictly increasing; there are no missing values. The file has no metadata (units beyond the column names, replicates, uncertainties, test conditions, or run identifiers), so the analysis uses the values as given.

**Candidate models.** Fitted by least squares (`scipy.optimize.curve_fit` or `numpy.polyfit`):

1. Linear: S = a + bP
2. Power law: S = a·P^m
3. Exponential: S = a·exp(−kP)
4. Quadratic: S = c0 + c1·P + c2·P²
5. Piecewise power law: two power laws joined at a breakpoint, found by scanning every candidate split (at least 8 points per segment) and keeping the split with the lowest total SSE.

**Model comparison.** R², RMSE, AIC (Gaussian residuals, AIC = n·ln(SSE/n) + 2k), and leave-one-out cross-validation (LOO-CV). LOO-CV is the most important check here because it measures out-of-sample error and penalises flexible models.

Code: `code/analyze_flame.py`. Full stdout: `out/analysis_log.txt`. Machine-readable summary: `out/summary.json`. Figure: `outputs/flame_speed_vs_pressure.png`.

## 3. Results

### 3.1 Single-curve models (all 68 points)

| Model | Parameters | R² | RMSE (cm/s) | AIC | LOO-CV RMSE (cm/s) |
|---|---|---|---|---|---|
| Linear | a = 35.54, b = −0.1038 | 0.117 | 4.96 | 221.8 | 5.12 |
| Power law | a = 114.86, m = −0.3345 | 0.217 | 4.67 | 213.7 | 4.83 |
| Exponential | a = 37.77, k = 0.00420 | 0.135 | 4.91 | 220.4 | — |
| Quadratic | c2 = 0.01564, c1 = −2.2228, c0 = 102.57 | 0.765 | 2.56 | 134.0 | 2.67 |

The exponential model was not included in the LOO-CV comparison because its results were not needed to decide between the candidates. The single power law's residuals are systematically positive at both ends and negative in the middle (Figure, right panel), which indicates the wrong functional form.

### 3.2 Breakpoint

The largest consecutive change in flame speed is at the pressure step 81.515 → 82.403 kPa (ΔS = +13.00 cm/s). The median absolute consecutive change across the series is 0.37 cm/s, so this jump is about 35 times the typical step. The optimal two-segment split falls at **81.96 kPa** (50 points below, 18 above).

### 3.3 Piecewise power law (final model)

Low-pressure segment (38.0–81.5 kPa, n = 50):

  **S = 1178.98 · P^(−0.92983)**  (cm/s, kPa)

High-pressure segment (82.4–97.5 kPa, n = 18):

  **S = 255.16 · P^(−0.46600)**  (cm/s, kPa)

| Segment | Model | R² | RMSE (cm/s) |
|---|---|---|---|
| Low P (n = 50) | power law, S = 1178.98·P^−0.92983 | 0.999 | 0.170 |
| Low P (n = 50) | linear, S = 53.989 − 0.4438·P | 0.961 | 1.151 |
| High P (n = 18) | power law, S = 255.16·P^−0.46600 | 0.944 | 0.184 |
| High P (n = 18) | linear, S = 46.056 − 0.1632·P | 0.945 | 0.181 |

Source: `out/analysis_log.txt` and `out/segment_metrics.txt`. Combined over both segments, the piecewise power law gives SSE = 2.06 and RMSE = 0.174 cm/s, versus SSE = 1486 for the single power law.

On the high-P segment, the power law and the linear fit are equally good (R² 0.944 vs 0.945), so the linear form is an adequate description there. The low-P segment is clearly curved: the power law (R² 0.999) beats the linear fit (R² 0.961). The high-P exponent (m = −0.47) should therefore be read as weakly constrained.

**LOO-CV comparison (all points):**

| Model | LOO RMSE (cm/s) | Median |error| (cm/s) |
|---|---|---|
| Linear | 5.12 | 5.22 |
| Power law | 4.83 | 5.17 |
| Quadratic | 2.67 | 0.82 |
| **Piecewise power law** | **0.18** | **0.11** |

The piecewise model's error is about 15× smaller than the best single-curve model's error (LOO RMSE 0.18 vs 2.67).

## 4. Discussion

- **The apparent smooth relationship is misleading.** Pooling both regimes into one curve produces high error and systematic residuals (Figure, right panel). A quadratic can look reasonable (R² = 0.77) but still has a median error of 0.8 cm/s versus 0.11 cm/s for the piecewise model, and it would mispredict flame speed near the step.
- **Within each regime, flame speed decreases with pressure**, and the decrease is steeper at low pressure (local exponent ≈ −0.93) than at high pressure (≈ −0.47). This is consistent with a monotone but saturating dependence in the low-pressure regime.
- **The high-P regime sits about 13 cm/s above the extrapolated low-P trend.** At the breakpoint, the low-P curve gives ≈ 19.6 cm/s and the high-P curve gives ≈ 32.7 cm/s. Extrapolating either segment across the gap would be unreliable.
- **Caveats:**
  - The breakpoint is chosen from the data (by scanning splits), so its exact location is uncertain by up to one sample spacing (≈ 0.9 kPa). The existence of the step is not in doubt: the jump is much larger than the within-segment noise.
  - The high-P segment has only 18 points spanning 82–97.5 kPa, so its exponent (m = −0.47) is less well constrained than the low-P exponent.
  - No replicates or measurement uncertainties are given, so no confidence intervals on the parameters are reported. Parameter values should be treated as descriptive of this series, not as validated physical constants.
  - Within each regime the piecewise residuals have RMSE ≈ 0.17–0.18 cm/s and no visible trend (Figure, right panel). Their scale is a rough noise level, not a formal measurement uncertainty, since no replicates are available.

## 5. Open Questions and Recommendations

1. **Identify the cause of the discontinuity near 82 kPa.** Candidate explanations to check against lab logs include: a change of test campaign, fuel or mixture, ignition or flow setting, instrument or calibration change, or a data-logging discontinuity. A physical bifurcation (e.g., a change in flame regime) would need its own model; a logging or calibration artifact would mean the high-P segment should be corrected or excluded.
2. **Collect replicate data** on both sides of the breakpoint, and in a narrow window around 82 kPa, to confirm the step and pin down its location.
3. **Do not use a single smooth correlation** for this series for prediction across the full pressure range.

## 6. Reproducibility

- Script: `code/analyze_flame.py` (reads `data/flame_pressure_series.csv`, read-only).
- Outputs: `out/analysis_log.txt` (stdout), `out/summary.json` (fitted parameters and CV results), `outputs/flame_speed_vs_pressure.png` (two-panel figure: data with fitted curves, and residuals).
- Environment: Python 3 with numpy 2.5.4, scipy 1.18.1, matplotlib 3.11.2. pandas is not installed in this environment, so the script uses only the standard `csv` module.
