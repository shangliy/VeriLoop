# Audit checklist

Each item is a defect that was found in a real review round of an
agent-written experiment report (generative-recommendation experiments,
five rounds), with the check that catches it. Walk all sections; for each,
write either a finding with `file:line` or "checked, sound".

Severity: **blocker** (the claim does not follow), **major** (the claim must
be narrowed or an experiment added), **minor** (wording, presentation).

## A. Does the number exist, and is it the number claimed?

1. **Untraced numbers.** A whole table column existed only in the results
   document, with no log. -> `trace_numbers.py`; then open the log.
2. **Log provenance.** A log that appears after a reviewer asked for it must
   come from a script that prints that format. -> find the script, check its
   mtime against the log's, read the print statement.
3. **Mixed rows.** One row combined recall from model A with diagnostic
   metrics from models B and C; a headline mixed a normalised and an
   unnormalised variant. -> tracer MIXED ROW, then confirm every cell of a row
   comes from one checkpoint and one configuration.
4. **Report vs log drift.** A value in the report differed from the log
   (.496 written, .478 logged). -> spot-check every headline number by eye.
5. **Stale logs.** The script was edited after the log was written. -> tracer STALE.
6. **Subset vs full.** A comparison used n=2000 on one side and the full test
   set on the other. -> read n on both sides of every delta.

## B. Baselines

7. **The simple baseline that wins.** A training-free kNN and a flat model on
   the same text features beat every elaborate method on the target metric.
   -> is there a zero-training baseline and a flat same-input baseline? If
   not, that is the first experiment to request.
8. **Weak baseline.** A standard model was run with a reduced input (SVD-128)
   and sat three points below its properly configured version. -> compare the
   baseline's number to published numbers on that dataset and to a tuned run;
   check it had the same tuning budget and the same inputs as the method.
9. **Missing obvious control.** The method was "coarse routing + X"; the
   control "plain X + the same routing as an index" was absent and, once run,
   matched it. -> for each component, ask what the cheapest way to get the
   same effect is, and whether it was run.
10. **Nearest neighbour not compared.** -> name the closest published method
    and check it is a baseline or its absence is explained.

## C. Selection and tuning

11. **Selected on test.** top-M, temperature and a combination weight were
    chosen from a test-side sweep. -> in the code, find where each tuned value
    is chosen and on which split; `selected-on` in the ledger must say so.
12. **Grid-edge optimum.** The best value sat at the end of the grid. -> the
    grid must bracket the optimum on both sides.
13. **Metric switching.** The report led with lift where mean rank told the
    opposite story. -> is the primary metric the registered one? Are the
    metrics that disagree shown?
14. **Variant shopping.** Several variants were trained and the best reported
    as "the method". -> count variants in the scripts and logs; the report
    must state how many were tried and how the reported one was chosen.

## D. Matched comparison

15. Same test users, same n, same candidate set, same list length.
16. **Same operating point.** Comparing tail recall at different head/tail
    trade-offs is meaningless. -> compare at matched Tail or matched All, or
    compare whole frontiers; a post-hoc reweighting (for example
    `-tau*log(1+pop)`) must be applied to the baselines too.
17. **Same inputs.** A method with text features against a baseline without.
18. **Same budget.** Training time, parameters, scan fraction, beam width.

## E. Attribution and mechanism

19. **Multi-change method, no ablation.** A method changed five things
    relative to the baseline and the gain was attributed to one. -> list
    every difference from the code (not from the report); each needs its own
    ablation before a mechanism is named. Ledger gate G5.
20. **Correlation presented as cause.** A rank correlation between a
    geometric quantity and popularity was called the mechanism. -> is there
    an intervention (change only that quantity) with the predicted effect?
21. **Counterexample in own logs.** One method in the same logs did not show
    the claimed universal failure. -> search the report's own logs for a row
    that contradicts the general claim before looking anywhere else.
22. **Hypothesis already tested and negative.** -> check the ledger history
    and earlier audits; a reversed claim must say what changed.

## F. Statistics

23. **Single seed.** -> fewer than 3 seeds is "pilot", whatever the delta.
    Seed spread on this kind of metric has been as large as differences
    reported as gains.
24. **Unpaired or missing interval.** -> paired bootstrap over test users for
    a delta on the same users; the interval must exclude zero for a claim.
25. **Tie handling.** A tie-breaking bug inflated a rank metric. -> check how
    equal scores are ranked (random jitter or pessimistic, never optimistic).

## G. Measurement

26. **Inferred, not measured, cost.** Latency was argued from logit counts;
    measured, the method was 220x slower than the flat baseline. -> any
    speed, memory or cost claim needs a wall-clock measurement on stated
    hardware, same batch size, warm cache.
27. **Diagnostic validity.** -> does a derived diagnostic behave correctly
    on a case with a known answer (random scores, an oracle)?

## H. Scope and literature

28. **Scale.** All catalogues had N <= 12k; the claim was about generative
    retrieval in general. -> the claim's scope words must match what was run.
29. **Dataset family.** Three datasets from one source are one family.
30. **Misattributed citation.** A figure was attributed to the wrong paper;
    a paper cited for a claim was about something else. -> for each citation
    the argument depends on, open the paper and find the sentence or table.
    Search and read; do not answer from memory. Record the queries.
31. **Novelty boundary.** -> state the nearest prior method and the exact
    difference; "a known technique moved into this setting" is a patch.

## I. Trajectory

32. **Claim drift.** Across rounds the framing moved from "search error" to
    "two locks" to "geometry" as each was refuted. -> `claims.py show`; a
    claim reworded after its evidence loses its earlier verdict (gate G6),
    and the audit states the history in one line.
33. **Dropped findings.** -> list every finding of the previous audit and
    mark it resolved (with the log) or still open. A finding that is simply
    no longer mentioned is open.
34. **Killed alternatives reported.** Variants that were tried and dropped
    belong in the report; they bound how much selection happened.

## J. Code-level integrity (FabScore / SciIntegrity / ARIS-inspired)

35. **Hardcoded / simulated metrics or `[Ref ...]` prints.** A script
    hardcoded a float list/dict (`f1 = [0.85, 0.72]`) or printed a literal
    `[Ref ...]` number that drifted from the actual log (`.3720` vs `.3718`).
    -> `audit_code.py` (`HARDCODED_REF_PRINT`, `HARDCODED_METRIC_ARRAY`), then
    inspect the exact print and computation lines.
36. **Synthetic / mock fallback on missing inputs.** When a CSV was empty or
    an API key was absent, code silently generated random/mock data and wrote
    a plausible report. -> `audit_code.py` (`MOCK_OR_SYNTHETIC_FALLBACK`), and
    confirm every reported input file actually exists and is non-empty.
37. **Dead metric code.** An evaluation script defined a metric function that
    was never called, while the report described it as evaluated. ->
    `audit_code.py` (`DEAD_METRIC_CODE`).
38. **Scope overclaim words.** A small-scale or single-domain run used
    "universal", "proves", "extensive", or "robust across all". ->
    `audit_code.py --report` (`SCOPE_OVERCLAIM_WORD`) and check against the
    registered `scope` in `claims.json`.

## What a clean audit says

"Supported" needs: traced numbers (with exact sign, row-cited log match, and
paired `±`/CI co-occurrence), intact non-truncated logs (SHA-256 verified),
>= 3 seeds per dataset and non-deterministic baseline with a paired interval
(G7), valid-side selection, the strong simple baselines beaten at a matched
operating point, dedicated ablation logs for each change (G5), clean AST code
integrity checks, and scope words matching the runs. Anything less has a
precise lower status, and the audit says which gate is open and the smallest
experiment or edit that would close it.
