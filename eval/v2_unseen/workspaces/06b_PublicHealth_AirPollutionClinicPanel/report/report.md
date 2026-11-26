# Air Pollution, Respiratory Clinic Visits, and Policy: Daily Panel Analysis

## 1. Summary

- **Same-day PM2.5 is positively associated with respiratory visits, but the evidence is weak.** In the full model (PM2.5 plus heating degree days, flu index and school holiday), each +1 µg/m³ of same-day PM2.5 corresponds to +0.47 visits/day (Newey-West 95% CI 0.03 to 0.90). A +10 µg/m³ change corresponds to about +4.7 visits/day (about 4% of the mean). The moving-block bootstrap CI (0.04 to 0.99) also barely excludes zero.
- **The association does not persist at lags.** Lag-1 and lag-2 PM2.5 coefficients are positive but their CIs include zero; the lag-3 coefficient is slightly negative. Because the same-day estimate is the only one that clears zero, and lags were examined after seeing it, the result should be treated as a hypothesis, not an established effect.
- **PM2.5 alone explains about 1% of daily visit variance** (R² = 0.014). Heating degree days and the flu index explain most of the variation (full-model R² = 0.37). On the evidence in this panel, the strongest correlates of respiratory demand are cold-weather days and influenza activity, not PM2.5.
- **The school-holiday indicator shows no reliable effect.** Only 4 holiday days exist, and the adjusted estimate (−4.7 visits, CI −10.9 to +1.5) is imprecise and changes sign relative to the raw comparison.
- **The data cannot support a causal or quantitative policy threshold.** The file has no calendar dates, no clinic denominator, no monitor identifier, and no information on whether zeros in PM2.5 or flu index are real values or missing-data codes.

## 2. Data

Source: `data/daily_panel.csv` (read-only), 120 rows, one per day, indexed by `day_index` 0–119. Variables:

| Variable | Definition (as inferred from name) | Mean (SD) | Range | Zeros |
|---|---|---|---|---|
| `pm25` | Daily PM2.5 (µg/m³) | 10.32 (7.16) | 0.00–33.31 | 8 |
| `respiratory_visits` | Daily respiratory clinic visits (count) | 108.4 (20.6) | 62–168 | 0 |
| `heating_degree_day` | Heating-related covariate (integer 0–9) | 5.28 (3.07) | 0–9 | 5 |
| `flu_index` | Influenza activity index | 0.319 (0.194) | 0.00–0.81 | 6 |
| `school_holiday` | Indicator (1 = school holiday) | 0.033 (0.18) | 0–1 | 116 zeros, 4 ones |

Holiday days are indices 0, 30, 60 and 90. Zeros in PM2.5 (indices 2, 4, 12, 23, 27, 81, 93, 117) and flu index (indices 5, 11, 17, 24, 85, 114) may be genuine low values or missing-data codes; the data do not say. I therefore report a sensitivity analysis that drops PM2.5 zeros.

Limitations of the file itself: the index has no calendar date, so day-of-week and seasonal patterns cannot be modelled directly, and the time series is short (120 days, likely one season or less). The `heating_degree_day` definition is not documented; it is treated as a daily integer heating-demand proxy.

## 3. Methods

Code: `code/analysis.py` (numpy only; run with `python3 -I code/analysis.py`). Full stdout: `out/analysis_log.txt`. Machine-readable results: `outputs/results.json`.

1. **Descriptives and correlations.** Pearson and Spearman correlations among all variables.
2. **Main model.** OLS of `respiratory_visits` on `pm25` (lag *k*, *k* = 0–3) plus `heating_degree_day`, `flu_index` and `school_holiday`. Standard errors are Newey-West HAC (Bartlett kernel, 3 lags) to allow for serial correlation in daily residuals. Lagged models drop the first *k* days.
3. **Pm25-only models** at lag 0 and 1, to show how much variance PM2.5 explains without controls.
4. **Inference check.** Moving-block bootstrap (block length 7 days, B = 2000, seed fixed) for the full-model PM2.5 coefficient at lag 0 and lag 1.
5. **Sensitivity.** Refit lag-0 full model after dropping the 8 days with PM2.5 = 0 (n = 112). Standard OLS SEs are reported here because the remaining rows are not consecutive.
6. **Descriptive comparisons.** Visits by PM2.5 band; raw visit means on holiday vs non-holiday days.
7. **Policy scale.** Coefficient × 10 µg/m³, expressed as visits/day and as % of mean visits.

## 4. Results

### 4.1 Correlations

| Pair | Pearson r | Spearman ρ |
|---|---|---|
| Visits ~ PM2.5 | +0.117 | +0.117 |
| Visits ~ heating degree days | +0.434 | +0.390 |
| Visits ~ flu index | +0.382 | +0.348 |
| Visits ~ holiday | +0.028 | +0.044 |
| PM2.5 ~ heating degree days | −0.160 | −0.180 |
| PM2.5 ~ flu index | +0.092 | +0.082 |

PM2.5 is only weakly correlated with visits, and its correlation with the two seasonal covariates is also weak, so confounding by these variables cannot be ruled out but is not the dominant concern in this data.

### 4.2 Regression coefficients (Newey-West 95% CI)

| Model | PM2.5 coef (per µg/m³) | 95% CI | R² |
|---|---|---|---|
| Lag 0, full | **+0.465** (SE 0.223) | [+0.028, +0.903] | 0.371 |
| Lag 1, full | +0.299 (SE 0.240) | [−0.170, +0.769] | 0.355 |
| Lag 2, full | +0.386 (SE 0.222) | [−0.049, +0.822] | 0.361 |
| Lag 3, full | −0.065 (SE 0.294) | [−0.642, +0.512] | 0.357 |
| Lag 0, PM2.5 only | +0.338 (SE 0.264) | — | 0.014 |
| Lag 1, PM2.5 only | +0.084 (SE 0.298) | — | 0.001 |

Covariate coefficients from the lag-0 full model:

- Heating degree days: **+3.19** visits per degree-day (SE 0.56, t = 5.7).
- Flu index: **+41.1** visits per unit index, i.e. about +8 visits per 0.2 index points (SE 8.2, t = 5.0).
- School holiday: **−4.67** (SE 3.17, t = −1.5), not statistically distinguishable from zero.

### 4.3 Robustness of the same-day PM2.5 estimate

- **Block bootstrap (7-day blocks):** lag 0 CI [+0.043, +0.995]; lag 1 CI [−0.336, +0.694]. The lag-0 result is marginally significant under both inference methods.
- **Dropping PM2.5 = 0 days (n = 112):** the lag-0 PM2.5 coefficient is +0.411 (plain OLS SE 0.228), essentially unchanged, so the zeros do not drive the result.
- **Raw bands by same-day PM2.5:** mean visits are 105.0 (PM2.5 = 0, n = 8), 110.3 (0–5, n = 23), 104.3 (5–10, n = 30), 107.6 (10–15, n = 28), 106.1 (15–20, n = 21) and 126.0 (≥20, n = 10). Visits are flat across the first five bands and rise only in the top band, which has 10 days. This pattern is unadjusted and is driven by a small number of high-PM days.

### 4.4 Holiday

Raw mean visits are 111.5 on the 4 holiday days versus 108.3 on other days (a difference of +3.2). The adjusted estimate is −4.7. Both are based on four days, and neither is distinguishable from zero. The holiday indicator should not be used for policy inference from this file.

## 5. Discussion

**What the data support.** Heating-related demand and influenza activity are the clearest correlates of respiratory clinic visits in this panel. Both show large, precisely estimated associations with the outcome, and both are plausible drivers of respiratory care demand. Same-day PM2.5 carries a small positive association that is compatible with a real but modest effect of roughly 4 visits per +10 µg/m³ per day, though the interval includes effects near zero and the estimate is not robust across lags.

**Why the PM2.5 estimate should be read cautiously.**

1. *Lag instability.* The same-day estimate is positive and the lag-1 and lag-2 estimates are positive but imprecise, while lag 3 is negative. Choosing the lag that gives the strongest signal after looking at several is a form of specification search; with only 120 days, a single significant lag out of four is not strong evidence.
2. *Small sample and autocorrelated errors.* Daily series are serially correlated; the HAC and bootstrap intervals are wider than naive ones, and both are near the zero boundary. Effective sample size is smaller than 120.
3. *Missing calendar structure.* Without dates, weekday effects, multi-day air-quality episodes, and seasonal trends beyond the heating proxy cannot be modelled. PM2.5 could be partly picking up unmeasured seasonal or weekday variation.
4. *Measurement.* Zeros in PM2.5 and the flu index may be missing-data codes, and the unit of observation (single clinic, catchment, or region) and the source of visit counts are not specified. Visit counts also depend on clinic capacity, which is not in the file.

**Implications for air-quality policy.** The panel is not sufficient to set an air-quality standard, justify a clinic-level action threshold, or estimate the health benefit of a PM2.5 reduction. What it does suggest is:

- If PM2.5 is causally related to visits at roughly 0.5 visits per µg/m³ per day, a sustained 10 µg/m³ reduction would avoid about 5 visits per day. That is a plausible order of magnitude but cannot be confirmed here, and the interval extends to near zero.
- The larger short-term demand swings in this panel track heating demand and influenza activity. Planning for respiratory surges should therefore rely on influenza surveillance and cold-weather forecasts; these are better-supported signals than same-day PM2.5 alone.
- A PM2.5-triggered staffing or communication protocol could be justified as a low-cost hypothesis test, provided it is evaluated prospectively with a pre-specified outcome and comparison period.

**Recommended data collection** to make the policy question answerable:

1. Calendar dates and clinic or catchment identifiers, so seasonality, weekday effects and multi-site comparisons are possible.
2. PM2.5 from a named monitor, with a missing-data flag separate from true zeros.
3. Clinic denominator (patient-days or staffed capacity) and visit-type codes (e.g. asthma, COPD, lower respiratory infection) to separate pollution-sensitive conditions from general respiratory demand.
4. Several years of data, so that at least two heating seasons and several influenza seasons are included.
5. A pre-registered lag structure and outcome definition, fixed before analysis.

## 6. Conclusions

In this 120-day panel, same-day PM2.5 is weakly and positively associated with respiratory clinic visits (about +4.7 visits per +10 µg/m³), with an interval barely excluding zero and no consistent pattern at other lags. Heating degree days and influenza activity are much stronger correlates of demand. The holiday indicator is uninformative. These results justify further data collection and a prospective evaluation, not a firm policy threshold.

## 7. Reproducibility

- Script: `code/analysis.py` (numpy 2.5.4, Python stdlib). Random seed fixed for the bootstrap.
- Log: `out/analysis_log.txt`.
- Results: `outputs/results.json`.
- The policy brief is `air_health_policy.md` at the workspace root.
