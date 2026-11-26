# Air Quality and Respiratory Health: Policy Brief

**Basis:** 120-day daily panel (`data/daily_panel.csv`): PM2.5, respiratory clinic visits, heating degree days, influenza index, school-holiday indicator. Full methods and results are in `report/report.md`.

## Bottom line

The panel gives weak support for a PM2.5–respiratory link and strong support for seasonal and influenza drivers of clinic demand. It is not sufficient to set an air-quality threshold or to quantify the health benefit of PM2.5 reductions.

## Key findings

| Finding | Estimate | Confidence |
|---|---|---|
| Same-day PM2.5 vs visits | +4.7 visits/day per +10 µg/m³ (≈4% of mean) | 95% CI ≈ +0.3 to +9.0; marginal |
| PM2.5 at lags 1–3 | Positive or negative, CIs include zero | Not supported |
| Heating degree days vs visits | +3.2 visits per degree-day | Strong |
| Influenza index vs visits | +41 visits per unit index (≈ +8 per 0.2) | Strong |
| School holiday vs visits | −4.7 (CI −10.9 to +1.5); 4 holiday days | Uninformative |
| PM2.5 alone, share of daily variance | R² = 0.014 | Negligible |

## Recommendations

1. **Do not adopt a clinic-level PM2.5 action threshold on this evidence.** The same-day effect is small and not robust across lags.
2. **Plan respiratory surge capacity around cold-weather and influenza signals**, which explain far more daily variation than PM2.5 in this panel.
3. **If a PM2.5-triggered protocol is trialled** (e.g. extra staffing or public advice on high-PM days), evaluate it prospectively with a pre-specified lag and outcome before scaling.
4. **Collect better data before a policy decision:** calendar dates; clinic or catchment identifiers; monitor-sourced PM2.5 with missing values flagged separately from zeros; clinic capacity; visit-type codes; several years spanning multiple seasons.

## Caveats

- The file has no dates, so weekday and seasonal patterns cannot be modelled directly.
- Zeros in PM2.5 (8 days) and flu index (6 days) may be missing-data codes. Dropping PM2.5 zeros leaves the estimate essentially unchanged.
- The lag-0 result was identified after comparing lags 0–3; with 120 days, it should be treated as a hypothesis.
- Associations are not causal estimates.
