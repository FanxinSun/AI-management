#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
SOURCE="$SCRIPT_DIR/SKILL.md"
BRIDGE_CODEX_ROOT="${CODEX_HOME:-$HOME/.codex}"
DEST_DIR="$BRIDGE_CODEX_ROOT/skills/agent-bridge"
DEST="$DEST_DIR/SKILL.md"

[ -f "$SOURCE" ] || { echo "missing skill source: $SOURCE" >&2; exit 1; }
mkdir -p "$DEST_DIR"

if [ -f "$DEST" ] && ! cmp -s "$SOURCE" "$DEST"; then
  cp "$DEST" "$DEST.bak-bridge"
fi
install -m 0644 "$SOURCE" "$DEST"
echo "installed Codex agent-bridge skill: $DEST"
