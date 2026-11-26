---
name: verifiable-gate
description: "Hard dual-layer evidence gate upgrading ARIS advisory audits into deterministic, blocking verification. Runs signed numerical provenance (trace_numbers.py), 6 Python AST integrity checks (audit_code.py), G1-G7 claim ledger checks (claims.py), citation checks, and path-isolated cross-family auditing (run_audit.py) before allowing delivery. Use after experiments or before paper submission when user says \"硬门控审计\", \"verifiable gate\", \"hard audit\", or as a mandatory blocker inside /research-pipeline."
argument-hint: "[workspace-path]"
allowed-tools: Bash(*), Read, Grep, Glob
---

# VeriLoop Gate: Dual-Layer Evidence Enforcement

Enforces **VeriLoop**'s fail-closed dual-layer verification gate before any research deliverable or manuscript section is released.

## Empirical Basis (v2 Frozen Benchmark & Unseen Blind Test, Unified Route A Rule)

Controlled zero-override evaluations across 16 SHA-256 frozen workspaces (`9` clean / `7` defective under a unified post-audit rule classifying disclosed, arithmetically correct derivations from logged counts as clean provenance gaps; `245` paired LLM trials, `k=3` repeats) and 21 strictly unseen `SciIntegrity-Bench` scenarios (`paper/main.pdf`, `eval/v2_frozen/`, `eval/v2_unseen/`) establish the exact role of each layer:
1. **Deterministic Layer 1 is a `$0` millisecond pre-filter (`71.4%` in-sample blocked, `57.1%` attributable):** Locked v2 Layer 1 (`eval/v2_frozen/locked/`, SHA-256 `42c39cf4a4adeee1` / `72dac256a9caf775`) blocks `5/7` defective workspaces (`4/7` directly attributable on sign flips, mock fallbacks, test-set tuning, and hardcoded prints, plus `1/7` incidental unit-rescaling block on `C05`) before any paid LLM call is needed.
2. **Read-only Layer 2 closes the semantic blind spot and preserves clean yield:** Layer 1 misses subtle code-logic denominator bugs (`H05`) and pure inferential overclaims (`C08`), while strict log-only numerical blocking incurs `2/9` clean provenance-gap FPs (`H06` disclosed normal-approx CI, `C04` prose polarity; `77.8%` yield). Read-only `codex-cli` resolves all `7/7 (100.0%)` defects and `9/9 (100.0%)` clean workspaces.
3. **Low out-of-sample FPR on strictly unseen clean runs:** With locked v2 mechanical gates, all `18/18` completed unseen scenarios were verified trap-avoiding (`CLEAN`), recording **`0/18 (0.0%)` AST FPR** and **`2/289 (0.69%)` number-level FPR** (out-of-sample recall unmeasured due to `0` positive unseen traps). Shipped v3 `trace_numbers.py` adds `--data` raw-dataset indexing and unsigned negative-direction prose polarity motivated by `C04`/`09c` (in-sample; fresh held-out validation is required before claiming out-of-sample v3 FP reductions).

## Workflow (Two Layers)

### Layer 1: Deterministic Zero-Cost Mechanical Gate
Run the unified CLI directly on the target workspace (`$ARGUMENTS`, default `.`):

```bash
./veriloop gate \
  --workspace "${ARGUMENTS:-.}" \
  --report report/report.md \
  --logs out/ \
  --scripts code/ \
  --out-json audits/verifiable_gate_result.json
```

This deterministically verifies:
- **`trace_numbers.py` (v3)**: every decimal ($\ge 3$ places) traces to intact logs (and auto-detected `<workspace>/data` or explicit `--data` raw datasets) with matching sign (`SIGN_MISMATCH`), percent/fraction equivalence, explicit negative-direction prose polarity on unsigned magnitudes (excluding metric nouns like `loss` and never relaxing explicit `+`), row-cited log file (`WRONG_LOG`), paired `±` / CI bounds (`UNPAIRED_PM/CI`), and script freshness (`CITED_STALE`, pass `--strict-stale` to hard-block on stale cited logs).
- **`audit_code.py`**: Python AST scan for `HARDCODED_REF_PRINT`, `HARDCODED_METRIC_ARRAY`, `MOCK_FALLBACK`, `TEST_TUNING`, `OPTIMISTIC_TIE`, and `DEAD_METRIC` (`0.0%` FPR in-sample and unseen).
- **`claims.py` (`G1--G7`)**: if `claims.json` exists, enforces SHA-256 log integrity, completion markers, multi-seed floors, validation-only selection, pre-registered baselines, ablation logs, anti-drift chronology, and machine-parseable CIs.
- **`citation_audit.py`**: add `--bib paper/refs.bib` when auditing LaTeX manuscripts.

### Layer 2: Path-Isolated Cross-Family Blocking Audit
Never pass executor summaries, `EXPERIMENT_LOG.md`, or `NARRATIVE_REPORT.md` to the reviewer. Pass `--reviewer-provider codex-cli` (when executor is Claude) or `--reviewer-provider claude-cli` (when executor is Codex):

```bash
./veriloop gate \
  --workspace "${ARGUMENTS:-.}" \
  --report report/report.md \
  --logs out/ \
  --scripts code/ \
  --reviewer-provider codex-cli \
  --budget-file audits/budget.json \
  --budget-limit 5.00 \
  --out-json audits/verifiable_gate_result.json
```

For milestone-level peer review of frozen code, tables, and paper drafts before submission, invoke the parallel dual-model auditor:

```bash
./veriloop milestone-audit \
  --milestone M4-submission \
  --workspace "${ARGUMENTS:-.}" \
  --artifacts report/report.md out/ code/
```

## Hard Blocking Rule

- **Exit code `0`**: `APPROVE_SUPPORTED` or `APPROVE_HONEST_REFUSAL` — delivery allowed.
- **Exit code `2`**: **HARD BLOCK**. Do NOT deliver the report or advance `/research-pipeline` to `/paper-writing`. Return *only* the mechanical error list and `audits/verifiable-gate-review.md` to the executor for a targeted repair turn, then re-run `./veriloop gate`.
