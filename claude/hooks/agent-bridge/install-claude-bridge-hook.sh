#!/bin/bash
# Installs a Claude Code hook that tells every session (new, resumed, subagents, and
# already-running ones on their next prompt) how to reach agy/codex/gemini/claude
# sessions in other terminal tabs through send_to_tty.sh.
# Leaves the guarded rule hook (agent-responsibility-rule.sh) untouched; only appends
# new hook entries. Backup: ~/.claude/settings.json.bak-bridge
set -e
# Works on macOS and Linux/WSL: the repo path is taken from this script's own location.
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../../.." && pwd)"
BRIDGE_SH="$REPO/general/tools/agent-bridge/send_to_tty.sh"
SKILL="$HOME/.claude/skills/agent-bridge/SKILL.md"
mkdir -p "$HOME/.claude/hooks"
H="$HOME/.claude/hooks/agent-bridge-note.sh"
cat > "$H" <<'EOF'
#!/bin/bash
# Injects the agent-bridge method into every Claude Code session and subagent.
# Arg: SessionStart | SubagentStart | UserPromptSubmit (once per session).
event="$1"
input=$(cat)
sid=$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null)
st="$HOME/.claude/hooks/state/agent-bridge-note"
mkdir -p "$st"
if [ "$event" = UserPromptSubmit ]; then
  [ -n "$sid" ] && [ -e "$st/$sid" ] && exit 0
fi
[ -n "$sid" ] && : > "$st/$sid"
note='AGENT BRIDGE (user, 2026-11-05): agy (Antigravity), codex, gemini and other Claude Code sessions in other terminal tabs on this machine ARE reachable. SendMessage/ListAgents only see Claude sessions; for everything else use @BRIDGE_SH@: "--list" shows live sessions (KIND PID TTY CWD), then send with: send_to_tty.sh <kind>:<pid> "message" (types it into that tab and presses Enter, like the user typing); "reply" answers whoever last messaged you. Full method: the agent-bridge skill (@SKILL@). Never tell the user another session cannot be reached or started before trying this. When the user says to start/nudge a session, send it yourself immediately, quoting the user approval (any rules in ~/.claude/CLAUDE.md about who may nudge whom still apply).'
jq -n --arg e "$event" --arg n "$note" '{hookSpecificOutput:{hookEventName:$e, additionalContext:$n}}'
EOF
# fill in the real paths (the heredoc above is quoted, so nothing was expanded)
sed -i.sedbak -e "s|@BRIDGE_SH@|$BRIDGE_SH|g" -e "s|@SKILL@|$SKILL|g" "$H" && rm -f "$H.sedbak"
chmod +x "$H"

S="$HOME/.claude/settings.json"
if grep -q agent-bridge-note "$S"; then echo "already wired in $S"; exit 0; fi
cp "$S" "$S.bak-bridge"
jq '
 def h(e): {hooks:[{type:"command",command:("\"$HOME/.claude/hooks/agent-bridge-note.sh\" "+e),timeout:10}]};
 .hooks.SessionStart += [h("SessionStart")] |
 .hooks.SubagentStart += [h("SubagentStart")] |
 .hooks.UserPromptSubmit += [h("UserPromptSubmit")]' "$S.bak-bridge" > "$S.new"
jq empty "$S.new" && mv "$S.new" "$S"
echo '{"session_id":"install-test"}' | "$H" SessionStart | jq -r '.hookSpecificOutput.hookEventName'
rm -f "$HOME/.claude/hooks/state/agent-bridge-note/install-test"
echo "installed: $H, wired into $S (backup $S.bak-bridge)"
