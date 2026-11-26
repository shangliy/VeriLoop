---
name: verifiable-gate
description: "Hard dual-layer evidence gate upgrading ARIS advisory audits into deterministic, blocking verification. Runs signed numerical provenance (trace_numbers.py), 6 Python AST integrity checks (audit_code.py), G1-G7 claim ledger checks (claims.py), citation checks, and path-isolated cross-family auditing (run_audit.py) before allowing delivery. Use after experiments or before paper submission when user says \"硬门控审计\", \"verifiable gate\", \"hard audit\", or as a mandatory blocker inside /research-pipeline."
argument-hint: "[workspace-path]"
allowed-tools: Bash(*), Read, Grep, Glob
---

# VeriLoop Gate: Hard Dual-Layer Evidence Enforcement

Enforces **VeriLoop**'s fail-closed, hard-blocking dual-layer verification gate before any research deliverable or manuscript section is released.

## Empirical Basis (v2 Frozen-Artifact Benchmark & Unseen Blind Test)

Controlled zero-override evaluations across 16 SHA-256 frozen workspaces (`245` paired LLM trials, `k=3` repeats) and 21 strictly unseen `SciIntegrity-Bench` scenarios (`paper/main.pdf`, `eval/v2_frozen/`, `eval/v2_unseen/`) establish why both layers are needed together:
1. **Deterministic Layer 1 catches unlogged fabrications that LLMs miss (`$0` cost):** `trace_numbers.py` deterministically catches an unlogged confidence interval (`H06`: `[0.9965, 0.9985]`) missed in **14 of 15** independent LLM trials across `claude-haiku`, `claude-sonnet`, and `codex-cli`.
2. **Read-only Layer 2 closes the semantic blind spot of static gates:** Layer-1 checks alone reach `75.0%` recall (`85.7%` precision) because they cannot judge subtle code-logic denominator bugs (`H05`) or pure inferential overclaims (`C08`). Coupling Layer 1 with read-only `codex-cli` (`path_only`) reaches **`100.0%` recall (`8/8` defective workspaces, `94.1%` F1, `87.5%` clean yield)**.
3. **Low benign flag rate on strictly unseen tasks:** With locked v2 mechanical gates (`42c39cf4a4adeee1` / `72dac256a9caf775`), the 21-scenario blind test produced **`0/18 (0.0%)` AST flags** and **`2/289 (0.69%)` number-level benign flags** (v3 adds `--data` raw-dataset provenance and negative-direction prose polarity recognition to eliminate the `09c` raw-CSV and `C04` prose-polarity false positives without relaxing explicit `+` sign checks).

## Workflow (Two Hard Layers)

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
- **`trace_numbers.py` (v3)**: every decimal ($\ge 3$ places) traces to intact logs (and auto-detected `<workspace>/data` or explicit `--data` raw datasets) with matching sign (`SIGN_MISMATCH`), percent/fraction equivalence, explicit negative-direction prose polarity on unsigned magnitudes, row-cited log file (`WRONG_LOG`), paired `±` / CI bounds (`UNPAIRED_PM/CI`), and script freshness (`CITED_STALE`, pass `--strict-stale` to hard-block on stale cited logs).
- **`audit_code.py`**: Python AST scan for `HARDCODED_REF_PRINT`, `HARDCODED_METRIC_ARRAY`, `MOCK_FALLBACK`, `TEST_TUNING`, `OPTIMISTIC_TIE`, and `DEAD_METRIC`.
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
  --milestone M3-draft \
  --workspace "${ARGUMENTS:-.}" \
  --artifacts report/report.md out/ code/
```

## Hard Blocking Rule

- **Exit code `0`**: `APPROVE_SUPPORTED` or `APPROVE_HONEST_REFUSAL` — delivery allowed.
- **Exit code `2`**: **HARD BLOCK**. Do NOT deliver the report or advance `/research-pipeline` to `/paper-writing`. Return *only* the mechanical error list and `audits/verifiable-gate-review.md` to the executor for a targeted repair turn, then re-run `./veriloop gate`.
