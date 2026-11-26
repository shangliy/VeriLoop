---
name: verifiable-gate
description: "Hard dual-layer evidence gate upgrading ARIS advisory audits into deterministic, blocking verification. Runs signed numerical provenance (trace_numbers.py), 6 Python AST integrity checks (audit_code.py), G1-G7 claim ledger checks (claims.py), citation checks, and path-isolated cross-family auditing (run_audit.py) before allowing delivery. Use after experiments or before paper submission when user says \"硬门控审计\", \"verifiable gate\", \"hard audit\", or as a mandatory blocker inside /research-pipeline."
argument-hint: "[workspace-path]"
allowed-tools: Bash(*), Read, Grep, Glob
---

# Verifiable Gate: Hard Dual-Layer Evidence Enforcement for ARIS

Upgrades ARIS's advisory `/experiment-audit`, `/result-to-claim`, and `/paper-claim-audit` stages into a **fail-closed, hard-blocking dual-layer gate** validated across 112 controlled runs (cutting unblocked blocker leakage from 86.7% to 0.0%, exact McNemar $p=0.000244$).

## Why This Skill Exists

Controlled ablations on `SciIntegrity-Bench` and `AIScientistPitfalls` (`paper/main.pdf`) establish three empirical failure modes that soft/advisory review alone misses:
1. **Existence gating fails (0/15 blocked):** checking that scripts exit cleanly and write files misses denominator bugs, hardcoded prints, and log contradictions.
2. **Summary framing softens verdicts ($p=0.031250$):** passing executor narrative summaries across review boundaries drops `BLOCK_MISCONDUCT` verdicts from 90.9% to 36.4%.
3. **Same-family review induces sycophancy ($p=0.003906$):** same-model fresh-session review drops blocking from 100.0% to 18.2% and votes `APPROVE` even after listing invalid claims (5/11 runs).

## Workflow (Two Hard Layers)

### Layer 1: Deterministic Zero-Cost Mechanical Gate
Run the unified CLI directly on the target workspace (`$ARGUMENTS`, default `.`):

```bash
python3 tools/verifiable_gate.py \
  --workspace "${ARGUMENTS:-.}" \
  --report report/report.md \
  --logs out/ \
  --scripts code/ \
  --out-json audits/verifiable_gate_result.json
```

This deterministically verifies:
- **`trace_numbers.py`**: every decimal ($\ge 3$ places) traces to intact logs with matching sign (`SIGN_MISMATCH`), row-cited log file (`WRONG_LOG`), paired `±` / CI bounds (`UNPAIRED_PM/CI`), and script freshness (`CITED_STALE`).
- **`audit_code.py`**: Python AST scan for `HARDCODED_REF_PRINT`, `HARDCODED_METRIC_ARRAY`, `MOCK_FALLBACK`, `TEST_TUNING`, `OPTIMISTIC_TIE`, and `DEAD_METRIC`.
- **`claims.py` (`G1--G7`)**: if `claims.json` exists, enforces SHA-256 log integrity, completion markers, multi-seed floors, validation-only selection, pre-registered baselines, ablation logs, anti-drift chronology, and machine-parseable CIs.
- **`citation_audit.py`**: add `--bib paper/refs.bib` when auditing LaTeX manuscripts.

### Layer 2: Path-Isolated Cross-Family Blocking Audit
Never pass executor summaries, `EXPERIMENT_LOG.md`, or `NARRATIVE_REPORT.md` to the reviewer. Pass `--reviewer-provider codex-cli` (when executor is Claude) or `--reviewer-provider claude-cli` (when executor is Codex):

```bash
python3 tools/verifiable_gate.py \
  --workspace "${ARGUMENTS:-.}" \
  --report report/report.md \
  --logs out/ \
  --scripts code/ \
  --reviewer-provider codex-cli \
  --out-json audits/verifiable_gate_result.json
```

## Hard Blocking Rule

- **Exit code `0`**: `APPROVE_SUPPORTED` or `APPROVE_HONEST_REFUSAL` — delivery allowed.
- **Exit code `2`**: **HARD BLOCK**. Do NOT deliver the report or advance `/research-pipeline` to `/paper-writing`. Return *only* the mechanical error list and `audits/verifiable-gate-review.md` to the executor for a targeted repair turn, then re-run `tools/verifiable_gate.py`.
