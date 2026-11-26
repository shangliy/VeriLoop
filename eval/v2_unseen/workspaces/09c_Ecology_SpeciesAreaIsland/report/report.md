# Species–Area Relationship on Islands: Fit, Robustness, and Conservation Implications

## 1. Question

Island biogeography predicts that species richness S increases with habitat area A. Here I (i) model the species–area relationship (SAR) in `data/island_species.csv`, (ii) check how robust the fit is, and (iii) state what it implies for conservation planning, including where it should not be trusted.

## 2. Data

- 25 islands (ids 0–24), with area in km² and species richness.
- Area ranges from 0.570 to 5.324 km² (median 3.30). Richness ranges from 11 to 43 (median 17).
- Pearson r(A, S) = 0.28 on the raw scale. Spearman ρ = 0.65 (p = 0.0004). The raw-scale correlation is weak, and the rank correlation is much stronger. This already hints at outliers (see §4).
- The data contain no replicate sampling, survey effort, distance to mainland, or habitat variables, so the analysis is restricted to area alone.

## 3. Methods

All code is in `code/sar_analysis.py`. Its full stdout is in `out/sar_analysis_log.txt`. The figure is `outputs/sar_fit.png`. The script uses numpy, scipy and matplotlib only (pandas is not installed here).

Three candidate models, all fitted by ordinary least squares:

- **M1, power law (Arrhenius/Preston form):** S = c·A^z, fitted as log10 S = log10 c + z·log10 A. This is the standard SAR model. z is the slope on the log–log scale.
- **M2, linear:** S = a + b·A.
- **M3, logarithmic (Gleason form):** S = a + b·ln A.

Model comparison uses R² and AIC on the natural scale, so all three models are judged on the same data. Robustness is checked in three ways:

1. Cook's distance and studentized residuals on the power-law fit, to find influential islands (rule of thumb: D > 4/n = 0.16).
2. A sensitivity fit with the flagged islands excluded.
3. Leave-one-out cross-validation (LOO), compared against a null model that predicts the mean richness of the training islands.

Uncertainty is given as 95% confidence intervals for slopes and 95% prediction intervals for new islands.

## 4. Results

### 4.1 Fit to all 25 islands

| Model | Parameters | 95% CI | R² (natural scale) | AIC (natural) |
|---|---|---|---|---|
| Power law | c = 14.31, z = 0.220 | z ∈ [0.043, 0.397] | 0.094 | 96.34 |
| Linear | b = 1.31 per km² | b ∈ [−0.64, 3.26] | 0.078 | 96.80 |
| Logarithmic | b = 3.65 per ln-km² | [−0.81, 8.12] | 0.111 | 95.89 |

On the log–log scale the power-law fit has R² = 0.22. None of the three models explains much of the variation, and the slope is imprecise: z is 0.22, but its CI runs from almost zero to 0.40. Since the three models differ by less than 1 AIC unit, the full data do not discriminate among them.

### 4.2 Influential islands

Two islands stand out:

| Island | Area (km²) | Richness | Studentized residual | Cook's D |
|---|---|---|---|---|
| 17 | 3.546 | 43 | +3.38 | 0.30 |
| 3 | 2.002 | 33 | +2.81 | 0.21 |

Both exceed the Cook's D threshold of 0.16, and both have richness far above what their area predicts. Island 17 has about 2.7 times the richness of island 15 (area 3.542 km², richness 16). These two islands account for most of the weak fit. The data cannot say whether they reflect real ecology (for example habitat heterogeneity, proximity to a source pool, or a larger habitat type), sampling effort, or a data-entry problem. This needs checking against the original survey records before any conclusion depends on them.

### 4.3 Sensitivity fit (islands 3 and 17 excluded, n = 23)

| Model | Parameters | 95% CI | R² (natural) | RMSE | AIC (natural) |
|---|---|---|---|---|---|
| Power law | c = 13.46, z = 0.215 | z ∈ [0.147, 0.284] | 0.645 | 1.52 | 25.22 |
| Linear | b = 1.45 per km² | [0.94, 1.95] | 0.629 | 1.55 | 26.23 |
| Logarithmic | b = 3.38 per ln-km² | [2.23, 4.54] | 0.638 | 1.53 | 25.64 |

Without the two outliers, the fit is much tighter (log-scale R² = 0.67, residual SD 0.042 on log10 scale), and the power-law slope is estimated with reasonable precision: z = 0.215 (95% CI 0.15–0.28). The three models now fit almost equally well (natural-scale R² 0.63–0.65). The power law has the lowest AIC, but the margin over the logarithmic model is only 0.4 units, so the data do not clearly favour any functional form.

### 4.4 Out-of-sample prediction (LOO cross-validation)

| Model | LOO RMSE (all 25) | LOO MAE |
|---|---|---|
| Null (mean richness) | 6.67 | 3.98 |
| Power law | 6.33 | 3.28 |
| Logarithmic | 6.37 | 3.57 |
| Linear | 6.52 | 3.74 |

On the full data, the SAR models barely beat the null model at predicting an unseen island. The best of them (power law) reduces error by about 5%. This is the practical meaning of the weak fit in §4.1: area alone predicts an individual island's richness poorly.

### 4.5 Predictions

Sensitivity fit (n = 23), predicted richness with 95% prediction intervals:

| Area (km²) | Predicted S | 95% PI |
|---|---|---|
| 1 | 13.5 | 10.9–16.7 |
| 2 | 15.6 | 12.7–19.2 |
| 5 | 19.0 | 15.5–23.4 |
| 10 | 22.1 | 17.7–27.6 (extrapolation) |
| 25 | 26.9 | 20.9–34.7 (extrapolation) |
| 50 | 31.3 | 23.5–41.6 (extrapolation) |

Full-data fit: predicted S = 12.3 at 0.5 km², 14.3 at 1 km², 20.4 at 5 km². Its intervals are much wider (e.g., 8–25 species at 1 km²).

Predictions for areas above 5.3 km² or below 0.57 km² are extrapolations and should be treated as indicative only.

### 4.6 Habitat loss implications (power law)

For a power-law SAR, habitat reduction by a fraction f leads to proportional species loss 1 − (1 − f)^z. Using the full-data z (0.220; CI 0.043–0.397):

| Habitat reduced by | Expected species loss | Range from z CI |
|---|---|---|
| 10% | 2.3% | 0.5–4.1% |
| 25% | 6.1% | 1.2–10.8% |
| 50% | 14.1% | 2.9–24.1% |
| 75% | 26.3% | 5.8–42.3% |
| 90% | 39.8% | 9.4–59.9% |

The sensitivity-fit z (0.215) gives almost identical losses at 10–50% reduction (differences under 0.5 percentage points), and about 0.8 points lower at 90%.

Equivalently, to retain a given fraction of species at the current richness (power law, full-data z): keep 61% of the habitat to retain 90% of species, 36% to retain 80%, and 4% to retain 50%. The last figure relies on extrapolation far below the smallest island (0.57 km²) and should not be used for planning.

## 5. Discussion

**What the SAR says.** Richness increases with area, and across these islands the best-supported description is a power law with z ≈ 0.22 (sensitivity fit: 0.215, 95% CI 0.15–0.28). A z in this range is typical of island SARs, which is consistent with the classic result that species richness rises slowly with area. In practice, this means each additional unit of area adds fewer species than the one before. Doubling the area of an island adds only about 16% more species (2^0.215 ≈ 1.16), so small losses of habitat cost proportionally fewer species than they remove area.

**Implications for conservation planning.**

1. *Habitat loss costs proportionally fewer species than area.* For z ≈ 0.22, losing half the habitat is expected to remove about 14% of species. The species-count loss is therefore smaller than the area loss. This does not mean habitat loss is cheap: the SAR counts species, not which ones are lost.
2. *The relationship is not a safe guide to the last few percent.* Losing 90% of habitat is expected to remove about 40% of species, and that estimate is the most uncertain (CI roughly 9–60%). The SAR gives a total count and says nothing about which species are lost, so it cannot show whether threatened or specialist species are protected at these levels of loss.
3. *Single-island predictions are imprecise.* Even in the cleaner sensitivity fit, a 1 km² island is predicted to hold 13–14 species with a 95% interval of about 11–17. In the full data the interval is roughly 8–25. Conservation targets for individual sites should therefore be set with ranges, not point values.
4. *Outliers matter for targets.* Islands 17 and 3 hold far more species than their area predicts. Whatever the cause, these islands are candidates for priority protection if their richness is real. Equally, if they are data errors, a planning target built on the full-data fit would overstate the species that small islands can hold.
5. *SLOSS.* A power law with z < 1 predicts that, at fixed total area, several small patches collectively hold more species than one large patch (the sum of S over patches exceeds S for the combined area). The data cannot resolve the SLOSS debate, because they contain no information on species shared between islands or on extinction dynamics, and the sum over patches double-counts shared species. This should be stated explicitly in any planning argument that uses the SAR this way.
6. *Extrapolation risk.* The SAR is fitted on islands of 0.57–5.3 km². Predictions for much larger reserves (the 10–50 km² extrapolations above) assume that the same power law continues. Real reserves differ in habitat quality, edge effects, and isolation, none of which this dataset contains.

## 6. Limitations

- **Small sample and outliers.** With 25 islands, the full-data slope is poorly estimated (CI 0.04–0.40), and two islands dominate the residuals. The sensitivity analysis is post-hoc: the exclusion was chosen after seeing the diagnostics. The full-data and sensitivity results should therefore be read together, and the sensitivity result should be confirmed on independent data.
- **Area is the only predictor.** Isolation, habitat diversity, and sampling effort are absent. These are known to affect island richness and may explain the residual variation (including islands 3 and 17).
- **Equilibrium assumption.** SARs assume richness is near equilibrium with area. If islands are still losing or gaining species (extinction debt or colonisation lag), the observed richness will misstate the long-run value, and the fitted z may be biased.
- **No uncertainty on the area measurements** or on richness counts is provided, so the errors in the regression are only the residual scatter.
- **Model form.** The power law is preferred for theoretical reasons and has the lowest AIC after exclusion. The data do not clearly distinguish it from linear or logarithmic forms (§4.3).

## 7. Conclusion

Richness increases with island area, but in this dataset the relationship is weak overall and is driven by two high-richness islands (17 and 3). Excluding them, the power-law SAR has z = 0.215 (95% CI 0.15–0.28), and it explains about two-thirds of the variance in richness. For conservation planning, this implies that habitat loss removes proportionally fewer species than area, but that the relationship becomes unreliable for severe losses and for individual small sites. Targets should be expressed as ranges, and the outlier islands should be checked against their original survey records before they are used to set priorities.

## Deliverables

- `code/sar_analysis.py`: full analysis (fits, diagnostics, LOO, predictions, loss table, figure).
- `out/sar_analysis_log.txt`: stdout from the final run.
- `outputs/sar_fit.png`: scatter with the three fitted curves (outliers in red) and log–log fit.
