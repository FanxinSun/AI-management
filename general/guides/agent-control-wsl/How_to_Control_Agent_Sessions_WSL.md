# Controlling Other Agent Sessions on WSL / Linux

This is the WSL version of [the macOS guide](../agent-control-macos/How_to_Control_Agent_Sessions_macOS.md). It uses the same script, [`send_to_tty.sh`](../../tools/agent-bridge/send_to_tty.sh), and the same names, `reply`, relay correction, registry (`~/.claude/agy-bridge/`) and log. **No setup is needed.** Sessions in ordinary Windows Terminal tabs work as they are.

## How a message reaches another Windows Terminal tab

Every WSL tab looks like this:

```text
Windows Terminal tab -> wsl.exe (Windows) -> Relay(pid) -> bash -> agy/claude
```

WSL gives each tab a socket, `/run/WSL/<Relay pid>_interop`. A Windows program launched with `WSL_INTEROP` pointing at that socket starts as a **child of that tab's `wsl.exe`**.

To send a message, `send_to_tty.sh`:

1. Walks up from the target's process to its `Relay(...)` ancestor and picks that tab's socket.
2. Launches [`conin_inject.ps1`](../../tools/agent-bridge/conin_inject.ps1) through the socket.
3. The script calls `FreeConsole` and then `AttachConsole(<parent wsl.exe>)`, so it is now on the target tab's console.
4. It calls `WriteConsoleInput` with the message as keystrokes. To the agent, this looks like typing.

The tab doesn't need focus, the window doesn't pop up, and the agents need no changes. Each send takes about 1 s because PowerShell has to start.

## Transport order on Linux (`VIA` column of `--list`)

| VIA | When |
|---|---|
| `tmux` | the target runs in a tmux pane (`tmux send-keys`) |
| `wt` | WSL, and the target's interop socket exists (the normal case) |
| `tiocsti` | only if `dev.tty.legacy_tiocsti=1` (off by default on kernels 6.2 and later) |
| `none` | the send fails and says why |

## Usage (same as macOS)

```bash
general/tools/agent-bridge/send_to_tty.sh --list
general/tools/agent-bridge/send_to_tty.sh --register agy-a
general/tools/agent-bridge/send_to_tty.sh --dry-run claude:573579
general/tools/agent-bridge/send_to_tty.sh claude:573579 "please review report.md"
general/tools/agent-bridge/send_to_tty.sh reply "done"
```

Return handling:

- **agy / gemini:** text followed by Enter in one burst.
- **Claude Code / Codex:** text without a trailing Enter, then lone Enters at +1.5 s and +2 s (`submit=1`, `BRIDGE_SUBMIT=1` inside `conin_inject.ps1`), because both treat a fast burst ending in Enter as a paste.

### Interactive dialog collisions (`D89`/`D90`, 2026-11-24) and pre-send `CONOUT$` + JSONL guards

- **What happened.** On `2026-11-24`, `e1 Committee` (`claude:3008`) opened an `AskUserQuestion` selector dialog twice (`16:06:56` and `16:11:09`). Incoming `send_to_tty.sh` Enter keystrokes from `Papers Supervisor` (`claude:12906`) and `codex:374060` picked `"Approve, cap 9,000 s (Recommended)"` and `"Hold, not yet"` (73 ms after the second picker opened), causing handovers to dispatch without human approval (`D89`/`D90`). <!-- handover-lint: allow -->
- **Fix in `send_to_tty.sh` + `conin_inject.ps1`:**
  1. **Claude JSONL dialog guard (`claude_open_dialog_of`):** Before typing into any Claude target, `send_to_tty.sh` inspects `~/.claude/sessions/<pid>.json` $\to$ `~/.claude/projects/*/<sessionId>.jsonl`. If an unanswered `AskUserQuestion`, `ExitPlanMode`, or `Artifact` tool call is open, it polls up to `BRIDGE_PROMPT_WAIT_SECS` (default 60 s) and refuses with `not sent: target has open interactive dialog (...)` (exit `1`) if still open.
  2. **Windows Terminal `CONOUT$` screen guard (`conin_inject.ps1`):** Reads `CONOUT$` on the attached console, checks the tail footer for interactive picker prompts (`Enter to select`, `Enter to confirm`, `Esc to cancel`, `to navigate`, `Tab to amend`, `Do you trust the contents of this`), and for Claude targets runs the same prompt-box / `/usage` panel auto-close / 4-attempt submit verification used on macOS and `tmux`. Setting `BRIDGE_READ_ONLY=1` (or running `send_to_tty.sh --read <target>`) dumps the screen without touching `CONIN$`; `BRIDGE_FORCE_SEND=1` bypasses the screen checks. It is the user's switch: no agent sets it without the user's word in its own session, and a refused send is reported, not forced.
  3. **Plain-text approvals rule:** Sessions must ask the user for approvals in plain text, never via `AskUserQuestion` pickers (also enforced by `claude/hooks/claude-guardrails/`).

### Codex tabs: auto-submit and `app-server` caller resolution (fixed 2026-11-22)

- Earlier, `send_to_tty.sh` gated `submit=1` for `codex` on `[ "$OS" != Linux ]`, so on WSL a Codex tab treated `"text\r"` as a paste and left the message unsubmitted in the prompt box. `codex` now sets `submit=1` on Linux/WSL too, and `deliver_linux` omits the trailing `\r` from the initial burst when `submit=1`.
- Codex 0.171+ also runs tool shells under a tty-less `codex app-server` daemon, which caused `caller_pid()` to tag outgoing messages `[from codex:<daemon_pid>]` (making `reply` fail with `target 'reply' has no terminal`). `caller_pid()` now resolves a tty-less `codex` ancestor back to the live `codex` TUI process matching the thread's `cwd`.

### Switching an executor's model on WSL (tested 2026-11-14)

- **agy: works.** `send_to_tty.sh --raw agy:<pid> "/model gemini-4-hydrogen-high"` changed the session's model at
  once, and `~/.gemini/antigravity-cli/settings.json` went from `"Gemini 3.8 Flash (High)"` to
  `"Gemini 4 Hydrogen (High)"`. The setting is agy's global default, so later agy sessions start on it too. Model names
  come from `agy models`.
- **Codex: version first.** The argument form `"/model <model> --reasoning=<level>"` needs Codex 0.169.0 or later.
  - Check with `readlink /proc/<pid>/exe`.
  - On the old 0.154.0 custom build the command opens the picker, and the Returns of `--raw` accept the highlighted
    default without notice. A session running that build is restarted on 0.169.0 before any switch.
- **Before either:** check that the session is idle, and afterwards confirm the change from its settings or its tab.

### A long message can vanish while the bridge says "sent" (found 2026-11-14)

- **What happened.** At about 23:30 CST on 14 November, a 1,130-character nudge went to an agy tab (`agy:1876610`,
  `/dev/pts/12`, Windows Terminal). The bridge printed `sent to /dev/pts/12 (windows terminal)` and exited 0, but
  nothing arrived. The user's screenshot showed agy's input box empty and the tab at STOPPED, and no work started. A
  lone Enter sent afterwards through `conin_inject.ps1` changed nothing.
- **What worked.** Minutes later a 204-character nudge that pointed to a handover file reached the same tab, and agy
  started within about 21 s. An 843-character nudge had reached the same tab earlier that evening.
- **Why the bridge said "sent".** `conin_inject.ps1` prints `ok` whenever `WriteConsoleInputW` returns true. It never
  compares the number of records written (`w`) with the number given, and nothing reads back what the target
  received. So "sent" means only that Windows accepted the call.
- **The cause is not known.** There is one failure, and length is the only known difference. The text and its Enter
  go in one `WriteConsoleInputW` call, two 20-byte records per character. That is 2,262 records (about 45 kB) for
  the lost message, against 1,688 (about 34 kB) for the 843-character one that arrived. No test has shown whether a
  size limit, agy's handling of a long burst or the tab's state lost the text.
- **What to do.**
  - Put the detail in a handover file, and send a nudge of two or three lines that names it.
  - After every nudge, check within about a minute that the work started: a reply, a commit or a new file. If
    nothing moves, ask the user to look at the tab. Never take "sent" as "delivered".
- **A possible fix, not made.** Check `w` against the record count and fail on a short write, and send long text
  in pieces.

### Host fixes are in `fix/`

Fixes for the machine itself are not kept in this guide: every Claude Code session must read this file, and every change to it sends every session back to read it again (moved 2026-11-25).

- Ctrl+V screenshot paste in agy on WSL: [`fix/wsl-clipboard/`](../../../fix/wsl-clipboard/README.md)
- NuPhy Air96 volume and screenshot keys: [`fix/nuphy-air96/`](../../../fix/nuphy-air96/README.md)
- Codex `app-server` socket starvation ("workspace routing discovery timed out"): [`fix/codex-app-server-socket/`](../../../fix/codex-app-server-socket/README.md)

## Tested (2026-11-04, WSL2 kernel 6.18, Windows Terminal 1.24)

A byte logger ran in a separate Windows Terminal tab.

- `send_to_tty.sh pts/8 'bridge test 2 $HOME'` arrived as `[from agy:1674500] bridge test 2 $HOME\r`. Nothing expanded.
- UTF-8 (`中文`) came through intact.
- The submit path delivered `X`, then `\r`, then `\r`.
- **Live two-way agent relay tested**: `agy-mgmt` (pts/6) messaged `crossbridge` (pts/0); `crossbridge` executed `send_to_tty.sh reply` and delivered the acknowledgment directly back into `agy-mgmt`'s terminal input stream.

## Session titles (`TITLE` column, title targets)

`--list` shows each session's user-given title, the one set with `/rename`:

- **Claude Code:** `name` in `~/.claude/sessions/<pid>.json`.
- **agy:** the conversation the process has open (`~/.gemini/antigravity-cli/conversations/<id>.db`), then the latest `/rename` for that conversation in `history.jsonl`.
- **Codex:** the thread ID from its active rollout or writer-lock file, then the latest `thread_name` for that ID in `~/.codex/session_index.jsonl`.

The title is read on every call, so it stays right when a tab is reused: `/clear` followed by `/rename e1 s1 executor` keeps the same PID and TTY, and the title column follows. A title works as a target:

```bash
general/tools/agent-bridge/send_to_tty.sh "e1 s1 executor" "Read the handover and start"
```

Case and `-`/`_`/space are ignored. When two live sessions share a title, the send is refused and both are listed.

Codex sessions use the same title targeting. For example, the live title
`AI management` can be addressed directly; use `codex:<pid>` when the session
has no indexed title or when an exact process is required:

```bash
general/tools/agent-bridge/send_to_tty.sh "AI management" "[NOTICE] Please read /path/report.md"
general/tools/agent-bridge/send_to_tty.sh codex:823959 "Please review /path/report.md"
```

## Process identity on WSL

Sessions are identified by PID plus start time. On Linux the start time is the kernel's start tick (`/proc/<pid>/stat`, field 22). The wall-clock `ps -o lstart` used before drifts on WSL after the host sleeps (2.5 h observed), which made live registrations show as "stale". Registrations and reply records written in the old format are upgraded automatically the first time they are read.

## Caveats

- Long text arrives in chunks of about 16 bytes, like fast typing, not as one paste.
- The WSL interop sockets (`/run/WSL/*_interop`) can be used by any process in the distro. That's how this works, and it also means any local process can type into your tabs.
- VS Code terminals and other hosts are reached the same way if they run on `wsl.exe`. Not tested.
