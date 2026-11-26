# SPR benchmark selection: test accuracy vs published SOTA (4 of 20 codes)

## 1. Selection rationale

The task asks for 4 of the 20 binary SPR benchmarks. Benchmarks are identified only by opaque codes, and the registry gives only published SOTA accuracy and split sizes (400 / 100 / 200 for every code). I chose the four codes **before running any model**, using only registry SOTA and train/validation statistics (`code/profile_train_val.py`, `out/profile_train_val.log`). Test labels were not used.

Rule: cover the SOTA range (the 20 codes sorted by SOTA, with one pick from the top, upper-middle, lower-middle and bottom bands), and vary sequence length and vocabulary size so the four picks are not all structurally alike.

| Code | Published SOTA (%) | Band | Seq. length | Vocab size | Train pos. rate | Val majority acc. |
|---|---|---|---|---|---|---|
| ZOBKB | 95.2 | top | 6 | 8 | 0.500 | 0.53 |
| LHVPV | 87.1 | upper-middle | 12 | 16 | 0.490 | 0.50 |
| ILULR | 78.0 | lower-middle | 4 | 4 | 0.562 | 0.51 |
| FDLOT | 60.4 | bottom | 12 | 16 | 0.490 | 0.55 |

Selecting by SOTA band is a coverage choice. It is not evidence about how hard each code is for a given model.

## 2. Method

- **Data:** train on `{CODE}_train.csv` (400 rows). Select the model family and hyperparameters on `{CODE}_val.csv` (100 rows). Score `{CODE}_test.csv` (200 rows) once. One model per code, no cross-benchmark training.
- **Features** (`code/run_experiment.py`): positional one-hot tokens; bag-of-token counts; shape and color counts (the first and second characters of each token); and pairwise equality indicators for tokens, shapes and colors across all position pairs, plus their sums.
- **Candidates** (19 configurations): logistic regression (C ∈ {0.01, 0.1, 1, 10}); random forest with 300 trees (max depth ∈ {None, 6, 12}, min leaf ∈ {1, 5}); histogram gradient boosting (learning rate ∈ {0.05, 0.1}, depth ∈ {2, 3}); k-NN (k ∈ {1, 3, 5, 9}).
- **Selection:** highest validation accuracy, with ties going to the earlier candidate. The chosen configuration is refit on train only and scored on test.
- **Uncertainty:** 95% Wilson intervals on test accuracy. With n = 200, a half-width of about ±7 points is typical.
- **Comparison:** published SOTA is a reference number. Its protocol and model budget are not known to match this setup, so the gap is indicative only.

Single seed (0). No repeated runs.

## 3. Results

| Code | SOTA (%) | Selected config | Val acc. (%) | **Test acc. (%)** | Test 95% CI | Gap vs SOTA (pp) | Test majority (%) |
|---|---|---|---|---|---|---|---|
| ZOBKB | 95.2 | k-NN (k=3) | 61.0 | **45.0** | [38.3, 51.9] | −50.2 | 50.5 |
| LHVPV | 87.1 | k-NN (k=5) | 54.0 | **44.0** | [37.3, 50.9] | −43.1 | 54.5 |
| ILULR | 78.0 | Random forest (unlimited depth, leaf=1) | 93.0 | **90.0** | [85.1, 93.4] | +12.0 | 54.0 |
| FDLOT | 60.4 | Random forest (unlimited depth, leaf=5) | 63.0 | **52.0** | [45.1, 58.8] | −8.4 | 54.0 |

Source: `out/results_test_vs_sota.csv`. Full validation sweeps for every candidate are in `out/run_experiment.log`.

## 4. Discussion

**ILULR is the only code the approach learns.** With 4 positions and 4 tokens, a random forest reaches 90% test accuracy (CI 85–93), above both the majority baseline and the published 78.0%. Its 45 features cover the token and equality relations directly, and the rule is apparently simple enough to recover from 400 examples. This is the one place where the comparison to SOTA is favorable, and even here it is a single-seed result on 200 test points.

**ZOBKB and LHVPV are not learned.** Validation accuracy stays between 37% and 61% across all 19 configurations. Test accuracy is 45% and 44%, below the majority-class baseline (50.5% and 54.5%). Below-chance test accuracy after validation-based selection suggests the chosen configuration is fitting noise. It does not mean the labels are anti-correlated with the input. The published SOTA for these codes (95.2% and 87.1%) is far above what this feature set and training size achieve. Two explanations are consistent with the data and cannot be separated from this experiment:
1. The labels depend on a symbolic rule outside the features used here (for example, a higher-order or order-dependent relation). Their SOTA implies the rule is learnable, but these models do not find it from 400 examples.
2. The published SOTA used a different training budget, architecture or data, so the gap is partly a protocol difference. The registry does not say which.

**FDLOT is near chance.** Test accuracy is 52% (CI 45–59), within the interval of the 54% majority baseline and 8.4 pp below the 60.4% SOTA. This is a weak result from a bottom-band code, so it is not evidence that the code is hard for every method.

**Caveats.**
- With n = 200 per test set, ±7 pp is the typical uncertainty. Differences of a few points between configurations are not meaningful.
- Validation sets are also 100 items, so model selection is noisy. Picking from 19 configurations on 100 validation items can select a configuration that does not generalize, which probably explains the sub-majority test results for ZOBKB and LHVPV.
- I did not iterate on features after seeing test results, so these numbers are a single first attempt. Better features or a sequence model could change the ZOBKB, LHVPV and FDLOT results. I did not run that search, since it would have required reusing the test split as a development set.

**Bottom line.** Of the four codes, one (ILULR) is learned well with simple symbolic features and beats its published SOTA on this split. Three (ZOBKB, LHVPV, FDLOT) are not learned at all, and the two with high SOTA fall far short of it. Accuracy against SOTA on these hand-crafted codes depends heavily on the code, so a benchmark-level comparison should not be taken from one or two codes.

## 5. Files

- `code/profile_train_val.py`: train/validation profiling used for selection (no test data).
- `code/run_experiment.py`: features, candidate sweep, refit and test scoring.
- `out/profile_train_val.log`, `out/run_experiment.log`: stdout of the two scripts.
- `out/results_test_vs_sota.csv`: final table.
- `out/*.stderr.log`: stderr, which contains only NumPy/pandas binary-compatibility warnings from the conda environment. The results are unaffected.
