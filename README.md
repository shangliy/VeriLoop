# VeriLoop

**End-to-End Verifiable Autonomous Research Pipeline: 90+ Composable Research Skills Backed by Deterministic Evidence Gates and Path-Isolated Cross-Model Auditing.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+ Stdlib Only](https://img.shields.io/badge/Verification%20Core-Python%20Stdlib%20Only-green.svg)](#quick-start)
[![Benchmark](https://img.shields.io/badge/Controlled%20Runs-112%20Live%20Runs-0072B2.svg)](#benchmark-results)

- **Repository:** [https://github.com/shangliy/VeriLoop](https://github.com/shangliy/VeriLoop)
- **Companion Paper (arXiv Preprint):** [paper/main.pdf](paper/main.pdf) ([LaTeX](paper/main.tex))
- **Companion Paper (ICML 2027 8-Page Double-Blind):** [paper/main_icml2027.pdf](paper/main_icml2027.pdf) ([LaTeX](paper/main_icml2027.tex))
- **中文文档:** [README_CN.md](README_CN.md) · **Third-Party Attribution:** [NOTICE.md](NOTICE.md) · [Upstream ARIS Docs](docs/ARIS_UPSTREAM_README.md)
- **Self-Audited Paper:** `trace_numbers.py` **69/69 traced (0 untraced, 0 sign mismatches)** · `citation_audit.py` **26/26 verified (0 issues)** · `Best-Paper-Writing-Skill` **0 errors, 0 warnings**

---

## Why VeriLoop?

Autonomous research agents rarely fail by omitting output files; they fail by executing cleanly while reporting numbers, code paths, or conclusions that contradict their own logs. **VeriLoop** delivers a complete, convenient, and high-efficiency research pipeline in one place:

- **Complete Lifecycle (90+ Modular Skills):** Idea discovery, literature search, persistent Research Wiki, remote/local experiment execution, multi-seed statistical runs, dual-layer hard verification, automated LaTeX paper writing, and rebuttal workflows.
- **Convenient Single CLI (`./veriloop`):** One unified entry point (`gate`, `claims`, `board`, `demo`, `live`, `install`, `test`, `audit-paper`) with zero third-party dependencies for the entire deterministic verification core.
- **Efficient Fail-Fast Gating (`$0` Layer 1 → Targeted Layer 2):** Catches fabricated numbers, sign flips, Python AST integrity bugs, broken claim hashes, and missing BibTeX entries in milliseconds at `$0` LLM cost before invoking a path-isolated cross-family reviewer, backed by a hard USD budget circuit breaker.

```text
  Idea & Lit/Wiki ──▶ Experiment Execution ──▶ VeriLoop Dual-Layer Hard Gate ──▶ Paper & Rebuttal
  (90+ Modular Skills)   (Multi-Seed / GPU)         (./veriloop gate)            (Self-Audited)
                                                            │
                             ┌──────────────────────────────▼──────────────────────────────┐
                             │ Layer 1 — Deterministic Mechanical Gates ($0 LLM Cost)      │
                             │ • claims.py        : Pre-registered ledger (G1–G7, SHA-256) │
                             │ • trace_numbers.py : Signed provenance & WRONG_LOG checks   │
                             │ • audit_code.py    : 6 static Python AST integrity rules    │
                             │ • citation_audit.py: BibTeX key & citation verification     │
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

Across **112 controlled live runs** (`$46.49 / $50.00` total API budget) spanning all `11/11` `SciIntegrity-Bench` failure classes and all `4/4` `AIScientistPitfalls` ML traps:

| Governance Paradigm | Primary Blocker Leakage (`n=15`) | Exact McNemar `p` | Key Empirical Finding |
|---|---:|---:|---|
| **Existence Gate (`B1`, EviBound-style)** | `0/15` blocked (delivers all) | — | Checks output presence; misses code bugs & fabricated metrics |
| **Advisory Cross-Model Review (`B2`, ARIS-style)** | `13/15` (`86.7%`, 95% CI `[62.1%, 96.3%]`) | — | Advisory delivery leaks blockers; executor summaries soften `BLOCK_MISCONDUCT` (`90.9% → 36.4%`, `p=0.031250`) |
| **Same-Model Fresh Review (`Ours_ccr`, `n=11`)** | Only `2/11` (`18.2%`) blocked | `p = 0.003906` | **Same-family sycophancy:** lists invalid claims in JSON yet votes `APPROVE` in `5/11 (45.5%)` runs |
| **VeriLoop (`Ours_full`)** | **`0/15` (`0.0%`, 95% CI `[0.0%, 20.4%]`)** | **`p = 0.000244`** | **0% leakage**, **0% false-positive blocking (`3/3` clean approved)**, **4/4 SPR misconduct cleared in 1 repair turn** |

> **Live End-to-End Showcase (`./veriloop live`, `$0.99` total spend):** On a fresh ML classification experiment (`claude-haiku` executor + path-isolated `codex-cli` reviewer), Layer 1 verified numerical/AST provenance at `$0`, Layer 2 blocked Round 1 (`rc=2`) by uncovering 5 real methodological flaws directly from raw code and logs (confidence interval crossing zero, test-set exposure, optimizer-init seeds masquerading as independent splits, missing majority-class baseline, and convergence overclaim), and Round 2 repaired the defects while live G1 SHA-256 hashing immediately flagged an overwritten log.

---

## Quick Start

### 1. Verify Installation & Run the 10-Second Closed-Loop Demo (`$0` API cost)
```bash
git clone https://github.com/shangliy/VeriLoop.git
cd VeriLoop

# Run all 30 offline verification tests + skill catalog checks
./veriloop test

# Run the zero-API closed-loop walkthrough (Round 1 hard block -> Round 2 repair -> HTML board)
./veriloop demo

# Self-audit the companion paper (numbers + citations)
./veriloop audit-paper
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
# Install core verification skills (research-loop + verifiable-gate)
./veriloop install --verifiable-only

# Install the full VeriLoop suite (all 90+ lifecycle skills + hard verification gates)
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
| `./veriloop install [--verifiable-only \| --all]` | Install VeriLoop skills into Claude Code / Codex CLI |
| `./veriloop test` | Run all 30 offline verification unit/integration tests + catalog checks |
| `./veriloop audit-paper` | Run `trace_numbers.py` and `citation_audit.py` across `paper/sec/*.tex` |

---

## Repository Structure

| Path | Contents |
|---|---|
| `veriloop` | Unified zero-dependency CLI entry point |
| `tools/verifiable_gate.py` | Dual-layer hard-blocking gate engine (`rc=0` pass / `rc=2` block + JSON report) |
| `tools/install_veriloop.sh` | Installer for Claude Code / Codex CLI (`--verifiable-only` or `--all`) |
| `skills/research-loop/` | 5-step verifiable research loop, 38-item hostile checklist, path-only reviewer brief, and 8 stdlib scripts (`claims.py`, `trace_numbers.py`, `audit_code.py`, `run_audit.py`, `citation_audit.py`, `budget.py`, `run_seeds.py`, `render_board.py`) |
| `skills/verifiable-gate/` | Hard-blocking gate skill integrating verification across experiment and paper workflows |
| `skills/` (90+ skills), `mcp-servers/`, `templates/` | Full research lifecycle skills (idea discovery, Research Wiki, experiment orchestration, paper writing, rebuttal), incorporating MIT-licensed upstream ARIS workflows |
| `eval/` | Controlled benchmark harness (`run_benchmark.py`, `conditions.py`, `blind_judge.py`, `aggregate_tables.py`) for `SciIntegrity-Bench` and `AIScientistPitfalls` |
| `examples/` | `veriloop-walkthrough/` (zero-API demo), `mini-ml/` (minimal workspace), `live-showcase/` (real dual-model showcase) |
| `paper/` | Self-audited companion paper: [main.pdf](paper/main.pdf) (arXiv), [main_icml2027.pdf](paper/main_icml2027.pdf) (ICML 2027 8-page), `sec/*.tex`, `figures/*.pdf`, `build_tables_and_figures.py` |
| `tests/verifiable/` | 30 offline unit & integration tests covering claims, number tracing, AST auditing, citation checks, budget breaker, and `verifiable_gate.py` |

---

## Attribution & Citation

**VeriLoop** builds on MIT-licensed upstream research workflow skills from **ARIS** ([wanshuiyin/Auto-claude-code-research-in-sleep](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep), `arXiv:2605.03042`) — see [NOTICE.md](NOTICE.md) and [LICENSE](LICENSE) for full attribution. If you use VeriLoop in academic work, please cite both papers:

```bibtex
@article{veriloop2026,
  title={{VeriLoop}: Deterministic Evidence Gates and Path-Isolated Cross-Model Auditing for Autonomous Research},
  author={[Author Name(s)]},
  year={2026},
  note={Preprint / ICML 2027 submission},
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
