#!/bin/bash
# Appends the Ultracode rule (dynamic workflows: self-started, lower-effort subagents,
# stoppable) to a Claude Code CLAUDE.md, exactly once.
# Usage: install-ultracode-rule.sh [CLAUDE_MD]    (default: ~/.claude/CLAUDE.md)
# Works on macOS and Linux/WSL. Refuses a ~/.claude/CLAUDE.md that ~/.claude/settings.json
# guards with permissions.deny: on such a machine the section goes in through the
# user's guard-lift procedure instead.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
SECTION="$SCRIPT_DIR/CLAUDE_md_section5.md"
TARGET="${1:-$HOME/.claude/CLAUDE.md}"
MARKER='Dynamic workflows (ultracode): self-started'
SETTINGS="$HOME/.claude/settings.json"

[ -f "$SECTION" ] || { echo "missing $SECTION" >&2; exit 1; }

if [ -f "$TARGET" ] && grep -qF "$MARKER" "$TARGET"; then
  echo "already present in $TARGET"
  exit 0
fi

if [ "$TARGET" = "$HOME/.claude/CLAUDE.md" ] && [ -f "$SETTINGS" ] && command -v jq >/dev/null 2>&1 \
   && jq -e '(.permissions.deny // []) | index("Edit(~/.claude/CLAUDE.md)") != null' "$SETTINGS" >/dev/null 2>&1; then
  echo "refused: $TARGET is guarded by permissions.deny in $SETTINGS; install the section through the guard-lift procedure" >&2
  exit 1
fi

mkdir -p "$(dirname "$TARGET")"
if [ -f "$TARGET" ]; then
  cp "$TARGET" "$TARGET.bak-ultracode"
fi
cat "$SECTION" >> "$TARGET"
grep -qF "$MARKER" "$TARGET"
echo "installed into $TARGET"
