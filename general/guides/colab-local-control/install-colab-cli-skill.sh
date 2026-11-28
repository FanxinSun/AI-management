#!/usr/bin/env bash
# Installs the `colab-cli` skill, its bundled reference guide (`references/COLAB_LOCAL_CONTROL.md`),
# and the machine-wide `~/COLAB_LOCAL_CONTROL.md` guide identically across all supported AI brands
# (Claude Code, Codex, Antigravity/Gemini CLI, and shared ~/.agents/skills).
set -euo pipefail

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_SRC="$SRC_DIR/SKILL.md"
GUIDE_SRC="$SRC_DIR/COLAB_LOCAL_CONTROL.md"
SKILL_NAME="colab-cli"
HOME_GUIDE="$HOME/COLAB_LOCAL_CONTROL.md"

for req in "$SKILL_SRC" "$GUIDE_SRC"; do
    if [ ! -f "$req" ]; then
        echo "ERROR: missing $req" >&2
        exit 1
    fi
done

TARGETS=(
    "${CLAUDE_HOME:-$HOME/.claude}/skills/$SKILL_NAME"
    "${CODEX_HOME:-$HOME/.codex}/skills/$SKILL_NAME"
    "${GEMINI_CONFIG_DIR:-$HOME/.gemini/config}/skills/$SKILL_NAME"
    "$HOME/.agents/skills/$SKILL_NAME"
)

for dir in "${TARGETS[@]}"; do
    mkdir -p "$dir/references"
    cp "$SKILL_SRC" "$dir/SKILL.md"
    cp "$GUIDE_SRC" "$dir/references/COLAB_LOCAL_CONTROL.md"
    echo "installed: $dir/SKILL.md (+ references/COLAB_LOCAL_CONTROL.md)"
done

if [ -f "$HOME_GUIDE" ] && ! cmp -s "$GUIDE_SRC" "$HOME_GUIDE"; then
    cp -p "$HOME_GUIDE" "$HOME_GUIDE.bak-colab-cli"
fi
cp "$GUIDE_SRC" "$HOME_GUIDE"
echo "installed: $HOME_GUIDE"
