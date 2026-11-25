#!/bin/bash
# Installs the agy cross-agent-bridge skill (global for every agy session).
# Destination: ${AGY_CONFIG_HOME:-~/.gemini/config}/skills/cross-agent-bridge/SKILL.md
# A changed existing file is backed up to SKILL.md.bak-bridge first. Idempotent.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
SRC="$SCRIPT_DIR/SKILL.md"
DEST_DIR="${AGY_CONFIG_HOME:-$HOME/.gemini/config}/skills/cross-agent-bridge"
[ -f "$SRC" ] || { echo "missing $SRC" >&2; exit 1; }
mkdir -p "$DEST_DIR"
if [ -f "$DEST_DIR/SKILL.md" ] && ! cmp -s "$SRC" "$DEST_DIR/SKILL.md"; then cp "$DEST_DIR/SKILL.md" "$DEST_DIR/SKILL.md.bak-bridge"; fi
install -m 0644 "$SRC" "$DEST_DIR/SKILL.md"
echo "installed agy cross-agent-bridge skill: $DEST_DIR/SKILL.md"
