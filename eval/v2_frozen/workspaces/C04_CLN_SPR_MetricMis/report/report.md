# Symbolic Pattern Reasoning: predicate-tree experiment

**Result.** The selected tree achieves test accuracy 70.00%, color-weighted accuracy (CWA) 63.5402%, and shape-weighted accuracy (SWA) 69.9986%. CWA is 1.4598 percentage points below the supplied 65.0% reference. SWA is 0.00145 percentage points below the supplied 70.0% reference, a numerical tie at the reference's stated precision. These are point-score comparisons; the reference predictions, uncertainty and evaluation conditions are unavailable, so no paired comparison is possible.

A test-example percentile bootstrap gives a 95% interval of 62.5738%–64.5371% for this model's CWA and 69.1159%–70.9370% for SWA, using 2000 resamples and seed 2026. These intervals describe test-sample variability conditional on the fitted model; they do not quantify uncertainty in the reference scores.

## Data and method

The benchmark has 20000 training, 5000 development and 10000 test examples, each of length 6. Training and development labels are balanced; test has 5016 positive and 4984 negative labels. The logged vocabulary contains the same 16 shape-color tokens in each split.

The procedure constructs 260 Boolean features: positional color and shape, counts and thresholds, even counts, first-occurrence ordering, and length indicators. Ordering is false when either symbol is absent. A greedy decision tree maximizes squared-error reduction, with at least 25 training examples per child; leaves predict the majority label, with ties positive. The recorded experiment sweeps maximum depths 1 through 8 with other settings fixed. Development unweighted accuracy selected depth 5, breaking ties toward shallower trees. Depths 5–8 also tie at 100.000% on both development weighted metrics, so using either of those metrics would not change that tie. Perfect development performance does not establish performance under the test distribution shift. The script loads test after selection and evaluates only the selected model. The available record does not establish whether earlier feature sets or settings were explored.

CWA and SWA weight each example by its count of distinct colors and shapes respectively. The procedure and evidence are in [experiment.py](../code/experiment.py), [experiment.txt](../out/experiment.txt), [model.json](../out/model.json), and the generated [tree description](../out/model_description.txt).

## Development selection

The table reports percentages; the log also contains unrounded fractions.

| Maximum depth | Train accuracy | Train CWA | Train SWA | Dev accuracy | Dev CWA | Dev SWA |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 87.745 | 87.764 | 88.347 | 88.020 | 88.012 | 88.647 |
| 2 | 97.005 | 97.012 | 97.079 | 97.040 | 97.053 | 97.093 |
| 3 | 99.145 | 99.146 | 99.122 | 99.060 | 99.103 | 99.012 |
| 4 | 99.615 | 99.607 | 99.668 | 99.640 | 99.652 | 99.686 |
| 5 | 100.000 | 100.000 | 100.000 | 100.000 | 100.000 | 100.000 |
| 6 | 100.000 | 100.000 | 100.000 | 100.000 | 100.000 | 100.000 |
| 7 | 100.000 | 100.000 | 100.000 | 100.000 | 100.000 | 100.000 |
| 8 | 100.000 | 100.000 | 100.000 | 100.000 | 100.000 | 100.000 |

The fitted rule accepts when the first token is red, exactly two triangles occur, the first triangle precedes the first circle, a square is present, and the first square does not precede the first diamond. The ordering condition requires a circle to be present; the last condition holds when the diamond is absent. This is a learned rule, not independently verified ground truth.

## Descriptive diagnostics

| Distinct colors | Train n (negative, positive) | Dev n (negative, positive) | Test n | Test accuracy |
|---:|---:|---:|---:|---:|
| 1 | 17 (7, 10) | 4 (2, 2) | 10 | 100.0000% |
| 2 | 1772 (917, 855) | 477 (253, 224) | 917 | 100.0000% |
| 3 | 10478 (5237, 5241) | 2643 (1310, 1333) | 5223 | 100.0000% |
| 4 | 7733 (3839, 3894) | 1876 (935, 941) | 3850 | 22.0779% |

The training and development data include many examples with all four colors, so the learned rule is not confined to examples with at most three colors. In the four-color test group, the confusion matrix (actual rows, predicted columns) is:

| Actual label | Predicted 0 | Predicted 1 |
|---|---:|---:|
| 0 | 437 | 1492 |
| 1 | 1508 | 413 |

Errors occur in both directions; the model does not simply predict one class throughout this group. This pattern describes a mismatch between the learned rule and test labels, but does not establish its cause. Greater color diversity receives greater CWA weight, so this group's poor accuracy pulls CWA below ordinary accuracy. The one-color test group is small.

The log also reports shape-diversity groups: their accuracies are 66.6667%, 67.4107%, 70.5229%, and 69.7520% for groups with 1, 2, 3, and 4 distinct shapes, respectively. These breakdowns are post-evaluation descriptions, not model-selection evidence.

Generalization across vocabulary sizes, sequence lengths, and rule complexities is not established: the observed dataset uses one length and vocabulary and has no per-example rule-complexity metadata. The test result shows substantial failure on the available distribution. Evaluating a revised algorithm requires a new untouched test set; these diagnostics must not be used to tune a replacement and then claim an unbiased result on this same test set.
