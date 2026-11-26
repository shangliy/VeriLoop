#!/usr/bin/env bash
# Unified installer for Verifiable-ARIS skills (Claude Code & Codex CLI).
# Usage:
#   bash tools/install_verifiable_aris.sh --verifiable-only [--target claude|codex|both]
#   bash tools/install_verifiable_aris.sh --all             [--target claude|codex|both]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="verifiable-only"
TARGET="both"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --verifiable-only) MODE="verifiable-only"; shift ;;
    --all)             MODE="all"; shift ;;
    --target)          TARGET="${2:-both}"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--verifiable-only | --all] [--target claude|codex|both]"
      exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

install_skill_dir() {
  local src="$1"
  local dest_root="$2"
  local name
  name="$(basename "$src")"
  mkdir -p "$dest_root"
  rm -rf "$dest_root/$name"
  cp -a "$src" "$dest_root/$name"
}

install_to_target() {
  local dest_root="$1"
  local count=0
  if [[ "$MODE" == "verifiable-only" ]]; then
    for s in research-loop verifiable-gate; do
      install_skill_dir "$REPO_ROOT/skills/$s" "$dest_root"
      count=$((count + 1))
    done
  else
    for d in "$REPO_ROOT/skills"/*/; do
      local base
      base="$(basename "$d")"
      [[ "$base" == "skills-codex"* || "$base" == "shared-references" ]] && continue
      if [[ -f "$d/SKILL.md" ]]; then
        install_skill_dir "${d%/}" "$dest_root"
        count=$((count + 1))
      fi
    done
  fi
  echo "Installed $count skill(s) into $dest_root"
}

if [[ "$TARGET" == "claude" || "$TARGET" == "both" ]]; then
  install_to_target "${HOME}/.claude/skills"
fi
if [[ "$TARGET" == "codex" || "$TARGET" == "both" ]]; then
  install_to_target "${HOME}/.codex/skills"
fi

echo "Done! Try: python3 $REPO_ROOT/tools/verifiable_gate.py --help"
