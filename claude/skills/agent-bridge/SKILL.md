---
name: agent-bridge
description: Reach another agent session running in a different terminal tab on this machine — an Antigravity (agy), Codex, Gemini or other Claude Code session — to nudge it, hand it a job, tell it to start a handover, or reply to it. Use this whenever a session must be told something and SendMessage/ListAgents cannot reach it (agy, codex and gemini sessions are never in Claude's session listing), e.g. "tell the agy session to start", "nudge the executor", "send it to e1 s0 executor". Never claim another session cannot be reached or started before trying this.
---

# Agent bridge: talk to agy / codex / gemini / claude sessions in other tabs

Claude's own `SendMessage` / `ListAgents` only see Claude Code sessions. Every other
agent (agy = Antigravity CLI, codex, gemini) is reached with the bridge from the
user's repo `~/AI-management` (guides: `general/guides/agent-control-macos/How_to_Control_Agent_Sessions_macOS.md` on
macOS, `general/guides/agent-control-wsl/How_to_Control_Agent_Sessions_WSL.md` on WSL/Linux). It types the message into
the target's terminal tab as keystrokes (Terminal.app AppleScript on macOS, Windows
Terminal console input on WSL, `tmux send-keys` in tmux) and presses Enter, so the target
receives it exactly like a prompt from its user.

```bash
B="$HOME/AI-management/general/tools/agent-bridge/send_to_tty.sh"

$B --list                         # live sessions: TITLE NAME KIND PID TTY VIA CWD
$B --dry-run "e1 s1 executor"     # where a message would go, sends nothing
$B "e1 s1 executor" "Read ~/.claude/handover/<doc>.md and execute it. ..."
$B agy:2359398 "..."              # or by kind:pid (PID from --list)
$B <registered-name> "..."        # or by a name from --register (NAME column)
$B reply "done, report at ..."    # answer whoever last messaged you
$B --register <name>              # name YOUR OWN session so others can target it
```

How to pick the target:

1. Run `$B --list`. The TITLE column is each session's user-given title (agy,
   Claude Code, and Codex), read live, so it is current even after `/clear` +
   rename in the same tab. When the user names a session ("e1 s1 executor"),
   find that title there. Codex titles are resolved from the active thread's
   rollout/writer-lock identity and `~/.codex/session_index.jsonl`.
2. Target it by its title in quotes (case and `-`/space don't matter), by `kind:pid`
   (e.g. `agy:2359398`), or by a registered name. Avoid raw TTY names (`ttys003`, `pts/N`). If a title is
   missing, the session was never `/rename`d: identify it by KIND and CWD, and ask
   the user if several match.
3. Send one line. Newlines are flattened to spaces. The message arrives prefixed with
   `[from claude:<your pid>]`, which the receiver can answer with `$B reply "..."`.
4. Check the exit status: 0 = delivered, 1/2 = refused, with the reason printed.

## Rules that still apply (from ~/.claude/CLAUDE.md, if it defines them)

- If ~/.claude/CLAUDE.md says who may nudge whom (on the WSL machine: section 1), follow
  it. There, only a user-designated manager (name carries Manager / Router / Committee / CEO / CTO)
  nudges other sessions to work. When the user has approved the job in the manager's
  session, the nudge must state explicitly what the user approved. That relayed approval
  is the executor's go-ahead.
- The user saying "he is there, start it" IS the approval: send the nudge yourself right
  away, quoting the approval. Don't tell the user it can't be done and don't hand the
  sending back to them.
- An agy/codex session does not run Claude Code's hooks, so the nudge should point it at
  `~/.claude/CLAUDE.md` and the handover document first.

Nudge template:

```bash
$B agy:<pid> "[NUDGE from <manager session name>] The user approved in session '<name>' on <date>: <exact scope>. Read ~/.claude/CLAUDE.md, then ~/.claude/handover/<doc>.md, and execute it now. Write the report to ~/.claude/handover/<doc>.REPORT.md and reply with: $B reply \"report ready\""
```

## A "new" session the user names is often the SAME process

The user often reuses a tab: `/clear` there starts a new conversation and `/rename <new
name>` retitles it, but the PID, TTY and `--list` row stay the same. So when the user
says "<name> is online" and `--list` shows no new row, the session is the existing row
of that kind in that folder. Confirm it in agy's prompt history:
`tail ~/.gemini/antigravity-cli/history.jsonl` lists each `/rename` and `/clear` with
its workspace. After a `/clear` the session remembers nothing, so the nudge must tell it
to read ~/.claude/CLAUDE.md and the handover from scratch.

## Opening a NEW agy tab: do NOT do it yourself

On WSL, on 2026-11-05, `wt.exe -w 0 new-tab ... wsl.exe -d Ubuntu --cd <dir> -- bash -lc agy`
run from a Claude session returned exit 0, but no usable session came up (a test tab
never ran its command). Opening tabs was not tested on macOS either. Ask the user to
open the tab and `/rename` it, then find it with `$B --list`. If the user explicitly asks
you to open or resume a tab via `wt.exe`, never include an unescaped `;` (such as
`bash -lc '<cmd>; exec bash'`) — `wt.exe` treats `;` as its own subcommand delimiter
and spawns a broken `'exec bash'` error tab (`0x80070002`). Omit `'; exec bash'` or
escape `\;`.

## Codex tabs on WSL (auto-submit fixed 2026-11-22)

Since 2026-11-22 (`send_to_tty.sh` + `conin_inject.ps1`), `submit=1` is enabled for `codex` on Linux/WSL as well as macOS, so ordinary messages and `--raw` commands submit automatically. For details see `~/AI-management/general/guides/agent-control-wsl/How_to_Control_Agent_Sessions_WSL.md`.

## Dialog guard (`D89`/`D90`, 2026-11-24): never interrupt open UI pickers

Never open `AskUserQuestion` or other TUI dialogs when awaiting bridge replies — an incoming Enter can select `"Recommended"` without user action. Before typing, `send_to_tty.sh` inspects Claude JSONL transcripts and console screen buffers (`CONOUT$` on WSL, `history of t` on macOS, `capture-pane` in `tmux`), refusing with `exit 1` (`not sent: target has open interactive dialog` / `not at its prompt`) if a picker stays open past the wait window.

`BRIDGE_FORCE_SEND=1` and `BRIDGE_FORCE_DISPATCH=1` skip these checks. They are the user's switches (2026-11-25): never set one without the user's word in your own session. When a send is refused, do not force it and do not retry in a loop: write your report where the handover says, tell your own user, and say that the nudge did not go out.

## When the nudger cannot be told (2026-11-25)

The executor rules say to report back through the bridge to whoever nudged you. When the nudger is offline, or the bridge refuses the send, that duty is met by the report file and by telling your own user. It is never met by forcing the send.

## Changing a Codex session's model or effort (2026-11-13)

`$B --raw codex:<pid> "/model <model> --reasoning=<level>"` (or `"/model --reasoning=<level>"` for effort only).
`--raw` drops the `[from ...]` prefix, so the slash command is at the start of the line, and adds lone Returns (the
first closes Codex's command menu). Codex replies `Model changed to ... for this session only`. Read the tab to
confirm, and check the session is idle before sending. Model slugs: `~/.codex/models_cache.json`. Change another
session's model only when the user asked for it. Details: §5a of the macOS guide. Untested on WSL.

## Changing an agy session's model or effort (2026-11-14)

`$B --raw agy:<pid> "/model <name>-<effort>"` (e.g. `gemini-4-argon-high`, `claude-opus-5-5-medium`; list: `agy models`)
or `"/effort <level>"`. Read the footer to confirm (`<Model (Effort)> · <effort>`). Unlike Codex, both are saved as
agy's default in `~/.gemini/antigravity-cli/settings.json`, so they change new agy sessions too; for one prompt only use
`/model <name> <prompt>`. Never write `/model <name> <effort>`: the effort word becomes a prompt. Details: §5b of the
macOS guide.

## A Codex session that hit its usage limit stays stopped (2026-11-17)

Codex does not resume by itself after the 5-hour limit resets (user: "you need to manually resume it"). Read the
tab (`history of t`, via `osascript`; see §5c of the macOS guide): the limit line says `try again at <time>`, a clock
time without a date (compare it with `date`), and once reset the status bar shows e.g. `5h 99% left · weekly 29% left`. After that time send a normal bridge message: resume
the handover where it stopped, first look for any half-made edit in the files it was writing, and record the
interruption in its report. Then read the tab again and confirm it shows Working. Check the weekly budget before
handing it a long job.

## Caveats

- Each send takes about 1 s on WSL (PowerShell startup) and about 4 s on macOS for a
  Claude target (extra Returns). Long text arrives as fast typing on WSL.
- If a person is typing in the target tab at that moment, the two texts get mixed.
- Registrations go stale when a process restarts (`--list` reports this); re-register.
- "sent" does not mean delivered. On WSL it means only that Windows accepted the keystrokes. On
  2026-11-14 a 1,130-character nudge to an agy tab was lost while the bridge printed "sent"; a
  204-character nudge pointing to a file then worked. Keep nudges to two or three lines that
  name a file. Within about a minute, check that the target started (a reply, a commit or a new
  file); if not, ask the user to look at the tab. Details are in
  ~/AI-management/general/guides/agent-control-wsl/How_to_Control_Agent_Sessions_WSL.md.
