# Symbolic Pattern Reasoning: decision-tree experiment

**Result.** The selected symbolic decision tree achieved **80.00% test accuracy**, matching the task's supplied **80.0% SOTA reference** (difference: **0.00 percentage points**). It did not demonstrate an improvement over that reference. Its training accuracy was **100.00%**, while development accuracy was **80.00%**, indicating a substantial generalization gap. The source and evaluation protocol of the supplied reference are not independently verified here, so this is a comparison to the stated figure rather than a controlled head-to-head experiment.

## Data and experimental design

The local SPR_BENCH files contain **20,000 training**, **5,000 development**, and **10,000 test** examples. All observed sequences in each split have **16 tokens**. Training has **10,000** examples of each class; development has **2,522 reject** and **2,478 accept**, and test has **5,104 reject** and **4,896 accept**. Thus the stated exact class balance does not hold for the observed development and test files. Only one benchmark is available. There is no evidence here for generalization across varying vocabulary sizes, sequence lengths, rule complexities, or independently generated benchmarks.

Each token is parsed into its shape and optional color. Binary features represent shape and color counts, count thresholds and parity; shape and color at each position; and the relative order of first occurrences. Missing symbols are assigned a position after the sequence for order comparisons. A greedy binary classification tree uses the features to minimize weighted Gini impurity, with a minimum leaf size of **20**. The feature extractor is designed around the specified shape and color vocabulary and considers positions through **16**; conclusions are limited to that setting.

We trained separate trees on the training split with maximum depths listed below. The selection criterion was highest development accuracy, with the first candidate retained on ties. An always-accept classifier is included as a simple contextual baseline. The chosen depth was fixed before opening the test split; the selected model was evaluated on test once. There was no cross-benchmark training.

| Maximum depth | Train accuracy | Dev accuracy |
|---:|---:|---:|
| 1 | 93.635% | 75.72% |
| 2 | 98.700% | 78.96% |
| 3 | 99.800% | 79.80% |
| 4 | 99.800% | 79.80% |
| 5 | 100.000% | 80.00% |
| 6 | 100.000% | 80.00% |
| 8 | 100.000% | 80.00% |
| Always accept | 50.000% | 49.56% |

## Selected model and test results

The depth-**5** tree first checks whether the triangle count is exactly **2**, whether the first token is red, and whether the first triangle precedes the first circle. Failure of any of these checks leads to rejection. For sequences passing them, the remaining tree distinguishes the order of the first square and diamond and whether the diamond count is zero. The saved tree includes its node counts and exact branches; the learned rule is descriptive of this fitted model and need not be the benchmark's true generation rule.

| Metric | Selected model |
|---|---:|
| Train accuracy | 100.00% |
| Development accuracy | 80.00% |
| Test accuracy | 80.00% |
| Test accuracy, 95% Wilson interval | 79.2046%–80.7724% |
| Test sensitivity (accept recall) | 80.6373% |
| Test specificity (reject recall) | 79.3887% |
| Supplied SOTA accuracy | 80.0% |

The test confusion matrix contains **4,052 true rejects**, **1,052 false accepts**, **948 false rejects**, and **3,948 true accepts**. The interval quantifies binomial sampling uncertainty under an independent-sample assumption; it does not capture model-selection uncertainty or any dependence among examples.

## Discussion and reproducibility

The tree discovers a highly predictive conjunction in training, but its large train-to-dev and train-to-test gaps mean that perfect training fit is not evidence of a generally valid hidden rule. The split discrepancy could reflect changes in generation or other dataset properties; the available evidence does not establish its cause. The task's requested broad robustness and improvement over SOTA therefore remain unproven. No additional benchmarks or experimental variants were selected using test performance.

Run `OPENBLAS_NUM_THREADS=1 python code/analysis.py > out/analysis.txt` from the workspace root to reproduce feature extraction, training, development selection, model serialization, and the single test evaluation. Run `python code/summarize.py > out/summary.txt` to reproduce the interval, class recalls, and difference from the supplied reference using the logged confusion matrix. The selected model is stored in `out/model.json`, and all reported empirical numbers are logged in `out/analysis.txt` or `out/summary.txt`.
