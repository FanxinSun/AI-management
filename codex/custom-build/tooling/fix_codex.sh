#!/usr/bin/env bash
# fix_codex.sh — automated remediation for Codex workspace routing discovery timeout (code -32603)
# and app-server IPC socket starvation / queue saturation (code -32600).
set -euo pipefail

echo "=========================================================="
echo " [Codex Auto-Remediation] Starting diagnostics and repair"
echo " Time: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "=========================================================="

# 1. Stop and disable runaway background timers
echo "[1/5] Stopping and disabling dormant cllm-catcher background timer..."
if systemctl --user list-unit-files cllm-catcher.timer &>/dev/null; then
    systemctl --user stop cllm-catcher.timer cllm-catcher.service 2>/dev/null || true
    systemctl --user disable cllm-catcher.timer 2>/dev/null || true
    echo "  ✓ cllm-catcher.timer disabled and stopped."
else
    echo "  ✓ cllm-catcher.timer not found or already removed."
fi

# 2. Reset supervisor pending backlog in state.json
echo "[2/5] Resetting supervisor state backlog..."
STATE_JSON="$HOME/.local/state/cllm-catcher/state.json"
if [ -f "$STATE_JSON" ]; then
    python3 -c '
import json, sys
p = sys.argv[1]
try:
    with open(p, "r") as f:
        data = json.load(f)
    data["pending_notices"] = []
    with open(p, "w") as f:
        json.dump(data, f, indent=2)
    print("  ✓ Cleared pending_notices in state.json")
except Exception as e:
    print(f"  ⚠ Could not reset state.json: {e}")
' "$STATE_JSON"
else
    echo "  ✓ No state.json found to reset."
fi

# 3. Patch catcher.py if offline guard or delivery break is missing
echo "[3/5] Verifying supervisor offline guard in catcher.py..."
CATCHER_PY="$HOME/.local/share/cllm-catcher/catcher.py"
if [ -f "$CATCHER_PY" ]; then
    python3 -c '
import re, sys
path = sys.argv[1]
with open(path, "r") as f:
    code = f.read()

changed = False
# Ensure delivery break exists
if "remaining = to_process[idx + 1 :] + remaining" not in code:
    old_loop = """    for notice in to_process:
        key = notice.get("key", "")
        if queue_notice(notice["message"]):
            state["alerted"][key] = now()
        else:
            state["alerted"][key] = now()"""
    new_loop = """    for idx, notice in enumerate(to_process):
        key = notice.get("key", "")
        if queue_notice(notice["message"]):
            state["alerted"][key] = now()
        else:
            state["alerted"][key] = now()
            remaining = to_process[idx + 1 :] + remaining
            break"""
    if old_loop in code:
        code = code.replace(old_loop, new_loop)
        changed = True

# Ensure offline gate in main() exists
if "if not status or not status.get(\"online\"):" not in code:
    old_main = """        process_new_events(state)
        residue = audit_residue(state)
        status = status_snapshot()
        state["last_status"] = status"""
    new_main = """        status = status_snapshot()
        state["last_status"] = status
        if not status or not status.get("online"):
            save_state(state)
            return 0

        process_new_events(state)
        residue = audit_residue(state)"""
    if old_main in code:
        code = code.replace(old_main, new_main)
        changed = True

if changed:
    with open(path, "w") as f:
        f.write(code)
    print("  ✓ Successfully applied offline guard and delivery break to catcher.py")
else:
    print("  ✓ catcher.py already has offline guard and delivery break")
' "$CATCHER_PY"
else
    echo "  ✓ catcher.py not present."
fi

# 4. Check and purge saturated queue entries in queue_1.sqlite
echo "[4/5] Inspecting and purging saturated queue threads in queue_1.sqlite..."
QUEUE_DB="$HOME/.codex/queue_1.sqlite"
if [ -f "$QUEUE_DB" ]; then
    cp "$QUEUE_DB" "${QUEUE_DB}.bak.$(date +%s)"
    python3 -c '
import sqlite3, sys
db = sys.argv[1]
con = sqlite3.connect(db)
cur = con.cursor()
# Find any thread with >= 50 queued items
cur.execute("SELECT thread_id, count(*) FROM queued_items GROUP BY thread_id HAVING count(*) >= 50")
rows = cur.fetchall()
if not rows:
    print("  ✓ No saturated queues found (all thread queues < 50 items).")
else:
    for tid, count in rows:
        cur.execute("DELETE FROM queued_items WHERE thread_id = ?", (tid,))
        print(f"  ✓ Purged {cur.rowcount} queued items for saturated thread {tid} (had {count} items).")
    con.commit()
con.close()
' "$QUEUE_DB"
else
    echo "  ✓ No queue_1.sqlite database found."
fi

# 5. Clean up hung app-server processes if socket is unresponsive
echo "[5/5] Testing Codex health and app-server responsiveness..."
if ! timeout 5 codex doctor --summary &>/dev/null; then
    echo "  ⚠ App-server is unresponsive or socket is hung. Terminating hung app-server..."
    pkill -f "codex app-server" 2>/dev/null || true
    sleep 1
    rm -rf "$HOME/.codex/app-server-control/app-server-control.sock"
    echo "  ✓ Stale socket and hung app-server cleaned."
fi

echo "Running codex doctor --summary:"
codex doctor --summary

echo "=========================================================="
echo " [Codex Auto-Remediation] Complete. Codex is ready to run."
echo "=========================================================="
