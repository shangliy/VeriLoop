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
- **Convenient Single CLI (`./veriloop`):** One unified entry point (`gate`, `verify-cites`, `fetch-bib`, `bind`, `review-ui`, `audit-pdf`, `gpu-showcase`, `claims`, `board`, `demo`, `live`, `install`, `test`, `lint-paper`, `audit-paper`, `milestone-audit`, `eval-v2`) with zero third-party dependencies for the entire deterministic verification, log-binding, citation-API, and interactive review-UI core.
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

## How VeriLoop Compares

> *While most AI research tools focus on generating papers faster, **VeriLoop** focuses on making every number, plot, citation, and claim line-by-line auditable before release.*

| System / Project | Category | End-to-End Exp → Paper | Hard Mechanical Gates (AST / Signed Trace) | Auto-Bind Logs → LaTeX & Figs (TB/W&B/CSV) | Online Citation & Abstract Gate | Award-Paper Style & Fig Lint | Interactive Audit UI (Paper ↔ Log) | Frozen Paired + Unseen Eval |
|---|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| **AI-Scientist / v2** (Sakana) | Autonomous research agent | ✅ (tree search) | ❌ (LLM self-review) | ⚠️ (custom scripts) | ⚠️ (S2 search, non-blocking) | ❌ | ❌ | ❌ |
| **ARIS** (upstream base) | Cross-model research workflow | ✅ (65+ skills) | ❌ (advisory review) | ❌ | ❌ | ❌ | ❌ | ❌ (1 run) |
| **EviBound** | Execution existence gate | ⚠️ (Colab runner) | ⚠️ (file existence / `rc=0`) | ❌ (MLflow schema) | ❌ | ❌ | ❌ | ⚠️ (8 self-authored) |
| **FabScore / FLAWS / PaperAudit** | Post-hoc audit benchmarks | ❌ (post-hoc) | ⚠️ (FabScore re-exec) | ❌ | ⚠️ (partial) | ❌ | ❌ | ✅ (post-hoc corpora) |
| **PaperQA2 / OpenScholar / STORM** | Literature RAG & synthesis | ❌ (lit/writing) | ❌ | ❌ | ✅ (full-text RAG) | ❌ | ⚠️ (cite links) | ✅ (lit QA benchmarks) |
| **AI-research-feedback** (`claesbackman`) | Multi-agent writing feedback & dissemination | ❌ (post-draft review) | ❌ (LLM subagents, advisory) | ❌ | ⚠️ (LLM check, no API gate) | ✅ (`voice-builder` + Beamer/web) | ⚠️ (`explain-diff` HTML) | ❌ |
| **Overleaf / Cursor + LaTeX** | Collaborative / IDE editors | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ (no log binding) | — |
| **VeriLoop (Ours)** | **Verifiable end-to-end research & paper pipeline** | ✅ (**90+ skills + real GPU showcase**) | ✅ (**`$0` AST + signed trace + G1–G7 + XMR**) | ✅ (**stdlib TB / W&B / CSV → macros, tables, PDFs**) | ✅ (**arXiv / Crossref / S2 gate + abstract check + `fetch-bib`**) | ✅ (**60-award-paper lint + Okabe-Ito**) | ✅ (**zero-dep split-pane `review-ui`**) | ✅ (**16 frozen + 21 unseen, zero overrides**) |

*Note on complementary strengths:* Full-text literature RAG tools (e.g., PaperQA2 / OpenScholar) remain stronger for large-scale multi-document synthesis, and AI-Scientist-v2 demonstrates broader open-ended tree-search exploration; VeriLoop is complementary to Cursor/Overleaf and specialized RAG tools, providing the missing deterministic verification and log-to-LaTeX provenance layer.

---

## Benchmark Results

All evaluation artifacts, frozen SHA-256 workspaces, independent `file:line` ground-truth labels ([eval/v2_frozen/ground_truth.csv](eval/v2_frozen/ground_truth.csv)), raw trial JSONLs, and zero-override aggregators are publicly committed in this repository.

### 1. Frozen Paired Benchmark (`16` SHA-256 Workspaces, `9` Clean / `7` Defective under Unified Route A Rule, `k=3`, `245` Valid LLM Trials)

| System / Layer | Framing | `n` | Precision | Recall | F1 | FPR | Clean Yield | 3-Repeat Unan. |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **`layer1_mechanical` (`$0`)** | deterministic | 16 | `71.4%` | `71.4%` | `71.4%` | `22.2%` | `77.8%` | `100.0%` |
| **`claude-sonnet`** | `path_only` | 48 | `100.0%` | `85.7%` | `92.3%` | `0.0%` | `100.0%` | `100.0%` |
| **`claude-haiku`** | `path_only` | 48 | `91.3%` | `100.0%` | `95.5%` | `7.4%` | `92.6%` | `87.5%` |
| **`claude-haiku`** | `with_summary` | 48 | `95.5%` | `100.0%` | `97.7%` | `3.7%` | `96.3%` | `93.8%` |
| **`codex-cli`** | `path_only` | 48 | **`100.0%`** | **`100.0%`** | **`100.0%`** | **`0.0%`** | **`100.0%`** | `100.0%` |
| **`L1 ∪ claude-haiku`** | `path_only` | 48 | `72.4%` | `100.0%` | `84.0%` | `29.6%` | `70.4%` | — |
| **`L1 ∪ claude-haiku`** | `with_summary` | 48 | `77.8%` | `100.0%` | `87.5%` | `22.2%` | `77.8%` | — |
| **`L1 ∪ claude-sonnet`** | `path_only` | 48 | `75.0%` | `85.7%` | `80.0%` | `22.2%` | `77.8%` | — |
| **VeriLoop (`L1 ∪ codex-cli`, strict hard union)** | **`path_only`** | **48** | **`77.8%`** | **`100.0%`** | **`87.5%`** | **`22.2%`** | **`77.8%`** | — |

- **Pre-Filtering Coverage vs. Strict-Blocking Trade-Off:** Under a unified post-audit labeling rule adopted across both splits (disclosed, **arithmetically correct** derivations from logged counts—such as `H06`'s normal-approximation CI `[0.9965, 0.9985]` and unseen `04c`'s analytic midpoint `0.425`—are `CLEAN` provenance gaps, not fabrications; dual-label sensitivity under original `H06=DEFECTIVE` is reported in Appendix Table 5), `$0` locked v2 Layer 1 (`eval/v2_frozen/locked/`, in-sample) blocks **`5/7 (71.4%)` defective workspaces** (`4/7 = 57.1%` directly attributable plus `1/7` incidental via `$m` unit rescaling on `C05`, verified by `eval/v2_frozen/counterfactual_c05.json`) before paid review while read-only `codex-cli` resolves the remaining logic (`H05`) and inferential (`C08`) flaws for `7/7 (100.0%)` recall. Hard-blocking on Layer-1 numerical warnings lowers clean yield to `77.8%` via two benign provenance FPs (`H06`, `C04`), motivating a practical cascade where high-precision AST checks hard-block immediately and numerical provenance diagnostics feed Layer 2.
- **Frozen Pairing Insights:** Every LLM auditor caught `5/5` constructed defect twins, while `claude-sonnet` missed natural denominator bug `H05` in `6/6` repeats; workspace-level paired `path_only` vs. `with_summary` tests show zero majority-vote flips (`p = 1.000000`, `n = 16` workspaces; low power). Post-v2 v3 `trace_numbers.py` (`--data`, unsigned prose polarity) was motivated by `C04`/`09c` (in-sample) and awaits a fresh held-out benchmark before claiming out-of-sample v3 FP reductions.

### 2. Strictly Unseen `21`-Scenario `SciIntegrity-Bench` Blind Test (Locked v2 Mechanical Gates)

With `eval/v2_frozen/locked/trace_numbers_v2.py` (`42c39cf4a4adeee1`) and `audit_code_v2.py` (`72dac256a9caf775`) SHA-256 locked before running (`18/21` completed, all `18/18` verified trap-avoiding `CLEAN` against official checklists, `12/18` containing ≥3-decimal numbers, `$0.3187` total spend; see [eval/v2_unseen/unseen_forensic_audit.csv](eval/v2_unseen/unseen_forensic_audit.csv) and committed forensic files under `eval/v2_unseen/workspaces/`):
- **AST `HIGH` / `MEDIUM` Out-of-Sample FPR:** **`0/18 (0.0%)`**
- **Number-Level Out-of-Sample FPR:** **`2/289 (0.69%)`** (`2/18 = 11.1%` scenario-level FPR: unlogged analytic midpoint `0.425` on `04c` and raw CSV quote `3.542` on `09c`).
- **Out-of-Sample Mechanical Recall:** Unmeasured (`0/18` completed unseen runs triggered a benchmark trap).

### 3. Long-Horizon Real-GPU End-to-End Case Study (`42` RTX 3060 Ti Runs)

Committed in [examples/gpu-overnight-research/](examples/gpu-overnight-research/) (`bash examples/gpu-overnight-research/run_reproduce.sh`): a crash-resumable 42-run multi-seed PyTorch AMP fp16 study (`5548.4s` / `92.47 min` GPU time, `593.0 MB` peak VRAM) across an 8-stage CIFAR-10 ladder (30 epochs, 3 seeds) and a 6-stage Fashion-MNIST ladder (15 epochs, 3 seeds):
- **Live Per-Stage Governance (`$0` API cost):** **`14/14` stage gates passed** on `wiki/RESEARCH_WIKI.md` (`1365` cumulative traced decimals, `0` untraced, `0` sign mismatches, `0` AST `HIGH`, `81.8 ms` median latency), and `4/4` pre-registered claims pass `7/7` ledger gates (`G1–G7`, `0` post-evidence revisions).
- **Zero-Transcription Binding & Verified Paper:** `./veriloop bind` ingests 126 TensorBoard/W&B files into `\vlC*` / `\vlF*` LaTeX macros, Booktabs tables, and Okabe-Ito PDFs → compiled ICML-style report ([overnight_study.pdf](examples/gpu-overnight-research/paper/overnight_study.pdf): **`75/75` expanded PDF numbers traced**, `0` Type-3 fonts, `0` warnings, `10/10` arXiv/Crossref/S2 verified references) + interactive split-pane [review_ui.html](examples/gpu-overnight-research/review_ui.html).
- **Real Empirical Findings:** On CIFAR-10, `M7_SEResNet_Full` reaches `0.9193±0.0004` (`+14.06 pp` over `M1_PlainCNN`); across both datasets, unaugmented `M2_ResNet_Base` is severely overconfident (`raw_ece=0.1261 → cal_ece=0.0098`, `T*=2.6460`), whereas Label Smoothing (`T*=0.7234` / `0.6716`) and Mixup (`T*=0.6449`) invert into underconfidence until validation-fitted `T*<1` restores sub-1.5% ECE.

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
| `./veriloop verify-cites <doc> --bib <refs.bib> --online --check-claims` | Hard literature gate querying **arXiv / Crossref / Semantic Scholar** (verifies existence, title, authors, year, retractions & claim-vs-abstract consistency) |
| `./veriloop fetch-bib <arxiv\|doi\|title...> [--append-to refs.bib]` | Fetch canonical BibTeX directly from arXiv / Crossref / Semantic Scholar APIs |
| `./veriloop bind --inputs <runs...> [--out-dir paper/bound]` | Auto-bind **TensorBoard / W&B / CSV** logs → `bound_metrics.txt`, LaTeX macros, Booktabs table, SHA-256 manifest & Okabe-Ito vector PDFs |
| `./veriloop review-ui --report <files...> --logs <logs...> [--serve]` | Interactive split-pane local Web review workbench (click any number/citation in manuscript → jump straight to exact `log:line`, AST finding, or fetched abstract) |
| `./veriloop audit-pdf <main.pdf> [--max-main-pages 8] [--render-dir dir]` | Per-page compiled PDF auditor: page limit, Type-3 fonts, `??` refs, anonymity leaks, visual margin overflow & expanded-macro number tracing |
| `./veriloop gpu-showcase [--skip-train]` | Real **NVIDIA RTX 3060 Ti** PyTorch Fashion-MNIST (`12` runs) → `bind` → ICML PDF → `gate` → `review_ui.html` end-to-end trace |
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
