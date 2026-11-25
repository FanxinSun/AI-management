#!/bin/bash
# Installs Claude Code guardrail hooks into ~/.claude/hooks/ai-management-claude-guardrails.sh
# and wires them into ~/.claude/settings.json without touching guarded CLAUDE.md or
# agent-responsibility-rule.sh. Backup: ~/.claude/settings.json.bak-claude-guardrails
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../../.." && pwd)"
LINT_PY="$REPO/general/tools/handover-lint/check_spec.py"
BRIDGE_SH="$REPO/general/tools/agent-bridge/send_to_tty.sh"
THOUGHT_DOC="$REPO/claude/rules/thought-chain-rigor/The_Claude_Thought_Chain_Rule.md"
CLAUDE_DIR="${CLAUDE_HOME:-$HOME/.claude}"
mkdir -p "$CLAUDE_DIR/hooks"
H="$CLAUDE_DIR/hooks/ai-management-claude-guardrails.sh"

cat > "$H" <<'EOF'
#!/bin/bash
# Claude Code guardrails (2026-11-24; code hygiene rewritten 2026-11-25):
#   askguard     : PreToolUse (AskUserQuestion) - block TUI picker dialogs vulnerable to bridge Enter spoofing
#   codehygiene  : PreToolUse (Write|Edit|MultiEdit) - refuse an edit of a .py file that ADDS a 1 - cdf upper tail or a
#                  hardcoded python3.X site-packages path; the check itself is check_spec.py --hook
#   thoughtchain : SessionStart | SubagentStart | UserPromptSubmit - inject T1-T5 checklist once per session update
set -u

mode="${1:-SessionStart}"
input="$(cat 2>/dev/null || true)"
REPO="@REPO@"
LINT_PY="@LINT_PY@"
BRIDGE_SH="@BRIDGE_SH@"
THOUGHT_DOC="@THOUGHT_DOC@"
SELF_NAME="ai-management-claude-guardrails.sh"

deny_json() {
  local reason="$1"
  jq -n --arg r "$reason" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
}

case "$mode" in
  askguard)
    [ "${AI_MGMT_ALLOW_ASK_DIALOG:-0}" = 1 ] && exit 0
    tool="$(printf '%s' "$input" | jq -r '.tool_name // empty' 2>/dev/null)"
    [ "$tool" = "AskUserQuestion" ] || exit 0
    deny_json "Denied by claude-guardrails (D89/D90 2026-11-24 incident): interactive AskUserQuestion picker dialogs are vulnerable to incoming send_to_tty.sh Enter keystrokes choosing '(Recommended)' options without user consent. Ask the user in plain text at the end of your response instead. (AI_MGMT_ALLOW_ASK_DIALOG is the user's switch; an agent never sets it.)"
    exit 0
    ;;
  codehygiene)
    tool="$(printf '%s' "$input" | jq -r '.tool_name // empty' 2>/dev/null)"
    case "$tool" in
      Write|Edit|MultiEdit) ;;
      *) exit 0 ;;
    esac
    fp="$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)"
    case "$fp" in
      *.py) ;;
      *) exit 0 ;;
    esac
    # The linter parses the file as it would be after the edit, so comments, docstrings, and `1 - cdf` strings are
    # ignored (path literals in code remain checked), a hunk or line that already had the pattern is left alone, and
    # `handover-lint: allow` on a line is honoured. Any doubt lets it through.
    [ -f "$LINT_PY" ] || exit 0
    py=/usr/bin/python3
    [ -x "$py" ] || py="$(command -v python3 2>/dev/null || true)"
    [ -n "$py" ] || exit 0
    reason="$(printf '%s' "$input" | "$py" -I "$LINT_PY" --hook 2>/dev/null)"; rc=$?
    if [ "$rc" -eq 10 ] && [ -n "$reason" ]; then
      deny_json "Denied by claude-guardrails (code hygiene): $reason"
    fi
    exit 0
    ;;
  SessionStart|SubagentStart|UserPromptSubmit)
    sid="$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null)"
    st_dir="${CLAUDE_HOME:-$HOME/.claude}/hooks/state/claude-guardrails-seen"
    mkdir -p "$st_dir"
    cur="$(stat -c %Y "$THOUGHT_DOC" "$0" 2>/dev/null | sort -n | tail -1)"; cur="${cur:-0}"
    if [ "$mode" = "UserPromptSubmit" ] && [ -n "$sid" ]; then
      seen="$(cat "$st_dir/$sid" 2>/dev/null || echo 0)"
      [ "$cur" -gt "$seen" ] 2>/dev/null || exit 0
    fi
    [ -n "$sid" ] && printf '%s' "$cur" > "$st_dir/$sid"
    msg="[CLAUDE THOUGHT-CHAIN & GUARDRAILS (2026-11-24, revised 2026-11-25; full text: $THOUGHT_DOC)]
1. Plain-text approvals only: AskUserQuestion pickers are blocked (D89/D90 bridge-Enter spoofing risk); ask in plain text and verify transcript + ~/.claude/agy-bridge/send.log before relaying any approval. The switches that bypass a guard (AI_MGMT_ALLOW_ASK_DIALOG, BRIDGE_FORCE_SEND, BRIDGE_FORCE_DISPATCH, AI_MGMT_RULES_GATE_OFF) are the user's: never set one yourself, and report a refused bridge send instead of forcing it.
2. Concrete specs & consumer checks: never write placeholder prose ('contract is exact'); state every flag, path pattern, schema and exit code literally, and where a step writes files that another step reads, say how they are staged (.partial, then an atomic rename) and which inputs are pinned by SHA-256; read downstream reader scripts and probe exact Python binaries before asserting support; run '$LINT_PY' before dispatching handovers/plans/stats scripts.
3. Numerical hygiene: compute an upper tail with .sf(...) for every distribution (never '1 - cdf(...)': 7% off at 8 sigma, exactly 0.0 from 8.29), adaptive MLE/root brackets, a self-test of every exported statistic at the edges of its range and far outside the expected one (for a counting statistic: n = 0, n far below B, n near B, n = 100*B), ceteris-paribus toy tables, and site.getusersitepackages() instead of hardcoded python3.X paths.
4. Seat boundaries & headers: a read-only Supervisor delegates multi-file project dump builds/runs through the logged Executor route and updates top-of-file headers when adding Addenda.
5. Canonical bridge script: '$BRIDGE_SH' (legacy ~/AI-management/agy-bridge/ path is retired)."
    jq -n --arg e "$mode" --arg m "$msg" '{hookSpecificOutput:{hookEventName:$e,additionalContext:$m}}'
    exit 0
    ;;
esac
exit 0
EOF

sed -i.sedbak \
  -e "s|@REPO@|$REPO|g" \
  -e "s|@LINT_PY@|$LINT_PY|g" \
  -e "s|@BRIDGE_SH@|$BRIDGE_SH|g" \
  -e "s|@THOUGHT_DOC@|$THOUGHT_DOC|g" "$H" && rm -f "$H.sedbak"
chmod +x "$H"

S="$CLAUDE_DIR/settings.json"
[ -f "$S" ] || echo '{}' > "$S"

if ! grep -q "ai-management-claude-guardrails" "$S"; then
  cp -p "$S" "$S.bak-claude-guardrails"
  jq '
   def h(e): {hooks:[{type:"command",command:("\"$HOME/.claude/hooks/ai-management-claude-guardrails.sh\" "+e),timeout:10}]};
   def pm(m; e): {matcher:m,hooks:[{type:"command",command:("\"$HOME/.claude/hooks/ai-management-claude-guardrails.sh\" "+e),timeout:10}]};
   .hooks = (.hooks // {}) |
   .hooks.SessionStart = ((.hooks.SessionStart // []) + [h("SessionStart")]) |
   .hooks.SubagentStart = ((.hooks.SubagentStart // []) + [h("SubagentStart")]) |
   .hooks.UserPromptSubmit = ((.hooks.UserPromptSubmit // []) + [h("UserPromptSubmit")]) |
   .hooks.PreToolUse = ((.hooks.PreToolUse // []) + [pm("AskUserQuestion"; "askguard"), pm("Write|Edit|MultiEdit"; "codehygiene")])
  ' "$S.bak-claude-guardrails" > "$S.new"
  jq empty "$S.new" && mv "$S.new" "$S"
  echo "installed: $H, wired into $S (backup $S.bak-claude-guardrails)"
else
  echo "updated script $H (already wired in $S)"
fi

# Self-tests
out_ask="$(echo '{"tool_name":"AskUserQuestion","tool_input":{}}' | "$H" askguard)"
printf '%s' "$out_ask" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null

T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
wr() { jq -n --arg f "$1" --arg c "$2" '{tool_name:"Write", tool_input:{file_path:$f, content:$c}}'; }
denied() { jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null; }

wr "$T/new1.py" 'y = 1 - stats.norm.cdf(z)' | "$H" codehygiene | denied          # a new tail bug is refused
wr "$T/new_tup.py" $'def cls_tail(sq, sqa):\n    p_sb, p_b = stats.norm.sf(sq), stats.norm.cdf(sq - sqa)\n    return float(p_sb / (1 - p_b)) if p_b < 1 else 0.0\n' | "$H" codehygiene | denied  # tuple unpacking
wr "$T/new_branch.py" $'def br(cond, z):\n    if cond:\n        p_b = stats.norm.cdf(z)\n    else:\n        p_b = 0.0\n    return 1 - p_b\n' | "$H" codehygiene | denied  # sibling branch taint
wr "$T/new2.py" 'p = 1 - stats.chi2.cdf(q, 1)' | "$H" codehygiene | denied       # for any distribution
wr "$T/new3.py" 'p = ".local/lib/python3.14/site-packages"' | "$H" codehygiene | denied
[ -z "$(wr "$T/ok.py" 'y = stats.norm.sf(z)' | "$H" codehygiene)" ]
[ -z "$(wr "$T/c.py" '# never write 1 - norm.cdf(x) or .local/lib/python3.14/site-packages' | "$H" codehygiene)" ]
[ -z "$(wr "$T/doc.py" $'"""Never use .local/lib/python3.14/site-packages."""\nimport site\n' | "$H" codehygiene)" ]
printf 'def f(x):\n    return 1 - norm.cdf(x)  # two sided\n' > "$T/old.py"
[ -z "$(jq -n --arg f "$T/old.py" '{tool_name:"Edit", tool_input:{file_path:$f, old_string:"# two sided", new_string:"# one-sided"}}' | "$H" codehygiene)" ]   # a line that already had it is left alone

out_ss="$(echo '{"session_id":"install-test"}' | "$H" SessionStart)"
printf '%s' "$out_ss" | jq -e '.hookSpecificOutput.additionalContext | contains("CLAUDE THOUGHT-CHAIN & GUARDRAILS")' >/dev/null
rm -f "$CLAUDE_DIR/hooks/state/claude-guardrails-seen/install-test"

if [ -x "$CLAUDE_DIR/hooks/agent-responsibility-rule.sh" ]; then
  resp_out="$(echo '{"session_id":"install-test"}' | "$CLAUDE_DIR/hooks/agent-responsibility-rule.sh" SessionStart)"
  rm -f "$CLAUDE_DIR/hooks/state/rules-seen-install-test"
  if printf '%s' "$resp_out" | jq -e 'has("systemMessage")' >/dev/null 2>&1; then
    echo "ERROR: agent-responsibility-rule.sh emitted setup warning: $resp_out" >&2
    exit 1
  fi
fi

echo "self-test passed: $H"
