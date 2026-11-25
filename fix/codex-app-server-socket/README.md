# Codex `app-server` socket starvation ("workspace routing discovery timed out")

Moved here on 2026-11-25 from the WSL agent-control guide, which every Claude Code session must read: a host fix
does not belong in a file on the reading list. The remediation script is
[`codex/custom-build/tooling/fix_codex.sh`](../../codex/custom-build/tooling/fix_codex.sh). The rule that came out
of this incident is in Part B of the Executor Regulations: supervisor and catcher loops need deduplication, queue
caps and failure cooldowns.

## As recorded on 2026-11-22

- **Symptom.** Starting `codex`, `codex --yolo`, or running `codex exec` in any workspace hangs for 17–21 seconds and aborts with:
  ```text
  Error: account/read failed: account/read failed: workspace routing discovery timed out (code -32603)
  ```
- **Cause.** The Codex CLI communicates via a local Unix socket (`~/.codex/app-server-control/app-server-control.sock`) with a background `codex app-server` daemon. When an external watcher or supervisor (such as a systemd timer or periodic script like `cllm-catcher`) loops rapid IPC calls or `codex queue` invocations against a target thread that is locked or has reached its queue capacity (`code -32600: queue cannot contain more than 100 submissions`), failed queue attempts without deduplication or cooldown accumulate into thousands of pending requests in the watcher's state store (7,662 notices observed). Running thousands of queue requests every tick floods the daemon's internal tokio message channels, starving worker threads so that new CLI client handshakes (`account/read`) time out.
  Even after introducing cooldowns and batch limits, recurrence was triggered on boot by an active 2-minute systemd timer (`cllm-catcher.timer`) firing against an inactive executor because:
  1. The supervisor script (`catcher.py`) did not gate on executor presence (`status["online"] == true`), continuing to audit residue and attempt queue deliveries while all sessions were offline.
  2. The target manager thread (`01a0bdeb-48a8-7fa3-b4cb-e75863992032`) remained saturated at 100/100 items in `~/.codex/queue_1.sqlite`, causing all new queue attempts to fail immediately (`code -32600`).
  3. `deliver_pending()` sequentially executed all 5 items in the batch without breaking on the first socket/queue error, generating repeated handshake failures that choked `app-server`.
- **Diagnostics.**
  - Check `codex doctor --summary` (fails on `reachability` or hangs).
  - Check active user systemd timers: `systemctl --user list-timers` to identify active periodic services targeting Codex.
  - Check queue saturation: query `~/.codex/queue_1.sqlite` (`SELECT thread_id, count(*) FROM queued_items GROUP BY thread_id`) for threads at or near the 100-item ceiling.
- **Fix.**
  1. Stop and disable dormant supervisor timers (`systemctl --user disable --now cllm-catcher.timer cllm-catcher.service`).
  2. Guard supervisor loops on active executor status: call `status_snapshot()` before processing events or residue audits; exit immediately (`return 0`) if `not status or not status.get("online")`.
  3. Break delivery loops immediately on error: in `deliver_pending()`, if `queue_notice()` returns `False`, break out of the batch loop instead of continuing to hammer the socket with remaining notices.
  4. Prune stale queued items from `~/.codex/queue_1.sqlite` (`DELETE FROM queued_items WHERE thread_id = ...`) to relieve queue saturation.
  5. Clear accumulated pending notices in `state.json` (`pending_notices = []`).
