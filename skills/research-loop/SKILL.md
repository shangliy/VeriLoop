---
name: research-loop
description: Evidence-first research loop for empirical ML/IR work, covering the stretch between choosing an idea and writing the paper - pre-register claims, run experiments on a small GPU, write a report whose every number traces to a log, have it audited by an independent reviewer who reads raw logs and code, then decide continue / revise / kill. Use it whenever the user pastes or points at an experiment status report, results table or "contributions" list and wants it judged ("作为reviewer评估", "评估这个结果", "review these results", "audit this report", "is this claim supported", "这个结论站得住吗"), whenever an agent is about to report experiment results or claim a method works, and when the user wants an idea taken through experiments end to end ("run the research loop", "把这个想法跑通", "自动科研"). Also use before any result is copied into a paper draft. Not for finding ideas (`research-idea`) or drafting the paper (`paper`); this skill sits between them and hands off to both.
---

# Research loop

An executor agent that runs experiments also writes the report about them, and
the report drifts: a column that was never logged, a row that mixes two
checkpoints, a top-M picked on test, a baseline three points too weak, a
mechanism asserted from a correlation, a claim quietly reworded after each
result. None of this needs bad intent; it is what happens when the party that
wants the result also grades it. This skill separates the roles and makes the
cheap checks mechanical, so reviewer attention goes to the questions a script
cannot answer.

Three rules carry most of the weight:

1. **A number without a file is not evidence.** Results live in logs written
   by scripts; the report quotes them. `trace_numbers.py` checks this.
2. **The executor cannot acquit itself.** A verdict on merit comes from a
   reviewer that starts from the raw logs and code, not from the report's
   framing, and finally from the user.
3. **Claims are fixed before evidence and every rewording is recorded.**
   `claims.py` holds the ledger and refuses "supported" until the gates pass.

`SKILL_DIR` = the directory of this file. Scripts are stdlib-only Python.

## Where it sits

```
research-idea  ->  research-loop  ->  paper
(choose)           (prove or kill)    (write)
```

- Workspace: the idea's directory from `research-idea` (`ideas/<date>-<slug>/`),
  or the `paper` workspace if one exists. Add `claims.json`, `reports/`, and
  `audits/` there. Do not create a second ledger: outcomes go into the existing
  `ideas/ideas_verdicts.md`.
- If a `paper` workspace exists, also log runs with its `exp.py` so stage 09
  sees them. `claims.py` adds what `exp.py` lacks: evidence must be a file on
  disk, baselines and ablations are gated, and rewordings are kept.
- Read project memory and `ideas_verdicts.md` first for constraints (compute,
  budget, deadline) and for what is already dead.

## Entry points

Pick by what the user brought:

| The user has | Start at |
|---|---|
| A report / table / contribution list to judge | **Audit** (the most common entry) |
| A chosen idea, nothing run yet | **Register**, then Run |
| Results in logs, no report yet | **Report**, then Audit |
| A request to run the whole thing | Register -> Run -> Report -> Audit -> Decide, stopping at each gate |

## 1. Register (before anything runs)

For each claim the work hopes to make, one ledger entry:

```bash
C="python3 $SKILL_DIR/scripts/claims.py -w <workspace>"
$C add C1 --text "<falsifiable claim>" --metric "<primary metric>" --select-on valid \
   --seeds 3 --baselines "<strong simple baselines>" --kill "<observation that ends it>" \
   --scope "<datasets / scale it is limited to>"
```

Choosing the baselines is the part that needs thought. A method is only as good
as the simplest thing that matches it, so register, alongside the published
competitors, (a) a training-free baseline on the same inputs, (b) the flat or
"boring" model fed the same features as the method, and (c) a properly tuned
standard model, tuned with the same budget as the method. `references/checklist.md`
section B says why each one has killed a result before. One primary metric is
named now; switching it later is a revision, not a detail.

Show the user the registered claims and wait for a go-ahead before spending
GPU-hours or API budget. This is the first human gate.

## 2. Run

- Every script prints its results to a log file under the project's output
  directory, named after the script (`foo.py` -> `out/foo.txt`). Print the
  configuration, the split each number was computed on, n, and the seed on the
  same lines as the metric. A number that only ever appeared in the chat or in
  a markdown file does not exist.
- Select everything (epochs, checkpoint, temperature, top-M, thresholds) on
  VALID and print the selected value; print TEST once, for the selected setting.
  A test-side sweep may be printed for reference if it is labelled as such.
- Fit the hardware you actually have: check free VRAM before launch, start with
  the smallest run that could fail, run long jobs in the background and wait
  for the completion notification instead of polling. Do not start a paid
  resource (cloud GPU, API) without the user's say-so.
- Pilot first (1 seed, subset). A pilot decides whether to proceed; it is
  labelled "pilot" everywhere and never becomes a paper number.
- After each run attach it: `$C evidence C1 --log out/foo.txt --seeds 1 --selected-on valid --n 22363 --changes 5 --ablated 0`
  (`--arm NAME` for a baseline; `--changes` = how many things differ from the
  baseline it is compared to).

## 3. Report

Write `reports/<date>-<n>.md`. Each table row names its log file; each claim
names its ledger id and its current status word (pilot / partial / supported).
Then run the tracer and static code scanner and fix issues until clean:

```bash
python3 $SKILL_DIR/scripts/trace_numbers.py reports/<file>.md --logs <out dir> --scripts <scripts dir>
python3 $SKILL_DIR/scripts/audit_code.py --scripts <scripts dir> --report reports/<file>.md
```

- **UNTRACED**: run the missing experiment and log it, or delete the number.
  Typing the number into a log by hand is fabrication, not a fix.
- **SIGN_MISMATCH**: magnitude exists in logs only with the opposite sign
  (e.g., `-0.0106` logged, `+0.0106` reported). Fix immediately.
- **WRONG_LOG**: the row named a specific log file, but a number on that row
  does not appear in that log. Fix the log citation or the number.
- **UNPAIRED_PM/CI**: `mean±std` or `[lo,hi]` never co-occur on the same log
  line; check for mixed checkpoints or copied CIs.
- **MIXED ROW**: a row drawing on several logs. Either split it or state which
  log each cell is from.
- **CITED STALE**: a script changed after a log cited by this report was
  written; rerun. (Unrelated `WORKSPACE STALE` logs are informational.)
- **`audit_code.py` HIGH findings**: hardcoded metric arrays or `[Ref ...]`
  prints, random/mock fallbacks on missing data, or test-split model selection.

A clean trace + AST scan means the numbers exist with matching signs in the
cited logs and no obvious code shortcuts fired. It does not mean the method or
comparison is scientifically valid; that is the audit's job.

## 4. Audit

Read `references/checklist.md` before auditing; it is the list of defects
found in real review rounds, each with the check that catches it.

**Who audits.** If you produced the experiments or the report in this
session, do not audit them yourself: spawn a fresh reviewer agent using
`references/reviewer-brief.md` (it gets paths and the claim ids, never your
summary or what you expect it to find). If the user hands you another agent's
report, you are the independent reviewer; do the audit directly.

**How.** In this order, because each step is cheaper than the next:

1. Run `trace_numbers.py` and `claims.py check`. Mechanical failures go
   straight into the findings.
2. Open the logs behind every headline number and the code that printed them.
   Confirm the split, n, the selected setting, the seed, and that the row's
   cells come from one model.
3. Walk the checklist: selection, baselines, matched comparison, attribution,
   scope, measurement, and the report's own logs for counterexamples.
4. For any claim about prior work that the argument leans on, read the cited
   paper's relevant section (not the abstract) and name the nearest neighbour.
   Search rather than recall; log the queries.
5. Write `audits/<date>-<n>.md`: verdict first, then findings ordered by
   severity, each with `file:line` evidence and the smallest experiment or edit
   that would resolve it. Say what was checked and found sound, so a clean area
   is distinguishable from an unexamined one.

**Verdict per claim** is one of: `supported`, `partial` (holds in a narrower
form; give the wording), `pilot` (direction only; fewer than 3 seeds or a
subset), `unsupported`, `refuted`. Record it with `$C status C1 <word> --by reviewer`.
The ledger will refuse `supported` while a gate is open; report the refusal
rather than arguing with it.

**No bargaining.** The reviewer does not see rebuttals from the executor and a
finding is closed by new evidence on disk, not by a reworded sentence. If a
finding vanishes from the next report without a log behind it, list it as
unresolved. If the right response is to narrow the claim, that is a `revise`
in the ledger with the reason, and the earlier verdict no longer applies.

## 5. Decide (the user's call)

Give the user, in the chat: the verdict table, the two or three findings that
change the story, and a recommendation among **continue** (with the next
decisive experiment), **revise** (narrowed claim), or **kill**. Then stop and
wait. Do not auto-select an idea, auto-proceed to the next stage, or start
another round of experiments to "fix the score" without the user.

After the decision, update the row in `ideas/ideas_verdicts.md` with the status
and the one-line evidence. Deaths are the most valuable entries; a killed idea
that is not recorded gets reinvented.

Hand off to `paper` only for claims at `supported`. The paper's tables are
built from the logs the ledger points to; run the tracer on the draft too.

## Optional second model

A reviewer from a different model family catches blind spots a same-family
reviewer shares with the executor. If the user has such a reviewer configured
and asks for it, give it the same path-only brief. It is off by default because
it sends the project's code and unpublished results to a third party and costs
money; never enable it, or install anything that edits settings or hooks, on
your own initiative.

## Reply shape

Verdict first. A table of claims (id, status, the gate or finding that limits
it), then findings by severity with `file:line`, then what is sound, then the
recommended next step. Keep it short; the audit file holds the detail. Reply in
the user's language; file names, code and paper titles stay as they are.

## Files

- `scripts/trace_numbers.py`: report numbers vs logs (untraced, sign mismatch, wrong log, unpaired `±`/CI, mixed rows, cited vs workspace stale).
- `scripts/claims.py`: claim ledger with gates G1-G7 (SHA-256 integrity, per-dataset/arm seeds, deterministic baselines, ablation-log binding, monotonic sequence G6, verified CI G7).
- `scripts/audit_code.py`: stdlib AST static code & scope-overclaim pre-scanner.
- `scripts/budget.py`: API cost ledger & hard USD circuit breaker (default `$50` cap).
- `scripts/run_audit.py`: cross-model independent audit engine (Claude + OpenAI + dry-run; single, two-stage `kill-adjudicate`, `ablation-plan`, effort presets, stagnation detector).
- `scripts/run_seeds.py`: single-GPU sequential multi-seed runner with crash resume and live local-log NaN/OOM/divergence watchdog.
- `scripts/render_board.py`: static verifiable HTML claim & audit dashboard with source SHA-256 provenance.
- `references/checklist.md`: the 38-item audit checklist (A–J), with the real failure behind each item.
- `references/reviewer-brief.md`: path-only brief for a fresh reviewer agent (with compute/API budget line).
