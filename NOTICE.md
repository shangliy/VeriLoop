# Third-Party Attribution & Notice

**VeriLoop** is an MIT-licensed end-to-end verifiable autonomous research pipeline that combines original verification infrastructure, CLI tooling, controlled benchmark harnesses, and research with MIT-licensed upstream research workflow skills from **ARIS**.

## 1. VeriLoop Original Components (This Work)
- **Repository:** https://github.com/shangliy/VeriLoop
- **Paper:** *"VeriLoop: Deterministic Evidence Gates and Path-Isolated Cross-Model Auditing for Autonomous Research"* (`paper/main.pdf`, `paper/main_icml2027.pdf`).
- **License:** MIT License.
- **Components:**
  - `veriloop` — unified zero-dependency CLI (`gate`, `claims`, `board`, `demo`, `live`, `install`, `test`, `audit-paper`)
  - `tools/verifiable_gate.py` & `tools/install_veriloop.sh` — dual-layer hard-blocking gate engine and installer
  - `skills/research-loop/` — 5-step verifiable research loop, 38-item hostile checklist, path-only reviewer brief, and 8 stdlib-only scripts (`claims.py`, `trace_numbers.py`, `audit_code.py`, `run_audit.py`, `citation_audit.py`, `budget.py`, `run_seeds.py`, `render_board.py`)
  - `skills/verifiable-gate/` — hard-blocking verification gate skill bridging experiment and paper workflows
  - `eval/` — controlled multi-system & ablation benchmark harness for `SciIntegrity-Bench` and `AIScientistPitfalls`
  - `examples/` (`veriloop-walkthrough/`, `mini-ml/`, `live-showcase/`), `paper/`, `docs/literature-audit.md`, `pilots/`, and `tests/verifiable/`

## 2. Upstream ARIS (`Auto-claude-code-research-in-sleep`)
- **Upstream Repository:** https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep
- **Paper:** Ruofeng Yang, Yongcan Li, and Shuai Li, *"ARIS: Autonomous Research via Adversarial Multi-Agent Collaboration"*, arXiv:2605.03042 (2026).
- **License:** MIT License (`Copyright (c) 2026 wanshuiyin`), preserved verbatim in [LICENSE](LICENSE).
- **Included Upstream Components:** Base lifecycle `skills/` library (idea discovery, literature search, Research Wiki, experiment orchestration, paper writing, rebuttal, patent/grant workflows), `mcp-servers/`, `templates/`, `agents/`, `commands/`, upstream helper scripts in `tools/` (excluding `verifiable_gate.py` and `install_veriloop.sh`), `docs/ARIS_UPSTREAM_README*.md`, and upstream `tests/`.
