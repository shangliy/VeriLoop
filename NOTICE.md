# Third-Party Attribution & Notice

**VeriLoop** is an end-to-end verifiable autonomous research pipeline combining original MIT-licensed verification infrastructure with MIT-licensed upstream **ARIS** workflow skills and CC BY 4.0 **Best-Paper-Writing-Skill**.

## 1. VeriLoop Original Components (This Work)
- **Repository:** https://github.com/shangliy/VeriLoop
- **Paper:** *"VeriLoop: Deterministic Evidence Gates and Path-Isolated Cross-Model Auditing for Autonomous Research"* (`paper/main.pdf`, `paper/main_icml2027.pdf`).
- **License:** MIT License.
- **Components:**
  - `veriloop` — unified zero-dependency CLI (`gate`, `claims`, `board`, `demo`, `live`, `install`, `test`, `lint-paper`, `audit-paper`, `milestone-audit`)
  - `tools/verifiable_gate.py` & `tools/install_veriloop.sh` — dual-layer hard-blocking gate engine and installer
  - `skills/research-loop/` — 5-step verifiable research loop, 38-item hostile checklist, path-only reviewer brief, and 8 stdlib-only scripts (`claims.py`, `trace_numbers.py`, `audit_code.py`, `run_audit.py`, `citation_audit.py`, `budget.py`, `run_seeds.py`, `render_board.py`)
  - `skills/verifiable-gate/` — hard-blocking verification gate skill bridging experiment and paper workflows
  - `skills/milestone-dual-audit/` — independent latest-Gemini + latest-Claude parallel milestone evaluator with SHA-256 freezing, conservative feedback merger, and prioritized next-action revision plan
  - `eval/` — controlled multi-system & ablation benchmark harness for `SciIntegrity-Bench` and `AIScientistPitfalls`
  - `examples/` (`veriloop-walkthrough/`, `mini-ml/`, `live-showcase/`), `paper/`, `docs/literature-audit.md`, `pilots/`, and `tests/verifiable/`

## 2. Upstream ARIS (`Auto-claude-code-research-in-sleep`)
- **Upstream Repository:** https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep
- **Paper:** Ruofeng Yang, Yongcan Li, and Shuai Li, *"ARIS: Autonomous Research via Adversarial Multi-Agent Collaboration"*, arXiv:2605.03042 (2026).
- **License:** MIT License (`Copyright (c) 2026 wanshuiyin`), preserved verbatim in [LICENSE](LICENSE).
- **Included Upstream Components:** Base lifecycle `skills/` library (idea discovery, literature search, Research Wiki, experiment orchestration, paper writing, rebuttal, patent/grant workflows), `mcp-servers/`, `templates/`, `agents/`, `commands/`, upstream helper scripts in `tools/` (excluding `verifiable_gate.py` and `install_veriloop.sh`), `docs/ARIS_UPSTREAM_README*.md`, and upstream `tests/`.

## 3. Best-Paper-Writing-Skill (`skills/bestpaper-writing/`)
- **Integrated Repository:** https://github.com/shangliy/Best-Paper-Writing-Skill (forked from https://github.com/gulucaptain/Best-Paper-Writing-Skill)
- **License:** Creative Commons Attribution 4.0 International (**CC BY 4.0**), preserved verbatim in [skills/bestpaper-writing/LICENSE](skills/bestpaper-writing/LICENSE) and [skills/bestpaper-writing/NOTICE.md](skills/bestpaper-writing/NOTICE.md).
  - Base skill portions adapted from [Master-cai/Research-Paper-Writing-Skills](https://github.com/Master-cai/Research-Paper-Writing-Skills) (MIT License, preserved in [skills/bestpaper-writing/LICENSE-base-skill](skills/bestpaper-writing/LICENSE-base-skill)), drawing on Prof. Peng Sida's open study notes.
  - Short published-paper excerpts in `skills/bestpaper-writing/references/exemplars/` are quoted with attribution for commentary/education only (copyright remains with their respective authors; do not copy into new papers).
- **Included Components:** `skills/bestpaper-writing/` (`SKILL.md`, 60-paper references/exemplars, Okabe-Ito `assets/figures/bestpaper.mplstyle` & `plot_style.py`, `scripts/check_draft.py`, `scripts/check_figures.py`, `scripts/style_metrics.py`, `scripts/find_exemplars.py`, `scripts/intake_to_brief.py`), wired into `./veriloop lint-paper`, `./veriloop audit-paper`, `tools/skill-groups.tsv`, and `tools/install_veriloop.sh`.
