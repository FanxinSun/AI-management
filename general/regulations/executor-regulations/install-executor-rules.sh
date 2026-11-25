#!/bin/bash
# Installs the executor rules (The_Executor_Regulations.md, Part A, short form) for agy and Codex.
#
# Usage:
#   install-executor-rules.sh                 agy global rules + Codex skill + Claude Code skill; no guarded file is touched
#   install-executor-rules.sh --codex-policy  only: a short pointer to the skill in the Codex global policy
#
# What it writes:
#   agy:   a marked section in ~/.gemini/config/AGENTS.md (agy's global rules; AGY_CONFIG_HOME overrides the dir)
#   Codex: the skill ${CODEX_HOME:-~/.codex}/skills/executor-rules/SKILL.md
#   Claude Code: the skill ${CLAUDE_HOME:-~/.claude}/skills/executor-rules/SKILL.md (loaded by its description when a
#          session acts as an executor; a handover should still carry HANDOVER_RULES.md)
#   --codex-policy: a marked four-line pointer in ${CODEX_HOME:-~/.codex}/AGENTS.md
#
# ~/.codex/AGENTS.md is guarded by the user's Codex policy: only the user changes it, even when the user asks an
# agent to. So --codex-policy asks for a word typed at the terminal and refuses without one. Run it yourself, in an
# ordinary terminal tab. Agents must not run it, or feed it input.
#
# Idempotent: a re-run replaces each marked section with the current text, keeps everything else, and leaves a
# .bak-executor-rules copy of any file it changes. Works on Linux/WSL and macOS (needs bash and python3).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../../.." && pwd)"
BLOCK="$SCRIPT_DIR/EXECUTOR_RULES_BLOCK.md"
AGY_RULES="${AGY_CONFIG_HOME:-$HOME/.gemini/config}/AGENTS.md"
CODEX_ROOT="${CODEX_HOME:-$HOME/.codex}"
SKILL="$CODEX_ROOT/skills/executor-rules/SKILL.md"
CLAUDE_SKILL="${CLAUDE_HOME:-$HOME/.claude}/skills/executor-rules/SKILL.md"
CODEX_POLICY="$CODEX_ROOT/AGENTS.md"
BEGIN='<!-- BEGIN executor-rules (AI-management/executor-rules) -->'
END='<!-- END executor-rules -->'
DESCRIPTION='Rules for carrying out a handover from a manager session as its executor. No made-up facts (copy or delete), apply given lists exactly, stop on anything unclear, keep what was already accepted, log every job, report commands as they ran. Use whenever you start, continue or report on a handover, a manager nudge, or any task where another session decides and you do the hands-on work.'

[ -f "$BLOCK" ] || { echo "missing $BLOCK" >&2; exit 1; }

# upsert TARGET SECTION_FILE: replace the marked section in TARGET, or append it.
upsert() {
  local target="$1" section="$2" tmp
  mkdir -p "$(dirname "$target")"
  [ -f "$target" ] || : > "$target"
  tmp="$(mktemp)"
  python3 -I - "$target" "$section" "$BEGIN" "$END" > "$tmp" <<'PY'
import pathlib, sys
target, section_file, begin, end = sys.argv[1:5]
text = pathlib.Path(target).read_text()
section = f"{begin}\n{pathlib.Path(section_file).read_text().rstrip()}\n{end}\n"
if begin in text:
    head, rest = text.split(begin, 1)
    if end not in rest:
        sys.exit(f"refused: {target} has the begin marker but no end marker")
    out = head + section + rest.split(end, 1)[1].lstrip("\n")
else:
    sep = "" if not text.strip() else ("\n" if text.endswith("\n") else "\n\n")
    out = text + sep + section
sys.stdout.write(out)
PY
  if cmp -s "$tmp" "$target"; then
    rm -f "$tmp"; echo "unchanged: $target"; return
  fi
  [ -s "$target" ] && cp -p "$target" "$target.bak-executor-rules"
  cat "$tmp" > "$target"   # keeps the file's mode and owner
  rm -f "$tmp"
  grep -qF "$BEGIN" "$target"
  echo "installed into $target"
}

# install_skill DEST LABEL: write the block as a skill file (frontmatter + block).
install_skill() {
  local dest="$1" label="$2" tmp
  tmp="$(mktemp)"
  { printf -- '---\nname: executor-rules\ndescription: "%s"\n---\n\n' "$DESCRIPTION"; cat "$BLOCK"; } > "$tmp"
  mkdir -p "$(dirname "$dest")"
  if [ -f "$dest" ] && cmp -s "$tmp" "$dest"; then
    rm -f "$tmp"; echo "unchanged: $dest"; return
  fi
  [ -f "$dest" ] && cp -p "$dest" "$dest.bak-executor-rules"
  install -m 0644 "$tmp" "$dest"
  rm -f "$tmp"
  echo "installed $label skill: $dest"
}

if [ "${1:-}" = "--codex-policy" ]; then
  [ -f "$SKILL" ] || { echo "install the skill first: run this script without options" >&2; exit 1; }
  if ! { exec 3</dev/tty; } 2>/dev/null; then
    echo "refused: --codex-policy needs an interactive terminal; run it yourself in a terminal tab" >&2
    exit 1
  fi
  echo "This adds a four-line pointer to the guarded Codex policy $CODEX_POLICY."
  printf 'Type INSTALL to go ahead: ' > /dev/tty
  read -r answer <&3 || answer=""
  exec 3<&-
  [ "$answer" = "INSTALL" ] || { echo "cancelled" >&2; exit 1; }
  pointer="$(mktemp)"
  cat > "$pointer" <<'EOF'
## Executor rules

Whenever you act as an executor (you carry out a handover or a manager's nudge), load the `executor-rules` skill
(`~/.codex/skills/executor-rules/SKILL.md`) before the first task, and follow it for the whole job. Its rules add to
this policy and never relax it. Full text: `~/AI-management/general/regulations/executor-regulations/The_Executor_Regulations.md`.
EOF
  upsert "$CODEX_POLICY" "$pointer"
  rm -f "$pointer"
  exit 0
fi

[ $# -eq 0 ] || { echo "usage: $0 [--codex-policy]" >&2; exit 2; }
upsert "$AGY_RULES" "$BLOCK"
[ -f "${AGY_CONFIG_HOME:-$HOME/.gemini/config}/rules/AGENTS.md" ] && upsert "${AGY_CONFIG_HOME:-$HOME/.gemini/config}/rules/AGENTS.md" "$BLOCK"
install_skill "$SKILL" Codex
install_skill "$CLAUDE_SKILL" "Claude Code"
