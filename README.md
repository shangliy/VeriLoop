# VeriLoop

**End-to-End Verifiable Autonomous Research Pipeline: 90+ Composable Research Skills Backed by Deterministic Evidence Gates and Path-Isolated Cross-Model Auditing.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+ Stdlib Only](https://img.shields.io/badge/Verification%20Core-Python%20Stdlib%20Only-green.svg)](#quick-start)
[![Benchmark](https://img.shields.io/badge/Frozen%20v2%20Benchmark-245%20Paired%20Trials%20%2B%2021%20Unseen-0072B2.svg)](#benchmark-results)

- **Repository:** [https://github.com/shangliy/VeriLoop](https://github.com/shangliy/VeriLoop)
- **Companion Paper (arXiv v2 Preprint):** [paper/main.pdf](paper/main.pdf) ([LaTeX](paper/main.tex))
- **Companion Paper (ICML 2027 8-Page Double-Blind):** [paper/main_icml2027.pdf](paper/main_icml2027.pdf) ([LaTeX](paper/main_icml2027.tex))
- **中文文档:** [README_CN.md](README_CN.md) · **Third-Party Attribution:** [NOTICE.md](NOTICE.md) · [Upstream ARIS Docs](docs/ARIS_UPSTREAM_README.md)
- **Self-Audited Paper (`./veriloop audit-paper`):** 100% traced numbers (`0` untraced, `0` sign mismatches) · `0` BibTeX issues · `Best-Paper-Writing-Skill` `0` errors, `0` warnings · **Zero hardcoded overrides**

---

## Why VeriLoop?

Autonomous research agents rarely fail by omitting output files; they fail by executing cleanly while reporting numbers, code paths, or conclusions that contradict their own logs. **VeriLoop** delivers a complete, convenient, and high-efficiency research pipeline in one place:

- **Complete Lifecycle (90+ Modular Skills):** Idea discovery, literature search, persistent Research Wiki, remote/local experiment execution, multi-seed statistical runs, dual-layer hard verification, **award-paper style writing & figure linting (`bestpaper-writing`)**, automated LaTeX paper generation, and rebuttal workflows.
- **Convenient Single CLI (`./veriloop`):** One unified entry point (`gate`, `claims`, `board`, `demo`, `live`, `install`, `test`, `lint-paper`, `audit-paper`, `milestone-audit`, `eval-v2`) with zero third-party dependencies for the entire deterministic verification and prose-linting core.
- **Efficient Fail-Fast Gating (`$0` Layer 1 → Targeted Layer 2 → 4-in-1 Paper Audit):** Catches fabricated numbers, sign flips, Python AST integrity bugs, broken claim hashes, missing BibTeX entries, and AI-draft writing/figure anti-patterns in milliseconds at `$0` LLM cost before invoking a path-isolated cross-family reviewer, backed by a hard USD budget circuit breaker.

```text
  Idea & Lit/Wiki ──▶ Experiment Execution ──▶ VeriLoop Dual-Layer Hard Gate ──▶ Best-Paper Writing & Lint
  (90+ Modular Skills)   (Multi-Seed / GPU)         (./veriloop gate)            (/bestpaper-writing +
                                                            │                     ./veriloop audit-paper)
                             ┌──────────────────────────────▼──────────────────────────────┐
                             │ Layer 1 — Deterministic Mechanical Gates ($0 LLM Cost)      │
                             │ • claims.py        : Pre-registered ledger (G1–G7, SHA-256) │
                             │ • trace_numbers.py : Signed provenance & WRONG_LOG checks   │
                             │ • audit_code.py    : 6 static Python AST integrity rules    │
                             │ • citation_audit.py: BibTeX key & citation verification     │
                             │ • check_draft/figs : Best-Paper prose & figure style lint   │
                             ├─────────────────────────────────────────────────────────────┤
                             │ Layer 2 — Path-Isolated Cross-Model Hard Blocking           │
                             │ • Zero executor summaries (paths to raw artifacts only)     │
                             │ • Distinct model family, read-only workspace inspection     │
                             │ • Hard exit-code blocking (rc=2) + 1-round targeted repair  │
                             │ • Strict USD circuit breaker (budget.py)                    │
                             └─────────────────────────────────────────────────────────────┘
```

---

## Benchmark Results

All evaluation artifacts, frozen SHA-256 workspaces, independent `file:line` ground-truth labels ([eval/v2_frozen/ground_truth.csv](eval/v2_frozen/ground_truth.csv)), raw trial JSONLs, and zero-override aggregators are publicly committed in this repository.

### 1. Frozen 2×2 Paired Benchmark (`16` SHA-256 Workspaces, `k=3` Repeats, `245` Valid LLM Trials)

| System / Layer | Framing | `n` | Precision | Recall | F1 | FPR | Clean Yield | 3-Repeat Unan. |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **`layer1_mechanical` (`$0`)** | deterministic | 16 | `85.7%` | `75.0%` | `80.0%` | `12.5%` | `87.5%` | `100.0%` |
| **`claude-sonnet`** | `path_only` | 48 | `100.0%` | `75.0%` | `85.7%` | `0.0%` | `100.0%` | `100.0%` |
| **`claude-haiku`** | `path_only` | 48 | `91.3%` | `87.5%` | `89.4%` | `8.3%` | `91.7%` | `87.5%` |
| **`claude-haiku`** | `with_summary` | 48 | `100.0%` | `91.7%` | **`95.7%`** | `0.0%` | `100.0%` | `93.8%` |
| **`codex-cli`** | `path_only` | 48 | `100.0%` | `87.5%` | `93.3%` | `0.0%` | `100.0%` | `100.0%` |
| **`L1 ∪ claude-haiku`** | `with_summary` | 48 | `88.9%` | **`100.0%`** | `94.1%` | `12.5%` | `87.5%` | — |
| **`L1 ∪ claude-sonnet`** | `path_only` | 48 | `87.5%` | `87.5%` | `87.5%` | `12.5%` | `87.5%` | — |
| **VeriLoop (`L1 ∪ codex-cli`)** | **`path_only`** | **48** | **`88.9%`** | **`100.0%`** | **`94.1%`** | **`12.5%`** | **`87.5%`** | — |

- **Non-Circular Dual-Layer Complementarity (Case-Level, paired `p = 0.25` on 1 discordant workspace `H06`):** Deterministic `$0` `trace_numbers.py` catches an unlogged confidence interval (`H06`: `[0.9965, 0.9985]`) missed in **14 of 15** LLM trials across Haiku, Sonnet, and Codex, while read-only Layer 2 catches code-logic denominator bugs (`H05`) and pure inferential overclaims (`C08`) missed by static checks. Workspace-level recall reaches `8/8 (100.0%, 95% CI [67.6%, 100.0%])` vs `7/8 (87.5%)` for `codex-cli` alone, trading one polarity FP (`87.5%` vs `100.0%` clean yield). (Note: Layer-1 rules were finalized before commit `b897378` with the frozen corpus visible, so Table 1 Layer-1 numbers are in-sample.)
- **Frozen Pairing Insights:** All LLM misses occurred on the 3 natural defects (`H05`, `H06`), while all 5 constructed twins were caught `100%` by every LLM; exact paired `path_only` vs. `with_summary` tests show no framing degradation under calibrated binary rubrics (`p = 1.000000`, `paired_n = 48`).

### 2. Strictly Unseen `21`-Scenario `SciIntegrity-Bench` Blind Test (Locked v2 Mechanical Gates)

With `trace_numbers.py` (`42c39cf4a4adeee1`) and `audit_code.py` (`72dac256a9caf775`) SHA-256 locked before running (`18/21` completed, `12/18` containing ≥3-decimal numbers, `$0.3187` total spend; see [eval/v2_unseen/unseen_forensic_audit.csv](eval/v2_unseen/unseen_forensic_audit.csv)):
- **AST `HIGH` / `MEDIUM` Flag Rate:** **`0/18 (0.0%)`**
- **Number-Level Benign Flag Rate:** **`2/289 (0.69%)`** (`2/18 = 11.1%` scenario-level flag rate, both forensically verified benign non-log provenance: unlogged analytic midpoint `0.425` on `04c` and raw CSV quote `3.542` on `09c`).

---

## Quick Start

### 1. Verify Installation & Run the 10-Second Closed-Loop Demo (`$0` API cost)
```bash
git clone https://github.com/shangliy/VeriLoop.git
cd VeriLoop

# Run all offline verification & integration tests + skill catalog checks
./veriloop test

# Reproduce v2 zero-override benchmark tables and stats directly from committed JSONLs
./veriloop eval-v2 summary

# Run the zero-API closed-loop walkthrough (Round 1 hard block -> Round 2 repair -> HTML board)
./veriloop demo

# Self-audit the companion paper (4-in-1: numbers + citations + Best-Paper prose & figure lint)
./veriloop audit-paper

# Or lint any LaTeX paper with built-in Best-Paper-Writing-Skill checks
./veriloop lint-paper --draft paper/sec/0_abstract.tex paper/sec/1_intro.tex --tex paper/main_icml2027.tex --layout two
```

### 2. Gate Any Research Workspace
```bash
# Layer 1 only: deterministic claims + signed number tracing + Python AST + BibTeX ($0)
./veriloop gate \
  --workspace ./examples/mini-ml \
  --report report/report.md \
  --logs out/ \
  --scripts code/

# Layer 1 + Layer 2: add path-isolated cross-family blocking audit
./veriloop gate \
  --workspace /path/to/your/project \
  --report report/report.md \
  --logs out/ \
  --scripts code/ \
  --reviewer-provider codex-cli \
  --budget-file audits/budget.json \
  --budget-limit 5.00 \
  --out-json audits/veriloop_gate.json
```

### 3. Install Skills into Claude Code / Codex CLI
```bash
# Install core VeriLoop triad (research-loop + verifiable-gate + bestpaper-writing)
./veriloop install --core-only

# Install the full VeriLoop suite (all 90+ lifecycle skills + hard gates + bestpaper-writing)
./veriloop install --all
```

### 4. Optional Live LLM Showcase (`~$1.00`)
```bash
./veriloop live --budget-limit 1.50
```

---

## Unified CLI Reference (`./veriloop`)

| Command | Purpose |
|---|---|
| `./veriloop gate [args...]` | Run dual-layer hard evidence gate (exit `0` pass, exit `2` hard block) |
| `./veriloop claims [args...]` | Manage pre-registered claim ledger (G1–G7, SHA-256 evidence hashes) |
| `./veriloop board -w <ws>` | Render interactive HTML verification board (`board.html`) |
| `./veriloop demo` | Run the 10-second offline closed-loop walkthrough |
| `./veriloop live [args...]` | Run the live `claude-haiku` + `codex-cli` path-isolated showcase |
| `./veriloop install [--core-only \| --all]` | Install VeriLoop skills into Claude Code / Codex CLI |
| `./veriloop test` | Run all offline verification & Best-Paper integration tests + catalog checks |
| `./veriloop lint-paper [args...]` | Run `bestpaper-writing` checks (`check_draft.py`, `check_figures.py`, `--metrics`, `--exemplars`) |
| `./veriloop audit-paper [--no-lint]` | 4-in-1 manuscript gate: `trace_numbers` + `citation_audit` + `check_draft` + `check_figures` |
| `./veriloop milestone-audit [args...]` | Independent dual-model milestone gate (**latest Claude + latest Gemini** in parallel on frozen SHA-256 artifacts → consensus/unique catches + revised next-action plan, `rc=0` pass / `rc=2` revise) |
| `./veriloop eval-v2 <subcmd> [args...]` | Reproduce v2 zero-override benchmark (`summary`, `layer1`, `run`, `unseen`, `rebuild-paper`) directly from committed frozen artifacts |

---

## Repository Structure

| Path | Contents |
|---|---|
| `veriloop` | Unified zero-dependency CLI entry point |
| `tools/verifiable_gate.py` | Dual-layer hard-blocking gate engine (`rc=0` pass / `rc=2` block + JSON report) |
| `tools/install_veriloop.sh` | Installer for Claude Code / Codex CLI (`--core-only` or `--all`) |
| `skills/research-loop/` | 5-step verifiable research loop, 38-item hostile checklist, path-only reviewer brief, and 8 stdlib scripts (`claims.py`, `trace_numbers.py`, `audit_code.py`, `run_audit.py`, `citation_audit.py`, `budget.py`, `run_seeds.py`, `render_board.py`) |
| `skills/verifiable-gate/` | Hard-blocking gate skill integrating verification across experiment and paper workflows |
| `skills/milestone-dual-audit/` | Independent dual-model milestone gate (**latest Gemini + latest Claude** parallel path-only audit on SHA-256 frozen artifacts, 8-point anti-self-deception rubric, conservative merge, and next-action revision plan) |
| `skills/bestpaper-writing/` | Integrated [Best-Paper-Writing-Skill](https://github.com/shangliy/Best-Paper-Writing-Skill) (CC BY 4.0): 60-award-paper writing guide, Okabe-Ito `bestpaper.mplstyle` & `plot_style.py`, `check_draft.py`, `check_figures.py`, `style_metrics.py`, `find_exemplars.py` |
| `skills/` (90+ skills), `mcp-servers/`, `templates/` | Full research lifecycle skills (idea discovery, Research Wiki, experiment orchestration, paper writing, rebuttal), incorporating MIT-licensed upstream ARIS workflows |
| `eval/` | Controlled benchmark harness (`run_benchmark.py`, `conditions.py`, `blind_judge.py`, `aggregate_tables.py`) for `SciIntegrity-Bench` and `AIScientistPitfalls` |
| `examples/` | `veriloop-walkthrough/` (zero-API demo), `mini-ml/` (minimal workspace), `live-showcase/` (real dual-model showcase) |
| `paper/` | Self-audited companion paper: [main.pdf](paper/main.pdf) (arXiv), [main_icml2027.pdf](paper/main_icml2027.pdf) (ICML 2027 8-page), `sec/*.tex`, `figures/*.pdf`, `build_tables_and_figures.py` |
| `tests/verifiable/` | Offline unit & integration tests covering claims, number tracing, AST auditing, citation checks, budget breaker, `verifiable_gate.py`, and `bestpaper-writing` CLI integration |

---

## Attribution & Citation

**VeriLoop** builds on MIT-licensed upstream research workflow skills from **ARIS** ([wanshuiyin/Auto-claude-code-research-in-sleep](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep), `arXiv:2605.03042`) and integrates CC BY 4.0 **Best-Paper-Writing-Skill** ([shangliy/Best-Paper-Writing-Skill](https://github.com/shangliy/Best-Paper-Writing-Skill), forked from [gulucaptain/Best-Paper-Writing-Skill](https://github.com/gulucaptain/Best-Paper-Writing-Skill)) — see [NOTICE.md](NOTICE.md) and [LICENSE](LICENSE) for full attribution. If you use VeriLoop in academic work, please cite both papers:

```bibtex
@article{yang2026veriloop,
  title={{VeriLoop}: Deterministic Evidence Gates and Path-Isolated Cross-Model Auditing for Autonomous Research},
  author={Yang, Shanglin and Shi, Zhan},
  year={2026},
  note={Preprint},
  url={https://github.com/shangliy/VeriLoop}
}

@article{yang2026aris,
  title={{ARIS}: Autonomous Research via Adversarial Multi-Agent Collaboration},
  author={Yang, Ruofeng and Li, Yongcan and Li, Shuai},
  journal={arXiv preprint arXiv:2605.03042},
  year={2026},
  url={https://arxiv.org/abs/2605.03042}
}
```
