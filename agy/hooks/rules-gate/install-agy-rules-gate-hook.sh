#!/bin/bash
# Installs an Antigravity (agy) hook in ~/.gemini/config/hooks.json (SessionStart +
# PreInvocation) that gates every brand new session and every unacknowledged resumed/old
# session until it reads ~/AI-management rules and runs general/rules/mandatory-repo-read/ack-rules.sh agy-<conversationId>.
# Backup: ~/.gemini/config/hooks.json.bak-rules-gate
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../../.." && pwd)"
ACK_SH="$REPO/general/rules/mandatory-repo-read/ack-rules.sh"
AGY_CFG="${AGY_CONFIG_HOME:-$HOME/.gemini/config}"
mkdir -p "$AGY_CFG/hooks"
H="$AGY_CFG/hooks/ai-management-rules-gate.sh"

cat > "$H" <<'EOF'
#!/bin/bash
# Enforces mandatory reading and acknowledgment of ~/AI-management rules for agy sessions.
# Reads camelCase JSON from stdin and outputs {"injectSteps":...} or {}.
input="$(cat)"
read -r event cid < <(printf '%s' "$input" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
print(d.get("hookEventName", "SessionStart"), d.get("conversationId", "unknown"))
' 2>/dev/null || echo "SessionStart unknown")

[ -n "$cid" ] || cid="unknown"
REPO="@REPO@"
ACK_SH="@ACK_SH@"
ACK_DIR="${AI_MGMT_ACK_DIR:-$HOME/.ai-management/rules-ack}"
mkdir -p "$ACK_DIR"

head_sha="$(git -C "$REPO" rev-parse HEAD 2>/dev/null || echo unknown)"
short_sha="$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo "$head_sha")"
safe_id="$(printf 'agy-%s' "$cid" | tr '/ ' '__' | tr -cd 'A-Za-z0-9._-')"

if [ -f "$ACK_DIR/$safe_id" ] && [ "$(cat "$ACK_DIR/$safe_id" 2>/dev/null)" = "$head_sha" ]; then
  echo '{}'
  exit 0
fi

# On PreInvocation, avoid repeating on every tool call within 120s while the agent is reading the repo.
stamp="$ACK_DIR/.notified-$safe_id"
if [ "$event" = "PreInvocation" ] && [ -f "$stamp" ]; then
  now="$(date +%s)"
  mtime="$(python3 -c 'import os,sys; print(int(os.path.getmtime(sys.argv[1])))' "$stamp" 2>/dev/null || echo 0)"
  if [ $((now - mtime)) -lt 120 ]; then
    echo '{}'
    exit 0
  fi
fi
touch "$stamp"

note="[MANDATORY AI-MANAGEMENT RULES GATE — STOP BEFORE WORKING]
This session ($safe_id) has NOT acknowledged $REPO rules at current HEAD ($short_sha).
Whether this is a BRAND NEW session or a RESUMED/OLD session, you MUST do the following BEFORE any planning, handover, edit, or script generation:
1. Read the rule and template files in $REPO:
   - $REPO/README.md
   - $REPO/general/rules/mandatory-repo-read/The_Mandatory_Repo_Read_Rule.md
   - $REPO/general/regulations/executor-regulations/The_Executor_Regulations.md
   - $REPO/general/regulations/others-repositories/The_Others_Repositories_Regulation.md
   - $REPO/general/rules/regular-remote-push/The_Regular_Remote_Push_Rule.md
   - $REPO/claude/rules/ten-years-retention/The_10_Years_Rule.md
   - $REPO/claude/rules/ultracode-workflow/The_Ultracode_Rule.md
   - $REPO/general/rules/multi-agent-dispatch/MULTI_AGENT_DISPATCH_RULES.md
   - $REPO/general/regulations/executor-regulations/EXECUTOR_RULES_BLOCK.md
   - $REPO/general/regulations/executor-regulations/HANDOVER_RULES.md
   - $REPO/general/templates/download-ui/README.md (and fetch_dst.py / download_wrapper.sh if a download task)
   - $REPO/claude/rules/thought-chain-rigor/The_Claude_Thought_Chain_Rule.md
   - $REPO/general/tools/handover-lint/README.md
   - $REPO/general/rules/project-planning/The_Project_Planning_Rule.md
   - Platform bridge guide (general/guides/agent-control-macos/ or agent-control-wsl/) as applicable.
2. Acknowledge by running: \"$ACK_SH\" \"$safe_id\"
3. Confirm in your response that you read ~/AI-management rules.
CRITICAL REMINDERS:
- For any user-run download script, you MUST copy/adapt $REPO/general/templates/download-ui/fetch_dst.py + download_wrapper.sh (exact in-place dashboard, <100-col narrow layout, status subcommand, resume, verification, caffeinate-safe single-instance guard, exit codes 0/1/2/3) — NEVER invent an ad-hoc downloader.
- End every user-run script/task delivery with the complete, exact copy-paste runnable command (Rule 14)."

python3 -c 'import json,sys; print(json.dumps({"injectSteps":[{"systemMessage":{"systemMessage":sys.argv[1]}}]}))' "$note"
EOF

sed -i.sedbak -e "s|@REPO@|$REPO|g" -e "s|@ACK_SH@|$ACK_SH|g" "$H" && rm -f "$H.sedbak"
chmod +x "$H"

HOOKS_JSON="$AGY_CFG/hooks.json"
[ -f "$HOOKS_JSON" ] && cp -p "$HOOKS_JSON" "$HOOKS_JSON.bak-rules-gate"

python3 - "$HOOKS_JSON" "$H" <<'PY'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
cmd = sys.argv[2]
data = {}
if path.exists() and path.read_text().strip():
    data = json.loads(path.read_text())
data["ai-management-rules-gate"] = {
    "SessionStart": [{"type": "command", "command": cmd, "timeout": 10}],
    "PreInvocation": [{"type": "command", "command": cmd, "timeout": 10}],
}
path.write_text(json.dumps(data, indent=2) + "\n")
PY

echo "installed: $H, wired into $HOOKS_JSON"

# Self-test unacknowledged -> emits injectSteps; acknowledged -> {}
test_out="$(echo '{"conversationId":"install-test","hookEventName":"SessionStart"}' | "$H")"
python3 -c 'import json,sys; d=json.loads(sys.argv[1]); assert "MANDATORY AI-MANAGEMENT RULES GATE" in d["injectSteps"][0]["systemMessage"]["systemMessage"]' "$test_out"
"$ACK_SH" "agy-install-test" >/dev/null
test_acked="$(echo '{"conversationId":"install-test","hookEventName":"PreInvocation"}' | "$H")"
[ "$test_acked" = "{}" ]
rm -f "${AI_MGMT_ACK_DIR:-$HOME/.ai-management/rules-ack}/agy-install-test" "${AI_MGMT_ACK_DIR:-$HOME/.ai-management/rules-ack}/.notified-agy-install-test"
echo "self-test passed: $H"
