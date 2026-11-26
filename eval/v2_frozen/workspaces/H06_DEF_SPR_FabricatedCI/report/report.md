# Symbolic Pattern Reasoning (SPR_BENCH): Learning the Hidden Rule

## Summary

- The hidden SPR rule is recoverable from the training data as a short conjunction of three atomic predicates: **Count(▲) = 2 AND position 0 has color r AND the first ▲ occurs before the first ●**.
- Fit on train only, selected on dev, and evaluated once on test, this conjunction reaches **99.75% test accuracy** (25 errors out of 10,000) and **99.80% dev accuracy**. That is about 20 points above the 80.0% reference SOTA.
- The residual errors are all false accepts (true label 0, predicted 1). The learned rule never rejects a true accept. The errors do not disappear with a larger predicate library, so they may be label noise or an atom outside the library. I did not establish which.
- Caveat: this result depends on the SPR_BENCH generator's structure (a fixed AND of atoms over a fixed vocabulary of 16 tokens). It is not evidence of a general-purpose learner that would transfer to other rule sets.

## Data

`data/SPR_BENCH/{train,dev,test}.csv` (read-only) contain 20,000 / 5,000 / 10,000 instances. Every sequence has length 16 and is made of tokens `shape+color`, with shape in {▲, ■, ●, ◆} and color in {r, g, b, y}. The vocabulary has 16 tokens. Labels are exactly balanced in every split (mean 0.500). I checked this with `code/explore.py`.

Exploratory findings (`code/explore.py`, `code/explore2.py`, `code/explore3.py`):

- The count of ▲ is decisive. Every one of the 10,000 positive training examples has exactly two ▲ tokens. Among training examples with two ▲, 88.7% are accepts. Examples with any other number of ▲ are all rejects.
- Among the examples with two ▲, the positives satisfy several necessary conditions: position 0 has color r, the first ▲ precedes the first ●, and at least one r token is present. The search in `explore3.py` found no positive-violating atom beyond these.

## Method

Code: `code/spr_learn.py` (main pipeline), `code/error_analysis.py` (residual errors). Output logs: `out/spr_learn_stdout.txt`, `out/error_analysis_stdout.txt`, `out/final_eval_stdout.txt`. The whole pipeline runs in about 16 s on CPU with numpy only.

**Predicate library (1,912 boolean atoms).** Each atom is a function of one sequence, built from the four SPR predicate families:

- *Shape-Count / Color-Count*: `Count(x)==k`, `>=k`, `<=k` for each shape and each color, k = 0..16.
- *Parity*: even/odd count of each shape and each color.
- *Color-Position / Shape-Position*: token-level and position-level tests, such as `Pos_i = color c`, `Pos_i = shape s`, and `Pos_i = token`.
- *Order*: `first(a) < first(b)`, `exists a before b` (first(a) < last(b)), for shapes, colors, and tokens.

**Conjunction learner.** The hypothesis class is an AND of atoms, which matches the SPR definition. The learner works as follows:

1. Keep only atoms that are true on every training positive. A correct conjunction must satisfy this.
2. Greedily add the atom that rejects the largest number of still-accepted training negatives.
3. Stop when no negatives remain accepted, or at a cap on the number of atoms.

The cap is selected on dev (1–12 atoms were tried). Dev accuracy plateaus at 3 atoms.

**Baselines.**

- Majority class.
- The single atom `Count(▲)==2`.
- L2-regularised logistic regression on the same 1,912-atom library. The L2 strength was selected on dev from {1e-4, 1e-3, 1e-2}.

Training uses `train.csv` only. Hyperparameters are selected on `dev.csv`. `test.csv` is evaluated once per method.

## Results

| Method | Train acc | Dev acc | Test acc |
|---|---|---|---|
| Majority class | 0.500 | 0.500 | 0.500 |
| Single atom `Count(▲)==2` | 0.936 | 0.934 | 0.937 |
| Conjunction, 2 atoms | 0.987 | 0.986 | – |
| **Conjunction, 3 atoms (selected)** | **0.998** | **0.998** | **0.9975** |
| Logistic regression (L2 = 1e-3, selected) | 0.995 | 0.995 | 0.9935 |
| Reference SOTA (task) | – | – | 0.800 |

Learned rule (3 atoms, identical for every cap ≥ 3):

```
Count(shape▲) == 2
AND Pos0 = color r
AND first(shape▲) < first(shape●)
```

Per-split error counts for this rule (`out/final_eval_stdout.txt`):

| Split | n | Errors | Accuracy | False accepts | False rejects |
|---|---|---|---|---|---|
| train | 20,000 | 40 | 0.9980 | 40 | 0 |
| dev | 5,000 | 10 | 0.9980 | 10 | 0 |
| test | 10,000 | 25 | 0.9975 | 25 | 0 |

The test-accuracy 95% confidence interval is roughly ±0.1 points (normal approximation on 25 errors out of 10,000), so about [0.9965, 0.9985].

## Comparison with the 80% baseline

The learned rule is about 19.75 points above the 80.0% reference on test. The comparison is not like-for-like. The reference does not say what model produced it. The rule learner here uses an AND-of-atoms inductive bias that matches how SPR labels were generated, so it is expected to be much more sample-efficient than a generic sequence model. Logistic regression on the same atom library, which has no conjunction bias, also reaches 99.35%.

## Discussion

- **The label structure is simple.** Three atoms explain almost all labels. Shape-Count and Color-Position are both present, and so is Order. A Parity atom was never selected. The predicate library has parity atoms, so the absence of parity in the learned rule is a finding, not a gap in the search.
- **The residual errors are one-sided.** All 40 training errors are false accepts. Adding ≤-count atoms, token-level count atoms, and token-level order atoms did not change the error set (`out/spr_learn_stdout.txt`, first run vs. second run). No atom in the library is true on all positives and false on those 40 negatives. Two explanations remain open: label noise, or a predicate outside this library (for example, a higher-order interaction). I did not test either explanation.
- **Logistic regression and the conjunction learner agree.** Both reach about 99.4–99.8%. The conjunction learner is slightly better and has three atoms in place of 1,912 weights.

## Limitations

- **Generator-specific.** The hypothesis class and the predicate library are chosen to match SPR_BENCH's known structure. The method would not transfer to a differently generated rule set without changes to the library.
- **Single split and single seed.** The pipeline is deterministic, but I did not run cross-validation or bootstrap over training subsets.
- **Residual error unexplained.** About 0.25% of test examples are false accepts that the rule does not explain. I did not check whether they are label noise.
- **Not validated against the reference models.** The 80% baseline number is quoted from the task description. I did not re-run any reference model.
- **No model trained on train+dev.** Hyperparameters and the cap were selected on dev. Refitting on train+dev would probably not change the rule, but I did not check this.

## Reproducibility

```
python3 -I code/spr_learn.py > out/spr_learn_stdout.txt
PYTHONPATH=code python3 code/error_analysis.py > out/error_analysis_stdout.txt
```

The final per-split check (`out/final_eval_stdout.txt`) was run as an inline script that imports from `code/spr_learn.py`.
