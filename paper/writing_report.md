# Best-Paper Writing Report (`VeriLoop` v2 — Route A Non-Circular Release)

Generated following `shangliy/Best-Paper-Writing-Skill` (forked from `gulucaptain/Best-Paper-Writing-Skill`) and verified via `./veriloop audit-paper` and two rounds of independent Claude Opus hostile milestone audits (`M3-draft-v2` and `M4-final-code-and-paper-v2`) for dual-target release:
- **Public arXiv v2 Preprint**: `paper/main.pdf` (`paper/main.tex`, `paper/arxiv_v2_submission.tar.gz`)
- **ICML 2027 Submission (`Datasets, Evaluations, and Benchmarks` track)**: `paper/main_icml2027.pdf` (`paper/main_icml2027.tex`, official unmodified `icml2027.sty`, double-blind, exact 8-page main body + Page 9 `AI Use Statement` & `Impact Statement` + `References` + Appendix)

---

## Step 1: Core Positioning (Route A Unified Labeling Rule)

- **Unified Pre-Registered Labeling Rule**: Any number explicitly disclosed in prose as an arithmetic derivation from logged raw counts or parameters (`H06` normal-approximation CI `[0.9965, 0.9985]` from logged `25/10000`, and unseen `04c` analytic midpoint `0.425=(0.75+0.10)/2`) is classified as `CLEAN` (benign non-log provenance gap), NOT `DEFECTIVE` misconduct.
- **Claim**: On 16 SHA-256 frozen workspaces (`9` clean, `7` defective, `245` paired LLM trials, zero overrides), VeriLoop's `$0` deterministic Layer 1 pre-filters `5/7 (71.4%)` defective workspaces before any paid review while read-only `codex-cli` resolves the remaining logic (`H05`) and inferential (`C08`) defects for `7/7 (100.0%)` recall (`87.5%` strict hard-block F1 at `77.8%` yield vs `100.0%` F1 when provenance warnings feed Layer 2); on 21 strictly unseen `SciIntegrity-Bench` scenarios (all `18/18` completed runs verified trap-avoiding `CLEAN`), locked v2 mechanical gates record `0.0%` AST FPR and `0.69%` number-level FPR (out-of-sample recall unmeasured).
- **Headline Verified Numbers (`paper/out/stats_summary.txt`, Zero Overrides)**:
  - `16` frozen workspaces (`9 CLEAN`, `7 DEFECTIVE`; `8` Haiku `5C/3D`, `8` Codex `4C/4D`; `6` natural runs, `5` clean twin bases, `5` constructed defect twins)
  - `layer1_mechanical` (locked v2, `$0`, in-sample): `5/7 (71.4%)` recall, `7/9 (77.8%)` yield, `71.4%` F1
  - `codex-cli (path_only)`: `7/7 (100.0%)` recall, `9/9 (100.0%)` yield, `100.0%` F1, `100.0%` unanimity
  - `claude-sonnet (path_only)`: `6/7 (85.7%)` recall (misses `H05` denom bug `6/6`), `9/9 (100.0%)` yield, `92.3%` F1
  - `L1 ∪ codex-cli (path_only, strict hard union)`: `7/7 (100.0%)` recall, `7/9 (77.8%)` yield, `87.5%` F1
  - Workspace-level exact McNemar framing tests (`n=16` workspaces, no trial pseudo-replication): `p = 1.000000` (`0:0` majority-vote flips for both `claude-haiku` and `claude-sonnet`)
  - Strictly unseen `21`-scenario blind test (`18/21` completed, `18/18` verified `CLEAN`, `$0.3187`): `0/18 (0.0%)` AST FPR, `2/289 (0.69%)` number-level FPR (`2/18 = 11.1%` scenario-level), out-of-sample recall unmeasured (`0` unseen trap defects).

---

## Step 2: M4 Opus Audit Closure Log (All 8 Findings Resolved)

1. **BLOCKER #1 (`H06` vs `04c`)**: Applied unified Route A rule; relabeled `H06` as `CLEAN` in `ground_truth.csv`, joined dynamically in `aggregate_v2.py` & `build_tables_and_figures.py`, rewrote all prose/tables/figures.
2. **MAJOR #2 (Trial-level McNemar pseudo-replication)**: Replaced trial-level `p=0.250000` with workspace-level exact McNemar (`n=16` workspaces, `n_def=7`).
3. **MAJOR #3 (Locked v2 snapshot vs shipped v3)**: Committed locked v2 scripts at `eval/v2_frozen/locked/trace_numbers_v2.py` (`42c39cf4a4adeee1`) & `audit_code_v2.py` (`72dac256a9caf775`); pinned `--layer1-only` & default unseen runner to locked v2 with SHA-256 assertions and non-clobbering default outputs; explicitly flagged v3 `C04`/`09c` fixes as in-sample.
4. **MAJOR #4 (Unseen trap labeling & `7_statements.tex`)**: Labeled all `18/18` completed unseen reports against official checklists (`gt_trap_taken=False` on `18/18`), explicitly stated out-of-sample recall is unmeasured, aligned `FPR` terminology everywhere.
5. **MAJOR #5 (`ground_truth.csv` gate-independent rationale)**: Rewrote all 16 evidence strings in human-verified `file:line` terms with zero Layer-1 tool outputs.
6. **MINOR #6 (`1_intro.tex` colon density warning)**: Fixed `1_intro.tex` colon density so `./veriloop audit-paper` reports `0 errors, 0 warnings`.
7. **MINOR #7 (`trace_numbers.py` `NEG_PREFIX_RE` `loss` bug)**: Removed `loss` from `NEG_PREFIX_RE` and added regression unit test (`"validation loss of 0.3120"` vs `-0.3120` triggers `SIGN_MISMATCH`).
8. **MINOR #8 (Unseen raw workspaces gitignored)**: Updated `.gitignore` to track minimal forensic files (`report/report.md`, `out/`, `code/`, and `09c/data/island_species.csv`, `788 KB` total) for all 18 completed unseen scenarios.
