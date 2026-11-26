# Beverage cooling on a counter: model fit

## Summary

- The drink cools by Newton's law of cooling, with ambient **Ta = 25.000 °C**, initial temperature **T0 = 85.000 °C**, and rate constant **k = 0.011552 min⁻¹** (time constant τ = 1/k ≈ **86.6 min**, half-life of the excess temperature ≈ 60 min).
- The series also contains two abrupt discontinuities that a single exponential cannot absorb: a **+5.4 °C step at t = 80 min** and a **−6.8 °C step at t = 121 min**. Between those times the curve relaxes toward **34 °C** instead of 25 °C, with the same k.
- A piecewise-ambient Newton model (ambient 25 / 34 / 25 °C across the three segments, shared T0 and k) fits all 200 points to **RMSE 0.00028 °C**. That is the expected rounding error for values logged to 3 decimals (≈0.00029 °C), so the model is exact to the precision of the data.
- A plain single-exponential Newton fit gives Ta = 17.9 ± 1.7 °C, which is biased by the two events and leaves strongly autocorrelated residuals (lag-1 r = 0.96). Its numbers should not be used.

## Data

`data/beverage_temperature_series.csv`: 200 rows, `time_min` = 0…199 at uniform 1-minute steps, `temperature_c` from 85.000 to 31.022 °C. The file is read-only and was not modified.

## Methods

Script: `code/fit_cooling.py` (run with `python3 -I`). Log: `out/fit_log.txt`. All fits use `scipy.optimize.curve_fit` with bounds.

1. **Part A, smooth models on all points.** Newton with free Ta, T0, k (A1); Newton with T0 fixed to the first reading (A2); two-exponential (A3); power-law excess (A4). Compared by RMSE, AIC/BIC, and lag-1 residual autocorrelation.
2. **Part B, residual diagnosis.** Compare each first difference with the median of its neighbours. Two deviations stand out: +5.38 °C at t 79→80 and −6.76 °C at t 120→121. Outside these two steps the second differences have SD 0.002 °C, so the smooth trend is very clean.
3. **Part C, event-aware Newton with decaying steps** (Newton plus J·e^{−k(t−tj)} terms at the event times). Kept as a comparison. It is misspecified: RMSE 0.53 °C, lag-1 r = 0.95.
4. **Part D, Newton on clean windows.** Refit Newton separately on t<80, 81≤t<121, and t≥121.
5. **Part E, piecewise-ambient Newton (preferred).** T(t) = Ta_j + (T0 − Ta_j)·e^{−kt}, where j is the segment (t<80, 80≤t<121, t≥121). T0 and k are shared across segments. Event times are taken from Part B and confirmed by Part C's change-point scan (±3 min scan, best at 80 and 121).

## Results

### Smooth models on all points (Part A)

| Model | Parameters | RMSE (°C) | AIC | lag-1 r(res) |
|---|---|---|---|---|
| A1 Newton (Ta, T0, k free) | Ta 17.94±1.7, T0 82.37±0.55, k 0.00818±0.00043 | 2.18 | 318 | 0.96 |
| A2 Newton (T0 = 85) | Ta 22.2±1.0, k 0.00974±0.00032 | 2.30 | 337 | 0.96 |
| A3 two-exponential | 5 params; Ta −19.6±32 (unphysical) | 1.95 | 277 | 0.95 |
| A4 power-law excess | Ta −50 (bound hit), p 0.43±0.64 | 2.07 | 300 | 0.96 |

None of these is adequate. The lag-1 autocorrelation of residuals stays at 0.95–0.96 across all of them, so a smooth model is systematically wrong. A3 gets the lowest error only by fitting an unphysical negative ambient. A1's residuals show a clear pattern by segment: mean +0.69 °C for t<30, −1.23 °C for 30≤t<90, and +0.48 °C for t≥90.

### Discontinuities (Part B)

| Step (reading index) | Raw Δ (°C) | Deviation from local trend (°C) |
|---|---|---|
| t 79→80 | +5.151 | +5.383 |
| t 120→121 | −6.922 | −6.756 |

### Clean-window Newton fits (Part D)

| Window | n | Ta (°C) | T0 (°C) | k (min⁻¹) | τ (min) | RMSE (°C) |
|---|---|---|---|---|---|---|
| t < 80 | 80 | 25.002 | 85.000 | 0.011550 | 86.6 | 0.0003 |
| 81 ≤ t < 121 | 40 | 34.002 | 85.003 | 0.011550 | 86.5 | 0.0003 |
| t ≥ 121 | 79 | 25.000 | 85.003 | 0.011550 | 86.6 | 0.0003 |

Each window is an exact Newton curve, and the three windows share the same k. The middle window has a different equilibrium (34 °C) and the outer two have 25 °C.

### Preferred model (Part E)

| Parameter | Estimate | SE |
|---|---|---|
| Ta, segment 1 (t<80) | 25.00032 °C | 0.0004 |
| Ta, segment 2 (80≤t<121) | 34.00003 °C | 0.0003 |
| Ta, segment 3 (t≥121) | 25.00009 °C | 0.0002 |
| T0 | 84.99987 °C | 0.0001 |
| k | 0.0115520 min⁻¹ | 1.2e-7 |

- τ = 86.56 min.
- RMSE 0.00028 °C, max |residual| 0.00056 °C, lag-1 r = +0.016. The residuals are white noise at rounding level, and this holds in each segment (mean ≈ 0, SD ≈ 0.0003 °C).
- With T0 fixed to the first reading (85.0 °C), the fit is unchanged: Ta = 25.0005, 34.0002, 25.0002 °C, k = 0.011553 min⁻¹, RMSE 0.00028 °C.
- Implied discontinuities from the fitted model: +5.428 °C at t=80 (observed +5.383) and −6.776 °C at t=121 (observed −6.756). These agree with the raw steps to within ~0.05 °C; the difference comes from the neighbouring cooling over one minute.

## Discussion

**Why a single exponential fails.** The single-exponential fit pulls its equilibrium to 18 °C because the two steps (a rise, then a larger drop) distort the decay; it does not reflect the ambient in any segment. The autocorrelated residuals show that the error is structural, not noise. Fitting more smooth functions (A3, A4) does not fix this and produces unphysical parameters.

**What the data show.** The cooling itself is clean Newton behaviour with Ta = 25 °C and τ ≈ 87 min. The departures are two sharp, discrete events, not gradual drift. The drink jumps up about 5.4 °C at t = 80, then drops about 6.8 °C at t = 121. Between them the curve relaxes toward 34 °C, not 25 °C.

**Interpretation caveat.** A continuous change of ambient temperature in Newton's law gives a continuous temperature, but the data jump at t = 80 and t = 121. So the preferred model is an empirical description, one in which each segment is a Newton curve with its own equilibrium, sharing k. It is not a continuous-ODE model with a time-varying ambient. The two discontinuities could have come from an external action (e.g. adding or removing a hot or cold component, moving the cup into a warmer spot), but the temperature record alone cannot identify the physical cause. I have not claimed one.

**Limitations.** One trajectory only, so the parameters have no between-run spread. The exact fit at rounding precision suggests the record may be synthetic or heavily processed, and the report should not be read as evidence about real drinks without that caveat. The ambient is a single constant within each segment; the room was described as only "roughly steady", and a real room would show more variation than this record does.

## Files

- `code/fit_cooling.py`: all fits (Parts A–E), residuals, SVG plot.
- `out/fit_log.txt`: full stdout of the run; `out/fit_summary.json`: all parameters, SEs, and diagnostics.
- `outputs/residuals.csv`: per-point predictions and residuals for the preferred model (E) and the single-exponential fit (A1).
- `outputs/fit_plot.svg`: data (black), preferred piecewise model (blue), single Newton fit (red dashed). Written as plain SVG because PIL is not installed, so matplotlib cannot be imported.
