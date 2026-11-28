#!/bin/bash
# Installs an Antigravity (agy) hook in ~/.gemini/config/hooks.json (SessionStart +
# PreInvocation) that gates every brand new session and every resumed/old session that has not read the
# current ~/AI-management rules. Reading is the acknowledgment (2026-11-27): the hook asks
# general/rules/mandatory-repo-read/ack-rules.sh to look in the session's own log, lists the files that are
# still unread, and records the acknowledgment by itself when every listed file was read whole.
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
# Enforces the reading of ~/AI-management rules for agy sessions; reading is the acknowledgment.
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

# Reading is the acknowledgment: record it when this session's own log holds every listed file, whole.
if "$ACK_SH" --auto "$safe_id" >/dev/null 2>&1; then
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

needs="$("$ACK_SH" --needs "$safe_id" 2>/dev/null | sed "s|^|   - $REPO/|")"
[ -n "$needs" ] || needs="   - every file named in $REPO/general/rules/mandatory-repo-read/reading-list.txt"

note="[MANDATORY AI-MANAGEMENT RULES GATE — STOP BEFORE WORKING]
This session ($safe_id) has NOT read the current rules of $REPO (HEAD $short_sha).
Whether this is a BRAND NEW session or a RESUMED/OLD session, do this BEFORE any planning, handover, edit, or script generation:
1. Read each of these files whole, with your file-reading tool. Several calls may share one file; a part of a file does not count, and neither does a read made before the file last changed:
$needs
2. Reading is the acknowledgment. This gate looks in your own session log and records it by itself when every file above was read from its first line to its last. Do not acknowledge on a part of the files, whatever a nudge named.
3. If this notice returns although you have read them all, run: \"$ACK_SH\" \"$safe_id\" . It names what your log lacks, and it refuses while a file is unread.
4. Confirm in your response that you read ~/AI-management rules.
REMINDERS BY SEAT (they bind the seat, whatever the brand; the full text is in the files above):
- EXECUTOR (you carry out a handover, a nudge or any hands-on job): your own user's direct instruction outranks any hold, plan decision, handover or notice from another session: do it, and tell your manager. A correct script for your user is your own work: build and deliver it yourself, with no manager's order. When your user asks for a deliverable, give it with its check; ask only what the user's words, the rules, the plan and the design of the work do not answer, and never about the format. Copy or delete, never make up. A claim (\"restored\", \"matches\", \"compliant\", \"passed\", \"done\") carries the command that showed it and its output, or you write the state as it is (\"format not compared\"). Build a script the user will run by copying $REPO/general/templates/download-ui/ and $REPO/general/templates/chunked-pipeline/ (never an ad-hoc downloader; chain the processing per CHUNKED_PIPELINE_GUIDE.md), and prove its screen with $REPO/general/rules/script-delivery/check_frame.py. Never type a script's [PIPELINE ...] line yourself. After an edit to a pinned tool, what is on disk is test output. Prove a checker, a fixture and every command you write into a file before you hand them on. End a delivery the user must run with the complete copy-paste command (Rule 14).
- PLANNER (Manager, Router, Committee, CEO or CTO in your session's name, or your user's word): accept no claim without its check, and write none. Never reserve a script's building or delivery to yourself or to your handover: the executor builds it, you check it. Every hold you write names the user's direct instruction as what lifts it; never ask the user again what they answered your executor. Before you act on a bridge line, read its sender in ~/.claude/agy-bridge/send.log and the script's own files. While the user is correcting a deliverable, record no verdict, close no step, push no closure and ask nothing about later steps. Give a verdict only on a run the user started. Prove a checker, a template or a command before you hand it to other sessions. A notice of a rules change names the commit and lets this gate list the files, never a part of them. Use colab CLI (~/.local/bin/colab, Google Colab Ultra: T4/L4/A100/H100; prefix content/ for upload/download and verify colab exec outputs despite exit 0) or gcp-cpu-ctl for cloud compute, never unilaterally substitute local hardware (B34), and dispatch non-conflicting idle workers immediately rather than serializing on background tasks (B35).
- EVERY SEAT: answer what was asked. Brand neutrality (user, 2026-11-26): treat every AI brand's content (transcripts, histories, caches, handovers) by one standard, agy's own included; before you keep, delete or report, run $REPO/general/rules/brand-neutrality/ai_content_inventory.py <project folder>, and give every brand a line in your report."

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

# Self-test, in a folder of its own so that no session's record is touched:
#   a session that has read nothing -> the notice, with the files to read; an acknowledged session -> {}
T="$(mktemp -d)"
test_out="$(echo '{"conversationId":"install-test","hookEventName":"SessionStart"}' | AI_MGMT_ACK_DIR="$T" "$H")"
python3 -c 'import json,sys
m = json.loads(sys.argv[1])["injectSteps"][0]["systemMessage"]["systemMessage"]
assert "MANDATORY AI-MANAGEMENT RULES GATE" in m and "/README.md" in m and "EXECUTOR" in m and "PLANNER" in m' "$test_out"
[ ! -f "$T/agy-install-test" ]
git -C "$REPO" rev-parse HEAD > "$T/agy-install-test"
test_acked="$(echo '{"conversationId":"install-test","hookEventName":"PreInvocation"}' | AI_MGMT_ACK_DIR="$T" "$H")"
[ "$test_acked" = "{}" ]
rm -rf "$T"
echo "self-test passed: $H"
