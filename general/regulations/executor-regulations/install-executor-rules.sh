#!/bin/bash
# Installs the executor rules and the planner rules (The_Executor_Regulations.md, Parts A and B, short forms) for
# agy, Codex and Claude Code. The rules bind the seat, whatever the brand, so every brand gets both blocks.
#
# Usage:
#   install-executor-rules.sh                 agy global rules + Codex skills + Claude Code skills; no guarded file is touched
#   install-executor-rules.sh --codex-policy  only: a short pointer to the two skills in the Codex global policy
#
# What it writes:
#   agy:   two marked sections in ~/.gemini/config/AGENTS.md (agy's global rules; AGY_CONFIG_HOME overrides the dir):
#          the executor rules and the planner rules
#   Codex: the skills ${CODEX_HOME:-~/.codex}/skills/executor-rules/SKILL.md and .../planner-rules/SKILL.md
#   Claude Code: the skills ${CLAUDE_HOME:-~/.claude}/skills/executor-rules/SKILL.md and .../planner-rules/SKILL.md
#          (loaded by their descriptions when a session acts as an executor or sits in the planner's seat; a
#          handover should still carry HANDOVER_RULES.md)
#   --codex-policy: a marked pointer to both skills in ${CODEX_HOME:-~/.codex}/AGENTS.md
#
# ~/.codex/AGENTS.md is guarded by the user's Codex policy: only the user changes it, even when the user asks an
# agent to. So --codex-policy asks for a word typed at the terminal and refuses without one. Run it yourself, in an
# ordinary terminal tab. Agents must not run it, or feed it input.
#
# Idempotent: a re-run replaces each marked section with the current text, keeps everything else, and leaves a
# .bak-executor-rules copy of any file it changes (the file as it was before the run). Works on Linux/WSL and macOS
# (needs bash and python3).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../../.." && pwd)"
BLOCK="$SCRIPT_DIR/EXECUTOR_RULES_BLOCK.md"
PLANNER_BLOCK="$SCRIPT_DIR/PLANNER_RULES_BLOCK.md"
AGY_RULES="${AGY_CONFIG_HOME:-$HOME/.gemini/config}/AGENTS.md"
CODEX_ROOT="${CODEX_HOME:-$HOME/.codex}"
CLAUDE_ROOT="${CLAUDE_HOME:-$HOME/.claude}"
SKILL="$CODEX_ROOT/skills/executor-rules/SKILL.md"
PLANNER_SKILL="$CODEX_ROOT/skills/planner-rules/SKILL.md"
CLAUDE_SKILL="$CLAUDE_ROOT/skills/executor-rules/SKILL.md"
CLAUDE_PLANNER_SKILL="$CLAUDE_ROOT/skills/planner-rules/SKILL.md"
CODEX_POLICY="$CODEX_ROOT/AGENTS.md"
BEGIN='<!-- BEGIN executor-rules (AI-management/executor-rules) -->'
END='<!-- END executor-rules -->'
PLANNER_BEGIN='<!-- BEGIN planner-rules (AI-management/executor-rules) -->'
PLANNER_END='<!-- END planner-rules -->'
DESCRIPTION='Rules for carrying out a handover from a manager session as its executor. No made-up facts (copy or delete), apply given lists exactly, stop on anything unclear, keep what was already accepted, log every job, report commands as they ran. Use whenever you start, continue or report on a handover, a manager nudge, or any task where another session decides and you do the hands-on work.'
PLANNER_DESCRIPTION='Rules for the planner seat: a Manager, Router, Committee, CEO or CTO session that plans, orders and judges while an executor session or workflow agents do the hands-on work. Accept no claim without its check, read the sender of a bridge line and the files of the script before acting on it, let a correction by the user come first, prove what you hand out, hand over data and not judgment, ask approvals in plain text. Use whenever you write a handover or a nudge, review the report of an executor, give a verdict, relay an approval, or tell sessions of a rules change.'
BACKED_UP=""

[ -f "$BLOCK" ] || { echo "missing $BLOCK" >&2; exit 1; }
[ -f "$PLANNER_BLOCK" ] || { echo "missing $PLANNER_BLOCK" >&2; exit 1; }

# backup_once FILE: keep the file as it was before this run (one copy per run, however many sections change).
backup_once() {
  case "$BACKED_UP" in *"|$1|"*) return ;; esac
  cp -p "$1" "$1.bak-executor-rules"
  BACKED_UP="$BACKED_UP|$1|"
}

# upsert TARGET SECTION_FILE BEGIN END: replace the marked section in TARGET, or append it.
upsert() {
  local target="$1" section="$2" begin="$3" end="$4" tmp name
  name="${begin#<!-- BEGIN }"; name="${name%% *}"
  mkdir -p "$(dirname "$target")"
  [ -f "$target" ] || : > "$target"
  tmp="$(mktemp)"
  python3 -I - "$target" "$section" "$begin" "$end" > "$tmp" <<'PY'
import pathlib, sys
target, section_file, begin, end = sys.argv[1:5]
text = pathlib.Path(target).read_text()
section = f"{begin}\n{pathlib.Path(section_file).read_text().rstrip()}\n{end}"
if begin in text:
    head, rest = text.split(begin, 1)
    if end not in rest:
        sys.exit(f"refused: {target} has the begin marker but no end marker")
    out = head + section + rest.split(end, 1)[1]      # what follows the section stays as it is
else:
    sep = "" if not text.strip() else ("\n" if text.endswith("\n") else "\n\n")
    out = text + sep + section + "\n"
sys.stdout.write(out)
PY
  if cmp -s "$tmp" "$target"; then
    rm -f "$tmp"; echo "unchanged: $target ($name)"; return
  fi
  [ -s "$target" ] && backup_once "$target"
  cat "$tmp" > "$target"   # keeps the file's mode and owner
  rm -f "$tmp"
  grep -qF "$begin" "$target"
  echo "installed into $target ($name)"
}

# install_skill DEST LABEL NAME DESCRIPTION BLOCK_FILE: write the block as a skill file (frontmatter + block).
install_skill() {
  local dest="$1" label="$2" name="$3" description="$4" block="$5" tmp
  tmp="$(mktemp)"
  { printf -- '---\nname: %s\ndescription: "%s"\n---\n\n' "$name" "$description"; cat "$block"; } > "$tmp"
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
  [ -f "$SKILL" ] && [ -f "$PLANNER_SKILL" ] || { echo "install the skills first: run this script without options" >&2; exit 1; }
  if ! { exec 3</dev/tty; } 2>/dev/null; then
    echo "refused: --codex-policy needs an interactive terminal; run it yourself in a terminal tab" >&2
    exit 1
  fi
  echo "This adds a short pointer to the executor-rules and planner-rules skills to the guarded Codex policy $CODEX_POLICY."
  printf 'Type INSTALL to go ahead: ' > /dev/tty
  read -r answer <&3 || answer=""
  exec 3<&-
  [ "$answer" = "INSTALL" ] || { echo "cancelled" >&2; exit 1; }
  pointer="$(mktemp)"
  cat > "$pointer" <<'EOF'
## Executor and planner rules

Whenever you act as an executor (you carry out a handover or a manager's nudge), load the `executor-rules` skill
(`~/.codex/skills/executor-rules/SKILL.md`) before the first task, and follow it for the whole job. Whenever you sit
in the planner's seat (your user made this session a manager), load the `planner-rules` skill
(`~/.codex/skills/planner-rules/SKILL.md`) before you plan, order or judge. Their rules add to this policy and never
relax it. Full text: `~/AI-management/general/regulations/executor-regulations/The_Executor_Regulations.md`.
EOF
  upsert "$CODEX_POLICY" "$pointer" "$BEGIN" "$END"
  rm -f "$pointer"
  exit 0
fi

[ $# -eq 0 ] || { echo "usage: $0 [--codex-policy]" >&2; exit 2; }
for rules in "$AGY_RULES" "${AGY_CONFIG_HOME:-$HOME/.gemini/config}/rules/AGENTS.md"; do
  [ "$rules" = "$AGY_RULES" ] || [ -f "$rules" ] || continue
  upsert "$rules" "$BLOCK" "$BEGIN" "$END"
  upsert "$rules" "$PLANNER_BLOCK" "$PLANNER_BEGIN" "$PLANNER_END"
done
install_skill "$SKILL" Codex executor-rules "$DESCRIPTION" "$BLOCK"
install_skill "$PLANNER_SKILL" Codex planner-rules "$PLANNER_DESCRIPTION" "$PLANNER_BLOCK"
install_skill "$CLAUDE_SKILL" "Claude Code" executor-rules "$DESCRIPTION" "$BLOCK"
install_skill "$CLAUDE_PLANNER_SKILL" "Claude Code" planner-rules "$PLANNER_DESCRIPTION" "$PLANNER_BLOCK"
