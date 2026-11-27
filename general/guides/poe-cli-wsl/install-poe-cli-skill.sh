#!/usr/bin/env bash
# install-poe-cli-skill.sh - Install poe-cli agent skill across all AI brands
set -euo pipefail

SKILL_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/SKILL.md"
if [ ! -f "$SKILL_SRC" ]; then
    SKILL_SRC="$HOME/.agents/skills/poe-cli/SKILL.md"
fi

if [ ! -f "$SKILL_SRC" ]; then
    echo "error: SKILL.md not found" >&2
    exit 1
fi

DEST_DIRS=(
    "$HOME/.agents/skills/poe-cli"
    "$HOME/.claude/skills/poe-cli"
    "$HOME/.codex/skills/poe-cli"
    "$HOME/.gemini/config/skills/poe-cli"
)

for d in "${DEST_DIRS[@]}"; do
    mkdir -p "$d"
    cp -f "$SKILL_SRC" "$d/SKILL.md"
    echo "installed: $d/SKILL.md"
done

echo "poe-cli skill installed across all AI brands successfully."
