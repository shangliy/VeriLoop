# Load Series Review: Annual Outlook and Reliability Commentary

**Data:** `data/load_15min.csv` (672 rows, 15-minute load in MW, 2026-01-01 00:00 to 2026-01-07 23:45, timestamps in UTC)
**Code:** `code/analysis.py` (numpy and matplotlib only). **Stdout log:** `out/analysis_stdout.log`. **Outputs:** `outputs/`.

## Bottom line

1. **This file cannot support an annual load forecast.** It covers seven days in one season, and 18% of it is missing. The annual numbers below are arithmetic envelopes from one winter week. They are not forecasts, and they should not be used for reserve sizing or capacity decisions.
2. **Observed level:** the week averaged **119.8 MW** (median 120.0 MW, standard deviation 5.0 MW). The peak was **133.6 MW** (2026-01-05 19:30 UTC) and the minimum was **99.1 MW** (2026-01-01 05:15 UTC).
3. **Short-horizon predictability:** no reliable intraday or weekly shape is visible in the seven days. Predicting the flat prior-day mean beat the hour-of-day profile and persistence in a day-ahead backtest. Expect day-ahead errors of about **3.0–3.4% MAPE (about 3.6–4.1 MW MAE)** from simple methods.
4. **Reliability-relevant signals:** single-interval ramps reach **21.8 MW** (15-minute change), and the 99th percentile absolute ramp is **19.2 MW**. A 30-hour telemetry gap (2026-01-01 20:00 to 01-03 01:45) should be investigated before this series is used in a review.

## 1. Data quality

| Check | Result |
|---|---|
| Rows / span | 672 rows, 7 calendar days, 2026-01-01 00:00 to 2026-01-07 23:45 |
| Sampling | Uniform 15 minutes; no duplicate timestamps |
| Missing values | **120 of 672 (17.9%)**, all empty fields, forming **one contiguous run** from 2026-01-01 20:00 to 2026-01-03 01:45 (30.0 h) |
| Coverage by day | Jan 1: 83%; Jan 2: 0%; Jan 3: 92%; Jan 4–7: 100% |
| Range | 99.07–133.57 MW |

The gap was not imputed. All statistics above use valid intervals only. The backtest uses only Jan 5–7, which are complete, so the gap does not affect the forecast evaluation. Jan 1 is also a public holiday in most jurisdictions, and the gap covers the holiday period, so the gap may be a holiday effect as well as a data problem. The reason for the gap is not documented in the file.

## 2. Descriptive results

Distribution (valid intervals, n = 552):

| Statistic | MW |
|---|---|
| Mean / median / std | 119.83 / 120.00 / 4.97 |
| P1 / P5 / P95 / P99 / P99.9 | 107.8 / 111.1 / 128.0 / 131.4 / 133.4 |
| Peak-to-average ratio | 1.11 |
| Week load factor (mean / max) | 0.897 |

Daily means were stable: 119.2 MW (Jan 1, partial), 119.6 (Jan 3, partial), 119.8 (Jan 4, Sun), 119.5 (Jan 5, Mon), 120.2 (Jan 6, Tue), and 120.5 (Jan 7, Wed). Weekend and weekday means differ by 0.15 MW (119.73 vs 119.88 MW), which is negligible.

Hour-of-day means range from 118.2 MW (23:00 UTC) to 122.6 MW (09:00 UTC). With roughly 6–7 observations per hour and a standard deviation of about 5 MW, the standard error of each hourly mean is about 2 MW. The hour-to-hour differences are therefore within noise and should not be read as a diurnal pattern.

![15-minute load](../outputs/fig_timeseries.png)

## 3. Short-horizon (day-ahead) backtest

Each method forecasts the 96 intervals of a target day using only prior data. Targets: Jan 5, Jan 6, Jan 7 (complete days).

| Method | n | MAE (MW) | RMSE (MW) | MAPE |
|---|---|---|---|---|
| Persistence (previous day, same interval) | 288 | 5.30 | 6.74 | 4.42% |
| Slot mean (same interval, all prior days) | 288 | 4.06 | 5.16 | 3.38% |
| Flat (mean of all prior valid data) | 288 | **3.65** | **4.64** | **3.03%** |

Per-day results are in `outputs/backtest_metrics.csv`. The flat forecast was best on all three days. Persistence was worst, which fits the absence of a repeatable daily pattern in this sample. The slot-mean method is weaker than the flat forecast because averaging over only two to four prior days adds noise to each interval's estimate. This ranking will not hold once a full year of history is available. It is a statement about this week, not about the system.

![Profile and backtest](../outputs/fig_profile_backtest.png)

## 4. Annual outlook: arithmetic envelope, not a forecast

Because the seasonal shape is unknown, the figures below are only scalings of the observed week.

- **Flat annual energy:** 119.83 MW × 8,760 h = **1,049.7 GWh**. This assumes the winter week is representative of the whole year, which it is not in general. Heating and cooling seasons are typically the largest drivers of annual peak and energy.
- **Growth scenarios** (trend applied to energy and peak, 0–3% per year): 1,050–1,081 GWh.
- **Planning peak envelope:** the observed 133.6 MW peak, grown at 0–3% per year and then raised by a 0–15% weather or extreme-event uplift. This gives **134–158 MW**. The uplift is a placeholder assumption, not an estimate of a 1-in-N-year peak.

The full grid is in `outputs/annual_scenarios.csv`.

## 5. Reliability commentary

**What the data supports**

- **Ramping:** the median absolute 15-minute change is 4.6 MW, and the 99th percentile is 19.2 MW. The largest single-interval move was 21.8 MW (down) and 21.2 MW (up). Within this sample, the system needs to absorb moves of about 20 MW within 15 minutes without warning, so ramping and regulation capability should be checked against that figure.
- **Forecast error:** at day-ahead, simple methods have MAE of about 3.6–4.1 MW. Any operating reserve set against forecast error should be sized with the error distribution from a longer history, not from these three backtest days.
- **Telemetry:** 30 consecutive hours of missing load data is a reliability event in its own right. If this is SCADA or historian loss, the review should record the outage and confirm that state estimation and the operator's displays were not relying on the missing feed.

**What the data cannot support**

- Reserve margin, loss-of-load probability, and N-1 adequacy. None of these can be computed without installed capacity, generation outages, interchange limits, or reserve requirements. The planning peak envelope (134–158 MW) is the figure to test against those inputs.
- Any statement about summer or extreme-weather peaks. There is no temperature data and no summer observation.

## 6. Limitations

- **Seven days, one season, no weather.** Annual conclusions are not supported. Any seasonal, weather-driven, or trend-based claim needs multiple years of data.
- **Holiday confound.** Jan 1 is a holiday, and the gap covers the holiday period. The weekday/weekend comparison includes only Jan 3–4 as weekend days.
- **Timezone.** Timestamps are labelled UTC and are used as given. No local-time conversion was applied.
- **Units.** The file says MW. Energy figures are MW × hours on a 15-minute basis, with no conversion applied to a different unit.

## 7. Recommended next steps

1. Obtain at least three years of 15-minute load history, with the cause of the 30-hour gap, and confirm that the gap was not an SCADA or historian failure.
2. Obtain hourly temperature (or heating and cooling degree days) for the same region, plus calendar data (holidays, weekday type).
3. Build the annual outlook as a weather-normalised peak and energy regression with a trend term, and report weather-driven peaks at 1-in-10 and 1-in-20 years.
4. Add installed capacity, outage schedules, and interchange data to convert the peak envelope into a reserve-margin and loss-of-load view.
5. Add behind-the-meter and distributed-energy data if they are not already netted out of this series.

## Files produced

- `code/analysis.py`: full pipeline (QA, descriptive statistics, backtest, scenarios, figures)
- `out/analysis_stdout.log`: script output
- `outputs/qa_summary.json`, `daily_summary.csv`, `hourly_profile.csv`, `backtest_metrics.csv`, `annual_scenarios.csv`
- `outputs/fig_timeseries.png`, `outputs/fig_profile_backtest.png`
