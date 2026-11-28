#!/bin/bash
# Installs send_to_tty.sh and conin_inject.ps1 into ~/.claude/agy-bridge/ (backing up
# changed copies to .bak-bridge), links ~/.local/bin/send_to_tty{,.sh} to this repo's
# script, and runs syntax + dialog-guard unit tests.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
BRIDGE_DEST="${AGY_BRIDGE_HOME:-$HOME/.claude/agy-bridge}"
LOCAL_BIN="${LOCAL_BIN:-$HOME/.local/bin}"

mkdir -p "$BRIDGE_DEST" "$LOCAL_BIN"

sync_file() {
  local src="$1" dst="$2" mode="$3"
  [ -f "$src" ] || { echo "missing $src" >&2; exit 1; }
  if [ -f "$dst" ] && ! cmp -s "$src" "$dst"; then
    cp -p "$dst" "$dst.bak-bridge"
  fi
  install -m "$mode" "$src" "$dst"
}

sync_file "$SCRIPT_DIR/send_to_tty.sh" "$BRIDGE_DEST/send_to_tty.sh" 0755
sync_file "$SCRIPT_DIR/conin_inject.ps1" "$BRIDGE_DEST/conin_inject.ps1" 0644
sync_file "$SCRIPT_DIR/codex_auto_resume.py" "$BRIDGE_DEST/codex_auto_resume.py" 0755

ln -sfn "$SCRIPT_DIR/send_to_tty.sh" "$LOCAL_BIN/send_to_tty"
ln -sfn "$SCRIPT_DIR/send_to_tty.sh" "$LOCAL_BIN/send_to_tty.sh"
ln -sfn "$SCRIPT_DIR/codex_auto_resume.py" "$LOCAL_BIN/codex-auto-resume"
ln -sfn "$SCRIPT_DIR/codex_auto_resume.py" "$LOCAL_BIN/codex_auto_resume.py"

python3 -B "$SCRIPT_DIR/test_codex_auto_resume.py"

bash -n "$SCRIPT_DIR/send_to_tty.sh"

# Unit-test claude_prompt_state and claude_open_dialog_of using a temporary HOME mock
tmp_home="$(mktemp -d)"
trap 'rm -rf "$tmp_home"' EXIT
mkdir -p "$tmp_home/.claude/sessions" "$tmp_home/.claude/projects/test-proj"
sid="11111111-2222-3333-4444-555555555555"
printf '{"pid":999999,"sessionId":"%s"}\n' "$sid" > "$tmp_home/.claude/sessions/999999.json"
cat > "$tmp_home/.claude/projects/test-proj/${sid}.jsonl" <<'JSONL'
{"type":"assistant","message":{"id":"m1","content":[{"type":"tool_use","id":"tu1","name":"AskUserQuestion","input":{}}]}}
JSONL

HOME="$tmp_home" bash -c '
set -e
src_fn="$(sed -n "/^claude_open_dialog_of()/,/^WIN_PS=/p" "'"$SCRIPT_DIR"'/send_to_tty.sh" | sed '\''$d'\'')"
eval "$src_fn"
ps_fn="$(sed -n "/^claude_prompt_state()/,/^deliver_macos()/p" "'"$SCRIPT_DIR"'/send_to_tty.sh" | sed '\''$d'\'')"
eval "$ps_fn"

[ "$(claude_open_dialog_of 999999)" = "AskUserQuestion" ] || exit 11
cat >> "'"$tmp_home"'/.claude/projects/test-proj/'"$sid"'.jsonl" <<'\''DONE'\''
{"type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"tu1","content":"ok"}]}}
DONE
[ -z "$(claude_open_dialog_of 999999)" ] || exit 12

dialog_scr="$(printf "Header\n────────────────────────\n ❯ 1. Approve\nEnter to select · ↑/↓ to navigate · Esc to cancel\n")"
[ "$(printf "%s" "$dialog_scr" | claude_prompt_state)" = "unknown" ] || exit 13

empty_scr="$(printf "Header\n────────────────────────\n❯ \n────────────────────────\n  auto mode on\n")"
[ "$(printf "%s" "$empty_scr" | claude_prompt_state)" = "empty" ] || exit 14

text_scr="$(printf "Header\n────────────────────────\n❯ hello\n────────────────────────\n")"
[ "$(printf "%s" "$text_scr" | claude_prompt_state)" = "text" ] || exit 15
'

echo "installed bridge tools to $BRIDGE_DEST and linked $LOCAL_BIN/send_to_tty{,.sh}; self-tests passed"
