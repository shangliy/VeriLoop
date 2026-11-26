# Irrigation and Yield in the Plot-Year Panel: Associational Analysis

## Summary

- The panel has 80 plots, one row each. It has **no year, time, or program-enrollment variable**, so the file cannot identify an irrigation *program* effect (no pre/post, no treated/untreated comparison, no difference-in-differences). What it supports is a cross-sectional association analysis of yield on irrigation volume, controlling for fertilizer, groundwater quota enforcement, and rainfall.
- Irrigation volume is positively associated with yield. Bivariate slope: +0.17 t/ha per 100 m³ (p = 0.007). After adjustment for fertilizer, quota enforcement, and rainfall, the slope is **+0.197 t/ha per 100 m³ (HC1 SE 0.038, p < 0.001; bootstrap 95% CI [0.12, 0.27])**. At the sample SD of irrigation (121 m³), that is roughly 0.24 t/ha, or about 5–6% of mean yield (4.29 t/ha).
- Groundwater quota enforcement is the strongest correlate of yield: +1.44 t/ha per full unit of the 0–1 enforcement score (≈ +0.43 t/ha per SD). Rainfall is also strongly associated (+0.13 t/ha per 100 mm). Fertilizer shows no association (+0.03 t/ha per 10 kg, p = 0.48).
- The irrigation slope is larger where quota enforcement is weakest (interaction p = 0.076, not significant at 5%). Irrigation's association with yield appears in every enforcement tercile, but the pattern is only suggestive.
- These are **associations, not causal effects**. Irrigation is not randomly assigned, and the data cannot rule out confounding by unobserved plot quality, soil, or management.

## Data

- File: `data/field_year_panel.csv` (read-only), 80 rows, columns `plot_id`, `yield_t_ha`, `irrigation_m3`, `fertilizer_kg`, `groundwater_quota_enforcement`, `rainfall_mm`. No missing values and no duplicate plot IDs.
- Descriptives (from `out/analysis_log.txt`):

| Variable | Mean | SD | Min | Max |
|---|---|---|---|---|
| yield (t/ha) | 4.29 | 0.66 | 2.65 | 5.54 |
| irrigation (m³) | 213.5 | 120.9 | 9.7 | 396.1 |
| fertilizer (kg) | 102.1 | 11.2 | 80.7 | 119.6 |
| quota enforcement (0–1) | 0.50 | 0.30 | 0.02 | 0.99 |
| rainfall (mm) | 395.8 | 223.9 | 4.9 | 799.7 |

- Regressor collinearity is low. The largest pairwise correlation is fertilizer vs. quota enforcement (r = −0.24, p = 0.03). Irrigation is uncorrelated with rainfall (r = 0.06) and nearly so with quota enforcement (r = −0.12, p = 0.30), so irrigation's coefficient is not absorbed by these controls.

## Methods

Script: `code/analysis.py` (numpy/scipy only, fixed seed). Stdout: `out/analysis_log.txt`.

1. Pearson correlations of yield with each regressor.
2. OLS of yield on irrigation alone (Model 1).
3. OLS adding fertilizer, quota enforcement, and rainfall (Model 2, the main specification). Standard errors are HC1 heteroskedasticity-robust.
4. Model 2 plus an irrigation × quota-enforcement interaction, with quota centered (Model 3).
5. Model 2 plus a quadratic irrigation term (Model 4), to check curvature.
6. Plot-level nonparametric bootstrap (2000 resamples) for the Model 2 irrigation coefficient.
7. Stratified descriptives by irrigation terciles and quota-enforcement terciles (Kruskal–Wallis tests), with the irrigation slope re-estimated within each quota tercile.

Units: irrigation is expressed per 100 m³, fertilizer per 10 kg, rainfall per 100 mm, and quota enforcement is kept on its 0–1 scale.

## Results

### Model 2 (main specification): yield ~ irrigation + fertilizer + quota + rainfall

| Term | Coef | HC1 SE | t | p |
|---|---|---|---|---|
| const | 2.296 | 0.505 | 4.55 | <0.001 |
| irrigation (per 100 m³) | **0.197** | 0.038 | 5.18 | <0.001 |
| fertilizer (per 10 kg) | 0.032 | 0.045 | 0.71 | 0.48 |
| quota enforcement (0–1) | **1.443** | 0.161 | 8.98 | <0.001 |
| rainfall (per 100 mm) | **0.133** | 0.021 | 6.33 | <0.001 |

n = 80, R² = 0.603, adjusted R² = 0.582.

Model 1 (irrigation alone): slope 0.169 per 100 m³ (SE 0.061, p = 0.007), R² = 0.095. Adding the other regressors roughly doubles the fit (R² from 0.10 to 0.60) and leaves the irrigation slope essentially unchanged, which suggests the irrigation association is not an artifact of rainfall or enforcement.

### Robustness

- **Bootstrap:** the irrigation coefficient in Model 2 has a 95% CI of [0.121, 0.271] across 2000 plot-level resamples; no draw was ≤ 0.
- **Curvature (Model 4):** the linear term is −0.114 (SE 0.189) and the quadratic is +0.077 (SE 0.043, p = 0.08). The implied marginal effect at mean irrigation is about 0.21 t/ha per 100 m³, close to the main estimate. The evidence for a nonlinear response is weak.
- **Interaction (Model 3):** irrigation × centered quota = −0.201 (SE 0.111, p = 0.076). The implied irrigation slope is about 0.35 t/ha per 100 m³ at the lowest enforcement, and it falls toward zero as enforcement rises. The sign is consistent with irrigation mattering most where groundwater governance is weak, but the interaction is not significant at 5%.

### Stratified views

| Irrigation tercile | n | Mean yield (t/ha) | Mean quota | Mean rain (mm) |
|---|---|---|---|---|
| Low (≤ 142 m³) | 27 | 4.01 | 0.54 | 364 |
| Mid (142–293 m³) | 26 | 4.30 | 0.50 | 422 |
| High (> 293 m³) | 27 | 4.56 | 0.47 | 403 |

Kruskal–Wallis across irrigation terciles: H = 8.27, p = 0.016. Higher-irrigation plots yield more on average, but they also have slightly lower quota enforcement, so the unadjusted gap (+0.54 t/ha) overstates the adjusted association.

| Quota-enforcement tercile | n | Mean yield (t/ha) | Mean irrigation (m³) |
|---|---|---|---|
| Low | 27 | 3.97 | 236 |
| Mid | 26 | 4.20 | 214 |
| High | 27 | 4.70 | 191 |

Kruskal–Wallis across quota terciles: H = 17.56, p < 0.001. Higher enforcement goes with higher yield and lower irrigation use. Irrigation is therefore not making up for weak enforcement in this sample. Plots under strong enforcement do well on less water.

Within-stratum irrigation slopes (per 100 m³): low enforcement +0.35 (r = 0.61, p < 0.001); mid +0.16 (r = 0.31, p = 0.13); high +0.15 (r = 0.36, p = 0.06).

## Discussion

**What the data show.** Across plots, more irrigation goes with higher yield, and the association holds after controlling for fertilizer, groundwater quota enforcement, and rainfall. Groundwater quota enforcement is the largest single correlate of yield in this sample. Its association is stronger than irrigation's per unit of standard deviation (about 0.43 vs. 0.24 t/ha per SD), and the two are nearly uncorrelated, so the enforcement association is not simply an irrigation effect.

**What the data cannot show.** The task refers to irrigation program outcomes, but the file has no program indicator, no year, and no before/after structure. Two things follow:

1. The estimates are cross-sectional. They do not show that enrolling a plot in an irrigation program or adding water raises yield. Water use may track plot quality, soil, or management, which are unobserved here. The adjusted coefficient is best read as a conditional association.
2. Program-evaluation designs (difference-in-differences, event study, or matching on pre-program yields) would need a plot-year structure with a year variable and a treatment-timing variable. Those are absent. The results should not be presented as program impact.

**Interpretation of the enforcement interaction.** The data hint that irrigation matters more where enforcement is weak. A plausible reading is that, under weak quota control, extra water is a bigger lever on yield, while under strong control, yield is already high and water use is lower. This is one-sided evidence with p = 0.076, and it should be treated as a hypothesis for a designed study, not a finding.

**Quality checks.** The model is well-specified in the sense that the controls are not collinear with irrigation, residual curvature is weak, and the bootstrap confirms sign and significance. The main limits are small n (80), one-cycle cross-section, and possible omitted variables. Heteroskedasticity-robust SEs are used throughout.

## Limitations

- No time or year dimension. The filename says "plot-year" but the file contains one row per plot, so the cross-section cannot separate year effects from plot effects.
- No program or treatment indicator. "Irrigation program outcomes" are proxied by irrigation volume, which is a continuous input, not an assignment.
- Possible reverse causality and selection: farmers may apply more water to plots with higher expected yield.
- The quota-enforcement variable is a 0–1 score with unknown construction. Its meaning and measurement error are not documented.
- Yield is in t/ha. The file does not say whether it is harvested or potential yield.
- Small sample: confidence in the interaction and quadratic terms is limited.

## Conclusion

In this 80-plot panel, irrigation volume and groundwater quota enforcement are both positively associated with yield, and rainfall is too. Holding those factors fixed, each additional 100 m³ of irrigation is associated with about 0.20 t/ha more yield (95% bootstrap CI 0.12–0.27). Because the file has no year or program variable, these figures describe associations, not the effect of an irrigation program. A causal estimate would require plot-year data with program timing and a pre-program baseline.

## Files

- `code/analysis.py`: analysis script (runs with `python3 -I code/analysis.py` from workspace root)
- `out/analysis_log.txt`: full stdout of the analysis
- `report/report.md`: this report
- `irrigation_impact.md`: copy of this report, at the workspace root as the task requested
