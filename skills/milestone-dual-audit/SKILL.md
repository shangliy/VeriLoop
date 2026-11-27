---
name: milestone-dual-audit
description: "Independent dual-model milestone evaluation using both the latest Gemini and latest Claude models in parallel after every research or paper-writing milestone (M1 Plan, M2 Experiments, M3 Draft, M4 Pre-Submission). Freezes raw artifacts with SHA-256, runs path-isolated hostile audits without executor framing, merges consensus and unique catches conservatively, and generates a prioritized next-action revision plan before advancing."
disable-model-invocation: true
---

# Milestone Dual-Model Audit (Latest Gemini + Latest Claude)

Use this skill at **every milestone checkpoint** in a research or paper-writing pipeline so major methodological, statistical, or reporting flaws are caught **before** investing further compute or publishing claims.

## When to Invoke (4 Mandatory Pipeline Checkpoints)

| Milestone | Stage | Frozen Artifacts to Audit | Gate Before Next Stage |
|---|---|---|---|
| `M1-plan` | After idea, experiment plan & claim pre-registration | `claims.json`, `EXPERIMENT_PLAN.md`, protocol scripts | Do not launch expensive experiments until protocol, baselines, and ground-truth metrics pass |
| `M2-experiments` | After experiments & aggregation scripts finish | Raw `results.jsonl` / logs, aggregation scripts (`build_tables*.py`), summary tables | **Critical:** Do not start paper drafting until metrics, ablations, variance, and mechanical gate FPR pass |
| `M3-draft` | After drafting Abstract, Intro, Method, Experiments & Figures | `paper/sec/*.tex`, `paper/figures/*.pdf`, `stats_summary.txt`, `refs.bib` | Do not polish/compile final PDF until claims match raw logs and selective reporting is eliminated |
| `M4-submission` | Final pre-arXiv / pre-venue release gate | Full compiled PDF, submission tarball, `README.md`, public repo manifest | Hard block (`rc=2`) on any unverified claim, tautological metric, or missing reproducibility artifact |

## Non-Negotiable Invariants

1. **Frozen Identical Artifacts (SHA-256):** Compute a SHA-256 manifest of every audited file before calling either model. Both Gemini and Claude evaluate the **exact same frozen snapshot**.
2. **True Parallel Independence:** Run latest **Claude** and latest **Gemini** in isolated contexts. Neither model sees the other's review, and **neither receives an executor's persuasive summary or rebuttal**.
3. **Layer-1 Pre-Audit First (`$0`):** When deterministic checkers exist (`./veriloop gate`, `./veriloop audit-paper`), attach their raw machine output and explicitly instruct both auditors to verify whether each deterministic flag is a **true defect or a false positive** (never assume a mechanical flag is a valid finding without checking the code/log).
4. **8-Point Anti-Self-Deception Rubric:** Every audit explicitly probes:
   - Tautological or circular headline metrics (config switches masquerading as detection capability)
   - Post-hoc overrides or test-set tuning in aggregation scripts
   - False positives misreported as achievements
   - Confounded or non-paired ablations (unfrozen artifacts, model strength vs. family confounding, unmeasured run variance)
   - Selective reporting (omitted baselines, held-out verdicts, clean-output yield rate)
   - Numerical, unit, sign, and code provenance against raw logs
   - Release reproducibility (ignored files, unreachable commit hashes)
   - Claim strength calibration (`supported` / `partial` / `pilot` / `unsupported` / `refuted`)
5. **Conservative Merge Rule (Never Average Away Blockers):**
   - Any `BLOCKER` or `MAJOR` from **either** Gemini or Claude sets the merged milestone status to **`BLOCK`** or **`REVISE`** (CLI exit code `2`) and halts advancement to the next stage.
   - Findings raised by **both** models are elevated as **Dual-Model Consensus**; findings raised by only one model are preserved verbatim as **Gemini-Only** or **Claude-Only** catches.
6. **Feedback → Revised Next Actions:** Every milestone run produces:
   - `<stamp>_<milestone>_claude.json` — independent Claude review
   - `<stamp>_<milestone>_gemini.json` — independent Gemini review
   - `<stamp>_<milestone>_action_plan.json` — machine-readable consensus/unique findings + prioritized next actions
   - `<stamp>_<milestone>_report.md` — concise Markdown synthesis with claim verdict table and revision checklist

## Quick Commands

```bash
# Dry-run ($0): freeze SHA-256 manifest and preview the exact isolated prompt
./veriloop milestone-audit \
  --milestone M2-experiments \
  --workspace . \
  --artifacts paper/build_tables_and_figures.py paper/out/stats_summary.txt \
  --dry-run

# Live independent dual audit (latest Claude + latest Gemini in parallel)
./veriloop milestone-audit \
  --milestone M3-draft \
  --workspace . \
  --artifacts paper/sec/0_abstract.tex paper/sec/1_intro.tex paper/sec/3_experiments.tex paper/out/stats_summary.txt paper/build_tables_and_figures.py \
  --claude-model opus \
  --gemini-model latest \
  --budget-file audits/budget.json \
  --budget-limit 10.00
```

## Acting on the Feedback (Mandatory Loop)

When `./veriloop milestone-audit` exits with code `2` (`BLOCK` or `REVISE`):

1. **Read `<stamp>_<milestone>_report.md`** — inspect the **Claim Verdict Table** and **Dual-Model Consensus** findings first, then review **Gemini-Only** and **Claude-Only** catches.
2. **Verify each finding directly against disk (`file:line`)** — never blindly accept a hallucinated critique, and never rationalize away a verified defect.
3. **Revise the next actions in priority order:**
   - **`P0 (BLOCKER)`:** Must fix the underlying experiment, metric, script, or claim (or narrow/retract the claim) before moving forward.
   - **`P1 (MAJOR)`:** Fix or run the smallest decisive follow-up check; document any resolved disagreement with disk evidence.
   - **`P2 (MINOR)`:** Batch into the next revision pass.
4. **Re-run `./veriloop milestone-audit`** on the updated frozen snapshot (passing `--prev-plan <prev_action_plan.json>` so both models verify that prior `P0/P1` items were genuinely resolved by new evidence on disk rather than silently dropped).
5. Advance to the next pipeline stage **only when exit code is `0` (`APPROVE`)** or the human user explicitly signs off on a narrowed scope.

## Files

- `scripts/milestone_dual_audit.py`: Zero-dependency parallel runner for latest Claude + latest Gemini (auto-detects local `claude`/`gemini` CLIs with Anthropic/Gemini HTTPS API fallbacks, SHA-256 freezing, `budget.py` circuit breaker, conservative feedback merger, and next-action generator).
- `references/milestone-rubric.md`: 8-point anti-self-deception rubric, stage-specific checklists (`M1–M4`), and strict JSON response contract.
