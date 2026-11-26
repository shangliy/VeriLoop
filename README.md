# Verifiable-ARIS

**Full-Lifecycle Autonomous Research (ARIS) + Hard Deterministic Evidence Gates and Path-Isolated Cross-Model Auditing (Verifiable Research-Loop).**

> Built on top of MIT-licensed **[ARIS](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep)** (`arXiv:2605.03042`, 85+ end-to-end research skills, Research Wiki, MCP bridges, and paper-writing workflows) upgraded with **Verifiable Research-Loop**'s zero-dependency deterministic verification gates, path-isolated cross-family hard blocking, controlled multi-benchmark harness, and self-audited companion paper.

- **Paper (arXiv Preprint):** [paper/main.pdf](paper/main.pdf) ([paper/main.tex](paper/main.tex))
- **Paper (ICML 2027 8-Page Double-Blind):** [paper/main_icml2027.pdf](paper/main_icml2027.pdf) ([paper/main_icml2027.tex](paper/main_icml2027.tex))
- **Upstream ARIS Documentation:** [docs/ARIS_UPSTREAM_README.md](docs/ARIS_UPSTREAM_README.md) · [中文版](docs/ARIS_UPSTREAM_README_CN.md) · [Attribution & License Notice](NOTICE.md)
- **Self-Audited Paper Metrics:** `trace_numbers.py` **69/69 traced (0 untraced, 0 sign mismatches)** · `citation_audit.py` **26/26 verified (0 issues)** · `Best-Paper-Writing-Skill` **0 errors, 0 warnings**

---

## Why Verifiable-ARIS?

Upstream **ARIS** provides the richest open-source autonomous research skill ecosystem (idea discovery, GPU experiment execution, Research Wiki, iterative cross-model loops, and LaTeX paper generation). However, controlled experiments across **112 live runs** (`$46.49 / $50.00` total API budget) reveal a critical **verification gap** in existing governance designs:

| Paradigm | Blocker Leakage (`n=15` Paired Tasks) | Exact McNemar `p` | Key Failure Mode Uncovered |
|---|---:|---:|---|
| **EviBound-style Existence Gate (`B1`)** | `0/15` blocked (delivers all) | — | Verifies file presence while missing code bugs & fabricated metrics |
| **ARIS-style Advisory XMR (`B2`)** | `13/15` (`86.7%` [62.1%, 96.3%]) | — | Advisory delivery leaks blockers; executor summaries soften `BLOCK_MISCONDUCT` (`90.9% → 36.4%`, `p=0.031250`) |
| **Same-Model Fresh Review (`Ours_ccr`, `n=11`)** | `2/11` (`18.2%` blocked) | `p = 0.003906` | **Same-family sycophancy**: explicitly lists invalid claims yet votes `APPROVE` in `5/11 (45.5%)` runs |
| **Verifiable-ARIS (`Ours_full`)** | **`0/15` (`0.0%` [0.0%, 20.4%])** | **`p = 0.000244`** | **0% leakage**, **0% false-positive blocking (`3/3` clean approved)**, **4/4 SPR misconduct repaired in 1 turn** |

---

## Architecture: Two Layers Working Together

```text
  ARIS Full-Lifecycle Skills (85+ skills)
  /idea-discovery ─▶ /experiment-bridge ─▶ /auto-review-loop ─▶ /paper-writing
                                                  │
                              ┌───────────────────▼───────────────────┐
                              │     Verifiable-ARIS Hard Gate         │
                              │     (tools/verifiable_gate.py)        │
                              ├───────────────────────────────────────┤
                              │ Layer 1 (Deterministic, $0 LLM cost)  │
                              │ • claims.py (G1–G7, SHA-256 hashes)   │
                              │ • trace_numbers.py (signed, WRONG_LOG)│
                              │ • audit_code.py (6 Python AST rules)  │
                              │ • citation_audit.py (BibTeX verify)   │
                              ├───────────────────────────────────────┤
                              │ Layer 2 (Path-Isolated XMR Blocker)   │
                              │ • Zero executor summaries             │
                              │ • Distinct model family, read-only    │
                              │ • Hard exit-code blocking + 1-round   │
                              │   targeted repair + USD circuit break │
                              └───────────────────────────────────────┘
```

---

## Quick Start (3 Commands)

### 1. Run all offline tests & 10-second verifiable demo (zero API cost)
```bash
python3 -m unittest discover -s tests/verifiable -v
bash examples/mini-ml/run_demo.sh
```

### 2. Run the unified Verifiable-ARIS hard gate on any research workspace
```bash
# Layer 1 only (deterministic numerical provenance + Python AST + claim ledger, $0)
python3 tools/verifiable_gate.py \
  --workspace ./examples/mini-ml \
  --report report/report.md \
  --logs out/ \
  --scripts code/

# Layer 1 + Layer 2 (path-isolated cross-family blocking audit)
python3 tools/verifiable_gate.py \
  --workspace /path/to/your/project \
  --report report/report.md \
  --logs out/ \
  --scripts code/ \
  --reviewer-provider codex-cli \
  --out-json audits/verifiable_gate_result.json
```

### 3. Install skills into Claude Code / Codex CLI
```bash
# Install ONLY the verifiable verification skills (research-loop + verifiable-gate)
bash tools/install_verifiable_aris.sh --verifiable-only

# Or install the FULL Verifiable-ARIS suite (85+ ARIS skills + verifiable gates)
bash tools/install_verifiable_aris.sh --all
```

---

## Repository Layout

| Path | Origin | Contents |
|---|---|---|
| `skills/research-loop/` | **Verifiable Research-Loop** | 5-step verifiable loop skill, 38-item hostile checklist, path-only reviewer brief, and 8 stdlib-only scripts (`claims.py`, `trace_numbers.py`, `audit_code.py`, `run_audit.py`, `citation_audit.py`, `budget.py`, `run_seeds.py`, `render_board.py`) |
| `skills/verifiable-gate/` | **Bridge Skill** | Native ARIS skill upgrading `/experiment-audit`, `/result-to-claim`, and `/paper-claim-audit` into hard blockers |
| `tools/verifiable_gate.py` | **Bridge CLI** | Single-command dual-layer gate returning exit code `0` (pass) or `2` (hard block) + structured JSON |
| `tools/install_verifiable_aris.sh` | **Installer** | Installs verifiable skills (`--verifiable-only`) or full ARIS + verifiable skills (`--all`) |
| `skills/` (85+ skills), `mcp-servers/`, `templates/`, `tools/` | **Upstream ARIS (MIT)** | Complete ARIS research workflow (`idea-discovery`, `research-wiki`, `experiment-bridge`, `auto-review-loop`, `paper-writing`, `rebuttal`, etc.) |
| `eval/` | **Verifiable Research-Loop** | Controlled benchmark harness (`run_benchmark.py`, `conditions.py`, `blind_judge.py`, `aggregate_tables.py`) for `SciIntegrity-Bench` and `AIScientistPitfalls` |
| `paper/` | **Verifiable Research-Loop** | Self-audited paper ([arXiv PDF](paper/main.pdf), [ICML 2027 PDF](paper/main_icml2027.pdf), `sec/*.tex`, `figures/*.pdf`, `build_tables_and_figures.py`, `writing_report.md`) |
| `tests/verifiable/` | **Verifiable Research-Loop** | 30 offline unit & integration tests (28 core + 2 `verifiable_gate.py` end-to-end tests) |
| `examples/mini-ml/` | **Verifiable Research-Loop** | 10-second runnable end-to-end verifiable research demo |

---

## Attribution & Citation

This repository combines MIT-licensed upstream **ARIS** with **Verifiable Research-Loop** (see [NOTICE.md](NOTICE.md) and [LICENSE](LICENSE)). If you use this repository, please cite **both** works:

```bibtex
@article{verifiable_research_loop_2026,
  title={Closing the Verification Gap in Autonomous Research: Deterministic Evidence Gates and Path-Isolated Cross-Model Auditing},
  author={[Author Name(s)]},
  year={2026},
  note={Preprint / ICML 2027 submission}
}

@article{yang2026aris,
  title={{ARIS}: Autonomous Research via Adversarial Multi-Agent Collaboration},
  author={Yang, Ruofeng and Li, Yongcan and Li, Shuai},
  journal={arXiv preprint arXiv:2605.03042},
  year={2026},
  url={https://arxiv.org/abs/2605.03042}
}
```
