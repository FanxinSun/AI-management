#!/usr/bin/env bash
# Installs the `gcp-cpu-compute` skill identically across all supported AI brands
# (Claude Code, Codex, Antigravity/Gemini CLI, and shared ~/.agents/skills).
set -euo pipefail

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_SRC="$SRC_DIR/SKILL.md"
SKILL_NAME="gcp-cpu-compute"

if [ ! -f "$SKILL_SRC" ]; then
    echo "ERROR: missing $SKILL_SRC" >&2
    exit 1
fi

TARGETS=(
    "${CLAUDE_HOME:-$HOME/.claude}/skills/$SKILL_NAME"
    "${CODEX_HOME:-$HOME/.codex}/skills/$SKILL_NAME"
    "${GEMINI_CONFIG_DIR:-$HOME/.gemini/config}/skills/$SKILL_NAME"
    "$HOME/.agents/skills/$SKILL_NAME"
)

for dir in "${TARGETS[@]}"; do
    mkdir -p "$dir"
    cp "$SKILL_SRC" "$dir/SKILL.md"
    echo "installed: $dir/SKILL.md"
done
