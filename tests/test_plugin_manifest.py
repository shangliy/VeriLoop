"""Cross-platform plugin packaging manifests for VeriLoop:
  - plugin.json (Antigravity / universal root manifest)
  - .agents/plugins/marketplace.json (Antigravity / Open Agents marketplace)
  - .claude-plugin/{plugin,marketplace}.json (Claude Code)
  - .codex-plugin/plugin.json (OpenAI Codex CLI — Codex-native skill mirror)
  - .cursor-plugin/plugin.json (Cursor)
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_marketplace_exposes_veriloop_at_repo_root():
    m = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text())
    assert m["name"] == "veriloop"
    (plugin,) = m["plugins"]
    assert plugin["name"] == "veriloop" and plugin["source"] == "./"


def test_plugin_manifest_has_no_pinned_version():
    p = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text())
    assert p["name"] == "veriloop"
    assert "version" not in p, "a pinned version would freeze plugin users until it is bumped"


def test_setup_registers_the_bridge_under_the_hardcoded_server_name():
    text = (REPO / "commands" / "setup.md").read_text()
    assert 'claude mcp add codex -s user -- python3 "${CLAUDE_PLUGIN_ROOT}/mcp-servers/codex-exec/server.py"' in text
    assert "~/.aris/repo" in text
    assert (REPO / "mcp-servers" / "codex-exec" / "server.py").is_file()


def test_codex_manifest_points_at_the_codex_mirror():
    # Codex CLI prefers .codex-plugin/plugin.json and must get the spawn_agent
    # mirror, never the mainline skills that call mcp__codex__codex
    p = json.loads((REPO / ".codex-plugin" / "plugin.json").read_text())
    assert p["name"] == "veriloop"
    assert p["skills"] == "./skills/skills-codex/"
    assert "version" not in p


def test_cross_platform_plugin_manifests_are_valid():
    root_p = json.loads((REPO / "plugin.json").read_text())
    assert root_p["name"] == "veriloop"
    assert root_p["repository"] == "https://github.com/shangliy/VeriLoop"

    agents_m = json.loads((REPO / ".agents" / "plugins" / "marketplace.json").read_text())
    assert agents_m["name"] == "veriloop"
    (entry,) = agents_m["plugins"]
    assert entry["name"] == "veriloop" and entry["source"]["path"] == "./"

    cursor_p = json.loads((REPO / ".cursor-plugin" / "plugin.json").read_text())
    assert cursor_p["name"] == "veriloop"
    assert cursor_p["skills"] == "./skills"
    assert (REPO / "skills").is_dir()
