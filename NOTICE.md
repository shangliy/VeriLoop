# Third-Party Attribution & Notice

**Verifiable-ARIS** is a derivative open-source distribution combining two MIT-licensed bodies of work:

## 1. Upstream ARIS (`Auto-claude-code-research-in-sleep`)
- **Upstream Repository:** https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep
- **Paper:** Ruofeng Yang, Yongcan Li, and Shuai Li, *"ARIS: Autonomous Research via Adversarial Multi-Agent Collaboration"*, arXiv:2605.03042 (2026).
- **License:** MIT License (`Copyright (c) 2026 wanshuiyin`), preserved verbatim in `LICENSE`.
- **Included Upstream Components:** Base `skills/` library (idea discovery, literature search, experiment orchestration, Research Wiki, paper writing, rebuttal, patent/grant workflows), `mcp-servers/`, `templates/`, `agents/`, `commands/`, `tools/` (excluding `verifiable_gate.py` and `install_verifiable_aris.sh`), `docs/ARIS_UPSTREAM_README*.md`, and upstream `tests/`.

## 2. Verifiable Research-Loop Additions (This Work)
- **Paper:** *"Closing the Verification Gap in Autonomous Research: Deterministic Evidence Gates and Path-Isolated Cross-Model Auditing"* (`paper/main.pdf`, `paper/main_icml2027.pdf`).
- **License:** MIT License.
- **Added Components:**
  - `skills/research-loop/` — 5-step verifiable loop skill, 38-item hostile checklist, path-only reviewer brief, and 8 zero-dependency stdlib verification scripts (`claims.py`, `trace_numbers.py`, `audit_code.py`, `run_audit.py`, `citation_audit.py`, `budget.py`, `run_seeds.py`, `render_board.py`)
  - `skills/verifiable-gate/` & `tools/verifiable_gate.py` — native ARIS hard-blocking dual-layer bridge skill and CLI
  - `tools/install_verifiable_aris.sh` — unified skill installer
  - `eval/` — controlled multi-system & ablation evaluation harness for `SciIntegrity-Bench` and `AIScientistPitfalls`
  - `paper/`, `docs/literature-audit.md`, `examples/mini-ml/`, `pilots/`, and `tests/verifiable/`
