# REIT Index Returns and Inflation: Association Analysis

## 1. Summary

- Across 40 quarters, quarterly REIT index return and year-over-year inflation are **strongly and positively associated** (Pearson r = 0.931, 95% CI [0.87, 0.96]; Spearman ρ = 0.931).
- The association is **contemporaneous**. Lagged correlations at ±1 to ±4 quarters are small (|r| ≤ 0.21) and not significant, so the data show no evidence of a predictive lead-lag relationship in either direction.
- An OLS slope of **0.156** (HAC SE 0.006, p < 0.001, R² = 0.87) says each 1-percentage-point rise in inflation coincides with about 0.16 higher REIT index return in the data's units.
- The result is stable across halves of the sample, robust to dropping the most influential quarter, and holds in a block-bootstrap and rank-based check.
- These are **associations, not causal effects**. With 40 observations, no date column, and undocumented units, the magnitudes should not be used for portfolio sizing or policy calibration without the data's provenance.

## 2. Data

- File: `data/reit_macro_quarterly.csv` (read-only), 40 rows, columns `quarter` (0–39), `inflation_yoy` (%, year-over-year), `reit_index_return`.
- No calendar dates, no series definitions, and no unit documentation were supplied. I make no assumptions about the sample period.
- Descriptives:

| Variable | Mean | SD | Min | Median | Max |
|---|---|---|---|---|---|
| inflation_yoy (%) | 2.31 | 0.75 | 0.65 | 2.30 | 4.18 |
| reit_index_return | 0.373 | 0.125 | 0.142 | 0.364 | 0.643 |

- Serial dependence: AR(1) of inflation ρ₁ = 0.11; AR(1) of REIT returns ρ₁ ≈ 0.00. Serial correlation is therefore low, but I still report HAC and bootstrap inference.
- Units: the REIT values (0.14–0.64) are too large to be plain quarterly total returns in decimal form. They are more plausibly annualized rates or a differently scaled index. The magnitude statements below are in data units.

## 3. Methods

All code is in `code/association_analysis.py`. Its stdout is in `out/association_analysis_log.txt`. The script uses numpy and scipy only (statsmodels is not installed here), with a fixed random seed.

1. **Contemporaneous correlation**: Pearson and Spearman, with Fisher-z 95% CI.
2. **Serial-dependence-robust inference**: circular block bootstrap (block length 4, B = 10,000) for the Pearson CI.
3. **OLS**: REIT_t = α + β·inflation_t + ε, with Newey–West (Bartlett kernel, 4 lags) HAC standard errors.
4. **Lead/lag structure**: cross-correlations for k = −4…+4, and a lagged regression REIT_t on inflation_{t−1}.
5. **Regime split**: inflation ≥ 3.0% (n = 6) vs. < 3.0% (n = 34), Welch t-test and Mann–Whitney U test. The 3.0% cutoff is my choice, not a data-driven one.
6. **Stability**: correlation in the first and second halves (n = 20 each).
7. **Influence**: leave-one-out correlation range, and Cook's distance from the OLS fit.

## 4. Results

### 4.1 Contemporaneous association

| Statistic | Value |
|---|---|
| Pearson r | 0.931 (95% Fisher CI [0.872, 0.963]), p ≈ 3×10⁻¹⁸ (iid p-value) |
| Block-bootstrap 95% CI for r | [0.875, 0.961] |
| Spearman ρ | 0.931, p ≈ 4×10⁻¹⁸ |

The rank correlation equals the linear correlation, so the association is not driven by a few extreme values or by a non-linear outlier pattern.

### 4.2 OLS (HAC SE)

| Term | Coef. | HAC SE | p |
|---|---|---|---|
| Intercept | 0.0137 | 0.0159 | — |
| Inflation (pp) | 0.1557 | 0.0062 | < 0.001 |

R² = 0.866; 95% CI for the slope [0.143, 0.168].

### 4.3 Lead/lag structure

| k (quarters) | −4 | −3 | −2 | −1 | 0 | +1 | +2 | +3 | +4 |
|---|---|---|---|---|---|---|---|---|---|
| r(infl_{t−k}, REIT_t) | −0.19 | −0.18 | −0.15 | +0.04 | **+0.93** | +0.05 | −0.05 | −0.19 | −0.21 |

- The only large correlation is at k = 0.
- At k = −1 and +1, which is where a short-run lead or lag would appear, |r| ≤ 0.05.
- Lagged regression, REIT_t on inflation_{t−1}: β = 0.009 (HAC SE 0.031, p = 0.78, R² = 0.003).
- The |r| threshold for significance at 5% with n = 40 is about 0.31, so the k ≠ 0 values are all below it.

### 4.4 Regime split (inflation ≥ 3.0% vs < 3.0%)

- High-inflation quarters (n = 6): mean REIT return 0.548, median 0.524.
- Low-inflation quarters (n = 34): mean 0.343, median 0.330.
- Welch t = 6.13 (p = 0.0001); Mann–Whitney p = 0.0006.
- The high-inflation group is small, so this contrast relies on six observations. It is consistent with the regression but is not a separate finding.

### 4.5 Stability and influence

- First half (n = 20): r = 0.875; second half (n = 20): r = 0.959. Both p < 0.001.
- Leave-one-out r ranges from 0.921 (dropping quarter 27, the highest-inflation point at 4.18%) to 0.938 (dropping quarter 8).
- Top Cook's distances are quarters 8 (0.13), 36 (0.13) and 24 (0.09). None is dominant. Dropping quarter 8 gives r = 0.938.

## 5. Discussion

### 5.1 Interpretation

Inflation and REIT index returns move together almost one-for-one in the same quarter. The relationship is strong, linear, stable across sub-periods, and not driven by any single observation. This matches the common view that listed real estate is sensitive to the inflation environment. The most likely mechanisms are (i) rents and property values that adjust with the price level, and (ii) the interest-rate channel, in which inflation and rates move together and affect REIT valuations.

The absence of lead or lag structure is informative. In this sample, REIT returns do not anticipate inflation, and inflation does not forecast REIT returns one quarter ahead. A same-quarter co-movement of this size is more consistent with a shared driver or with a coincident data construction than with a slow-moving transmission. The data cannot separate these.

### 5.2 Caveats

1. **Association, not causation.** A common driver (rates, growth, or a shock) could produce the co-movement. A regression on two observed series does not identify the direction.
2. **Small sample.** Forty quarters give a few effective degrees of freedom for regime-level comparisons. The high-inflation group has n = 6.
3. **Undocumented series.** Without dates, definitions, or units, the sample period, the REIT index construction (price or total return), and the inflation source are unknown. The very high same-quarter correlation for real series is unusual, so the construction and any timing alignment should be checked before the numbers are used.
4. **Overlapping-window concern.** If `inflation_yoy` is a rolling four-quarter change, consecutive values share information and the effective sample is smaller than 40. The low AR(1) of 0.11 suggests this is not the case here, but it cannot be confirmed from the file.
5. **Regime cutoff.** The 3.0% threshold is an analyst choice. Other cutoffs would change the group sizes and means.

### 5.3 Implications for portfolio practice

- **Inflation sensitivity is material and should be measured and stated.** A slope of this size implies REIT allocations carry sizeable exposure to the inflation factor. Practitioners should track that exposure rather than treat REITs as a stable inflation hedge by default.
- **Same-quarter co-movement limits diversification value against inflation shocks.** If REIT returns and inflation rise together contemporaneously, REITs add little protection in the quarter an inflation shock hits. The benefit would have to come from longer horizons or from real-asset characteristics not captured here.
- **Stress scenarios.** The high-inflation regime is where REIT returns were highest in this sample, but this group is tiny. Scenario analysis should not assume the same pattern holds under a rapid rate-driven inflation shock, which the data do not cover.

### 5.4 Implications for policy practice

- **Monitoring.** Because real-estate returns track inflation contemporaneously, REIT performance is a coincident signal rather than a leading indicator of inflation in this sample. Policymakers should not read a REIT rally as evidence that inflation is about to rise.
- **Cross-asset transmission.** The strong same-period link suggests that financial-conditions measures that include listed real estate may reflect inflation developments quickly. Any such use should be validated with a longer, dated series.

### 5.5 What would change these conclusions

- Dated, documented series over a long horizon, to test whether the same-quarter association persists across regimes and periods.
- Real (not nominal) REIT returns and a clear definition of the return horizon (quarterly vs. annualized).
- A multivariate specification including interest rates, growth, and a real-estate-specific shock, to test whether inflation's association survives controls for the rate channel.

## 6. Limitations of this analysis

- Association analysis only. No causal identification, no instrument, no event study.
- Univariate. Omitted variables (rates, growth, credit conditions) are not controlled for.
- The sample is 40 quarters without dates, so no statement about specific historical periods is made.

## 7. Reproducibility

- Script: `code/association_analysis.py` (run with `python3 -I code/association_analysis.py`).
- Log: `out/association_analysis_log.txt`.
- The bootstrap and permutation draws use a fixed seed, so the results reproduce exactly.
