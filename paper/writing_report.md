# Best-Paper Writing Report (`VeriLoop` v2)

Generated following `shangliy/Best-Paper-Writing-Skill` (forked from `gulucaptain/Best-Paper-Writing-Skill`) and verified via `./veriloop audit-paper` and `./veriloop milestone-audit` (Opus `M3-draft-v2`: `0 BLOCKER`, all `7 MAJOR` + `5 MINOR` resolved) for dual-target release:
- **Public arXiv v2 Preprint**: `paper/main.pdf` (`paper/main.tex`, `paper/arxiv_v2_submission.tar.gz`)
- **ICML 2027 Submission (`Datasets, Evaluations, and Benchmarks` track)**: `paper/main_icml2027.pdf` (`paper/main_icml2027.tex`, official unmodified `icml2027.sty`, double-blind, exact 8-page main body + Page 9 `AI Use Statement` & `Impact Statement` + `References` + Appendix)

---

## Step 1: Core Positioning

- **Claim**: Coupling deterministic numerical-provenance and Python AST gates with path-isolated cross-family read-only auditing delivers complementary coverage on a public 16-workspace SHA-256 frozen benchmark (`245` paired trials, zero overrides) — raising recall to `100.0%` (`8/8` defective workspaces, `94.1%` F1, `87.5%` clean yield) while maintaining a `0.0%` AST flag rate and `0.69%` number-level benign flag rate on 21 strictly unseen `SciIntegrity-Bench` scenarios.
- **Tension Type**: `capability-missing` / `tradeoff` (existence gates verify execution without verifying scientific validity; standalone LLM reviewers miss unlogged numerical fabrications; static mechanical gates miss subtle code-logic and inferential overclaims).
- **Observation / Insight** (stated directly in prose): Autonomous research agents rarely fail by omitting output files; they fail by executing cleanly while reporting numbers, code paths, or conclusions that contradict their own logs.
- **Handle**: *Deterministic Evidence Gates and Path-Isolated Cross-Model Auditing* (placed directly in the title).
- **Closest Work & Checkable Differences**:
  1. **EviBound** (`chen2026evibound`): checks pre-execution schemas and post-execution file existence, but does not audit signed numerical provenance, static AST code integrity, or claim semantics.
  2. **ARIS** (`yang2026aris`): pairs cross-model agents in an iterative loop, but designates Stage-1 experiment auditing as advisory, injects executor narrative summaries across review boundaries, and lacks frozen-artifact paired evaluations.
- **Headline Verified Numbers (Zero Overrides, `paper/out/stats_summary.txt`)**:
  - `16` SHA-256 frozen workspaces (`8` `claude-haiku` + `8` `codex-cli`, exact `8` `CLEAN` + `8` `DEFECTIVE`; `6` natural runs, `5` clean twin bases, `5` constructed defect twins)
  - `245` valid LLM trials (`k=3` repeats across `claude-haiku`, `claude-sonnet`, `codex-cli` under `path_only` and `with_summary`, plus `43` transparently logged `codex-cli` rolling-quota errors)
  - `layer1_mechanical` (`$0`): `85.7%` precision, `75.0%` recall, `80.0%` F1, `12.5%` FPR, `87.5%` clean yield (in-sample)
  - `L1 ∪ codex-cli (path_only)`: `88.9%` precision, `100.0%` recall (`8/8`, 95% Wilson CI `[67.6%, 100.0%]`), `94.1%` F1, `87.5%` clean yield (case-level complementarity on `H06`: caught by Layer 1, missed in `14/15` LLM trials; paired `p = 0.250000`)
  - Strictly unseen `21`-scenario `SciIntegrity-Bench` blind test (`18/21` completed, `12/18` numeric, `$0.3187` spend, locked SHA-256 gates): `0/18 (0.0%)` AST flag rate, `2/289 (0.69%)` number-level benign flag rate (`2/18 = 11.1%` scenario-level).

---

## Step 2: Claim & Evidence Map (v2 Zero-Override)

| # | Claim | Method Section | Evidence (Table / Figure) | Exact Verified Statistic |
|---|---|---|---|---|
| 1 | Non-circular dual-layer complementarity on frozen 16-workspace corpus | \S2.1--\S2.3 | Table 1, Figure 2, Table 4 (App.) | `layer1_mechanical`: `75.0%` recall / `85.7%` prec; `codex-cli (path_only)`: `87.5%` recall / `100.0%` prec; `L1 ∪ codex-cli`: `100.0%` recall (`8/8`, CI `[67.6%, 100.0%]`), `94.1%` F1, `87.5%` clean yield; `H06` unlogged CI caught by Layer 1, missed in `14/15` LLM trials |
| 2 | Paired frozen-artifact factorial isolates reviewer family vs. summary framing | \S3.3 | Table 2, Figure 3 | On identical frozen workspaces under calibrated binary rubrics: `path_only` vs `with_summary` exact McNemar `p = 1.000000` (`paired_n = 48`); `100%` LLM detection on `5` constructed twins, all misses on `3` natural defects (`H05`, `H06`) |
| 3 | Locked mechanical gates maintain low benign flag rate on strictly unseen tasks | \S3.4 | Table 3, Figure 4 | `21` unseen scenarios (`18/21` completed, `12/18` numeric, `$0.3187`): `0/18 (0.0%)` AST flags, `2/289 (0.69%)` number-level benign flags (`04c` analytic midpoint `0.425`, `09c` raw CSV `3.542`) |
| 4 | Self-audited manuscript and public reproducibility | \S3.1, App. | `./veriloop audit-paper`, `eval/v2_frozen/` | `37/37` traced numbers (`0` untraced, `0` sign mismatches), `23/23` BibTeX citations valid, `0` errors / `0` warnings on `check_draft.py` & `check_figures.py`, zero hardcoded overrides |

---

## Step 3: Post-Audit v3 Engineering Follow-Ups (Implemented in Codebase, Kept Separate from v2 Paper Lock)

To preserve exact reproducibility of the published v2 paper numbers (locked at commit `b897378`), all post-v2 improvements are cleanly versioned as v3 code upgrades without altering committed v2 benchmark JSONLs:
1. **`trace_numbers.py` v3**: Added optional repeatable `--data <file-or-dir>` raw-dataset provenance (eliminating `09c`-style raw CSV quote FPs without triggering script-staleness checks) and explicit negative-direction prose polarity recognition on unsigned magnitudes (eliminating `C04`-style `"1.4598 pp below"` FPs while strictly preserving `SIGN_MISMATCH` on explicit `+` signs).
2. **`tools/verifiable_gate.py`**: Fixed `wrong_log` → `wrong_logs` reporting key, fixed multi-`--logs` / multi-`--scripts` forwarding, and added `--data` / auto-`<workspace>/data` and `--strict-stale`.
3. **`./veriloop eval-v2`**: Added unified CLI subcommand for one-command reproduction of v2 zero-override aggregation, Layer-1 audit, factorial runner, unseen blind test, and paper table/figure rebuild.
