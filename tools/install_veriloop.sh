#!/usr/bin/env bash
# Unified installer for VeriLoop skills (Claude Code & Codex CLI).
# Usage:
#   bash tools/install_veriloop.sh --core-only [--target claude|codex|both]
#   bash tools/install_veriloop.sh --all       [--target claude|codex|both]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="core-only"
TARGET="both"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --core-only|--verifiable-only) MODE="core-only"; shift ;;
    --all)                         MODE="all"; shift ;;
    --target)                      TARGET="${2:-both}"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--core-only | --all] [--target claude|codex|both]"
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
  if [[ "$MODE" == "core-only" ]]; then
    for s in research-loop verifiable-gate bestpaper-writing; do
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
  echo "Installed $count VeriLoop skill(s) into $dest_root"
}

if [[ "$TARGET" == "claude" || "$TARGET" == "both" ]]; then
  install_to_target "${HOME}/.claude/skills"
fi
if [[ "$TARGET" == "codex" || "$TARGET" == "both" ]]; then
  install_to_target "${HOME}/.codex/skills"
fi

echo "Done! Try: $REPO_ROOT/veriloop --help"
