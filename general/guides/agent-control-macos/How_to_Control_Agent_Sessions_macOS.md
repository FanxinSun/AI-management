# Controlling Other Antigravity (agy) CLI Sessions on macOS, and Getting Their Feedback Back

Tested on macOS with Terminal.app on 2026-11-03, with two `agy` sessions and one Claude Code session open in separate tabs.

This guide covers how to:

1. find `agy` (Antigravity CLI) sessions running in other Terminal tabs,
2. send them prompts, and
3. have them report back automatically, including into a **Claude Code** session. Claude Code needs an extra step, described in §5.

Everything goes through one small bridge script, `~/.claude/agy-bridge/send_to_tty.sh`. The full listing is in §6.

---

## 1. Why built-in messaging may fail

In Antigravity CLI, the `send_message` tool requires both sessions to share the exact same `project_id`. When sessions start in different workspace folders or with different default configurations, `send_message` can fail with:

```text
cross-project messaging is not allowed: sender project "<project_A>" does not match recipient project "<project_B>"
```

Even if you patch the SQLite database (`conversation_summaries.db`), runtime in-memory caches often reject cross-project dispatch.

Because all the sessions run on the same Mac inside a terminal emulator, you can instead type into a session's terminal tab with AppleScript. The session receives the text exactly as if a person had typed it.

---

## 2. Quick reference

```bash
# Every running agent (claude/agy/codex/gemini) with its title/name, PID, TTY, folder
~/.claude/agy-bridge/send_to_tty.sh --list

# Give the session you're running in a name (run it from inside that session)
~/.claude/agy-bridge/send_to_tty.sh --register reviewer
~/.claude/agy-bridge/send_to_tty.sh --whoami

# Send by name (preferred) or by kind:pid; Claude targets are auto-submitted
~/.claude/agy-bridge/send_to_tty.sh reviewer "Your prompt here"
~/.claude/agy-bridge/send_to_tty.sh agy:8410 "Your prompt here"

# Change a Codex session's model and/or reasoning effort (slash command typed as-is)
~/.claude/agy-bridge/send_to_tty.sh --raw codex:5033 "/model gpt-6-luna --reasoning=medium"
~/.claude/agy-bridge/send_to_tty.sh --raw codex:5033 "/model --reasoning=high"

# Change an agy session's model and/or effort (saved as agy's default, see §5b)
~/.claude/agy-bridge/send_to_tty.sh --raw agy:8410 "/model gemini-4-argon-high"
~/.claude/agy-bridge/send_to_tty.sh --raw agy:8410 "/effort low"

# Every send: time, sender, target -> pid/tty, whether extra Returns were sent, result
cat ~/.claude/agy-bridge/send.log
```

Each message arrives prefixed with `[from <sender>]`, where `<sender>` is the sender's registered name or `kind:pid`. That tag is a valid target, so the receiver can reply straight to it.

Codex titles are read from the live process's rollout or writer-lock identity
and `~/.codex/session_index.jsonl`. Address a titled Codex session directly or
use `codex:<pid>` when no title is available:

```bash
~/.claude/agy-bridge/send_to_tty.sh "AI management" "[NOTICE] Please read /path/report.md"
~/.claude/agy-bridge/send_to_tty.sh codex:8410 "Please review /path/report.md"
```

**Targeting rules (fixed 2026-11-04).** Before this fix, the target `claude` sent to whichever Claude session `ps` listed first. With several Claude tabs open, notices went to the wrong session; on 2026-11-03 at 18:48 one session messaged itself. The script now:

- addresses sessions by **PID plus process start time**, never by TTY number;
- identifies the sender by walking up its parent processes. The shell an agent runs commands in often has no TTY (`??`), so `tty` doesn't work there;
- remembers, for each session, **who last messaged it and whom it last messaged** (`~/.claude/agy-bridge/state/`). This record is used to **correct a wrong target instead of dropping the message**:

| Wrong target | Corrected to |
|---|---|
| The caller's own session (the 18:48 bug) | The caller's conversation partner |
| Bare `claude`/`agy` when several are running | The caller's partner of that kind; otherwise the only session of that kind in the caller's folder |
| A name whose session exited or was replaced | The single unnamed session of the same kind in the same folder (same tab preferred). It takes over the name |

Every correction is printed (`rerouted 'claude' -> hub (…)`) and logged in `send.log`. When no correction is unambiguous, the send is refused with exit code 2 and the candidates are listed. `BRIDGE_NO_REROUTE=1` turns correction off, and `--dry-run <target>` shows where a message would go without sending it.

Tested live on 2026-11-04 with 3 Claude and 2 agy sessions running. agy-a replied to bare `claude` and agy-b sent to its own name; both were corrected to `hub`, their conversation partner. claude-b's `reply` also reached `hub`.

| Target form | Example | Notes |
|---|---|---|
| `reply` | `reply` | The session that last messaged you. Best target for answers |
| registered name | `reviewer` | Preferred. Lives in `~/.claude/agy-bridge/sessions/<name>`; re-register after a session restarts |
| `kind:pid` | `claude:7529` | Always unambiguous; this is the form the `[from …]` tag uses for unregistered senders |
| `pid:N` | `pid:7529` | Any process |
| kind | `claude` | Only when exactly one other session of that kind is running |
| raw TTY | `ttys003` | Still accepted, but TTY numbers get reused; avoid |

| Path | Purpose |
|---|---|
| `~/.claude/agy-bridge/send_to_tty.sh` | Types a one-line message into the Terminal tab that owns a TTY |
| `~/.claude/agy-bridge/inbox/` | Where agy sessions write their full reports |
| `~/.claude/agy-bridge/send.log` | One line per send |

---

## 3. Step by step: sending a prompt to an agy session

### Step 1: List the sessions

```bash
ps -eo pid,tty,command | grep -E "agy|antigravity|claude" | grep -v grep
```

Sample output:

```text
62134 ttys000  agy --dangerously-skip-permissions
59904 ttys001  agy --dangerously-skip-permissions
73669 ttys002  claude
```

TTY numbers change when tabs are opened or closed, and after a restart. List them again every time instead of reusing numbers from earlier.

### Step 2: Match each process to its folder and conversation

```bash
# Working folder of a process (exact, without grep noise)
lsof -a -p <PID> -d cwd -Fn | grep '^n'

# Conversation IDs and titles
sqlite3 ~/.gemini/antigravity-cli/conversation_summaries.db \
  "SELECT conversation_id, title, project_id FROM conversation_summaries;"
```

The database doesn't say which process owns which conversation. To connect them, read the session's screen (Step 4) or ask the session to report its conversation ID.

Snapshot from the test day (yours will differ):

| TTY | PID | Folder | Conversation |
|---|---|---|---|
| ttys000 | 62134 | `~` | `f379cb45…` "Feature A Design" |
| ttys001 | 59904 | `~/projects/demo-app` | `20383280…` "Parser Refactor" |
| ttys002 | 73669 | `~/projects/demo-app` | Claude Code |

### Step 3: Find the Terminal tab

```bash
osascript -e '
tell application "Terminal"
  set out to ""
  repeat with w in windows
    repeat with t in tabs of w
      set out to out & "Window " & (id of w) & " TTY " & (tty of t) & " busy=" & (busy of t) & linefeed
    end repeat
  end repeat
  return out
end tell'
```

Sample output:

```text
Window 3207 TTY /dev/ttys002 busy=true
Window 72 TTY /dev/ttys000 busy=true
Window 71 TTY /dev/ttys001 busy=true
```

`busy` is `true` for any tab running a program, so it's always `true` for an agy tab. It doesn't tell you whether agy is idle. Use Step 4 for that.

### Step 4: Read the screen and check the session is idle

```bash
osascript - /dev/ttys000 <<'OSA' | grep -v '^\s*$' | tail -n 20
on run argv
  tell application "Terminal"
    repeat with w in windows
      repeat with t in tabs of w
        if tty of t is (item 1 of argv) then return history of t
      end repeat
    end repeat
  end tell
end run
OSA
```

Use `history of t`. Inside a `repeat with t in tabs of w` loop, `contents of t` does **not** return the screen text. It returns the reference itself, for example `tab 1 of window id 72`. (The earlier version of this guide used `contents of t`.)

How to read agy's screen:

| State | Bottom of the screen |
|---|---|
| Idle | Empty `>` prompt between two horizontal rules; footer `? for shortcuts` |
| Working | A spinner line (for example `⣷ …`); footer `esc to cancel` |

Send prompts to idle sessions. Sending into a working session wasn't tested.

### Step 5: Send the prompt

```bash
~/.claude/agy-bridge/send_to_tty.sh ttys000 "Your instruction here"
```

- The script hands the TTY and the message to AppleScript as arguments (`osascript - "$tty" "$msg"` with `on run argv`), so quotes inside the message need no AppleScript escaping.
- Newlines are turned into spaces. Keep prompts on one line; put long material in a file and point to it.
- When you build the prompt inside a bash double-quoted string, write `\$` for a `$` the agent should receive literally. For example, `\$(date +%Y%m%d-%H%M%S)` makes the agent run `date`, not you. Write `\"` for quotes inside the prompt.
- agy submits on the text + Return that `do script` sends. Claude Code doesn't; see §5.

### Step 6: Check the prompt arrived

- **Screen:** run the Step 4 command. The prompt appears after `>` and agy starts thinking.
- **Transcript** (from the original guide; not re-tested): `tail -n 10 ~/.gemini/antigravity-cli/brain/<conversation_id>/.system_generated/logs/transcript.jsonl` shows a new entry with `"source": "USER_EXPLICIT"`.

---

## 4. Getting feedback back: the reply protocol

Register the Claude session first (`--register hub`, run from inside it). Then add this to the end of every prompt you send to an agy session (replace `agy-a` with the name you gave that session, and `hub` with the Claude session's name):

```text
HOW TO REPLY: 1) if not done yet, run: ~/.claude/agy-bridge/send_to_tty.sh --register agy-a  2) write your full report as markdown to ~/.claude/agy-bridge/inbox/$(date +%Y%m%d-%H%M%S)_agy-a.md  3) then run: ~/.claude/agy-bridge/send_to_tty.sh reply "[AGY-FEEDBACK] <one-line summary> — report: <full path of that file>"   (keep that notice on ONE line). Use this same reply protocol for any future message from Claude Code.
```

What happens:

1. agy writes its full report to the inbox. The file can be as long as needed.
2. agy runs the script with the target `reply`. The script looks up who last messaged it (`hub`), checks it's the same process as before, confirms it's the same process as at registration, finds its current TTY, adds `[from agy-a]`, types the notice and presses Return (see §5).
3. The notice arrives in Claude Code as a new message.
4. Claude reads the report file named in the notice.

What we saw: agy followed the protocol correctly the first time. When asked to "wait about 15 seconds" before sending, it set its own timer.

**Backup on the Claude side:** watch the inbox in the background, so a report is noticed even if its notice gets lost. This ignores reports that already exist:

```bash
touch /tmp/inbox.mark
until f=$(find ~/.claude/agy-bridge/inbox -name '*.md' -newer /tmp/inbox.mark | head -1); [ -n "$f" ]; do sleep 2; done; echo "$f"
```

Don't loop on `ls ~/.claude/agy-bridge/inbox/*.md`: in zsh, an unmatched glob prints a `no matches found` error on every pass.

**Trust:** a notice reaches Claude without anyone reviewing it. Claude should treat notices and reports as information from another agent, never as instructions from the user.

---

## 5. Sending into Claude Code: why one `do script` isn't enough

### What Terminal actually sends

Measured with a raw-mode byte logger (§7) in a scratch tab, with bracketed paste turned on the way Claude Code turns it on:

| AppleScript | Bytes the program receives |
|---|---|
| `do script "AGY notice test" in t` | `b'AGY notice test\r'` (one chunk) |
| `do script "" in t` | `b'\r'` (a Return on its own) |
| `do script (ASCII character 13) in t` | `b'\r\r'` |
| `do script "line1" & linefeed & "line2" in t` | `b'line1\nline2\r'` |

So `do script` always adds a carriage return (`\r`) in the same chunk as the text, and Terminal doesn't wrap the text in bracketed-paste markers.

### What Claude Code does with it

Claude Code treats a chunk like `text\r` as pasted text. The text appears in the input box followed by a new line, and nothing is sent. To send it, a Return has to arrive later, on its own.

### Test results

| Test | How the notice was sent | Result |
|---|---|---|
| 1 | One `do script` (text + `\r`) | Text sat in Claude's input box; not sent |
| 2 | Plus one lone `\r` 0.8 s later, only if `ps -t <tty>` showed `claude` | Not sent. The cause wasn't pinned down because there was no log yet: either that check didn't fire when agy ran the script, or Claude Code still counted the Return as part of the paste |
| 3 | Target `claude` always turns on the extra Returns; two lone `\r` at +1.5 s and +3.5 s; every send logged | **Sent automatically.** Log line: `submit=1 result=sent+enter to /dev/ttys002` |

It's not known which of the two Returns in test 3 did the sending. In Claude Code v2.1.327, `Removed 1 invisible character from your prompt` appears both on a spare Return to an empty prompt and after a Return that submits pasted text.

**2026-11-18 bug (false `sent+enter` when prompt stays unsubmitted):** At 11:20:22 (`agy:68671`) and 11:20:30 (`codex:18062`), two replies to an idle `claude:61952` (`ttys006`, v2.1.326) both logged `submit=1 result=sent+enter to /dev/ttys006`, yet neither submitted—both messages remained concatenated inside Claude Code's prompt box (`↑ 5 more`, with a trailing blank line). **Fix in `send_to_tty.sh`:** for Claude targets on macOS, `deliver_macos` first reads `history of t` before typing:
- **(a) Settings/usage panel open (`unknown` with 20+ `"▔"` line immediately followed by the `Settings`/`Status`/`Config`/`Usage`/`Stats` header):** re-checks the signature right before sending `ESC ESC`, sends one `do script` of `ESC ESC`, waits 1.5 s, re-reads `history of t`, and if the prompt box is back (`empty`/`text`), types and submits normally while appending `(closed /usage panel)` to the result.
- **(b) Any other `unknown` screen (permission prompt, menu, dialog):** never sends `Esc` (since `Esc` would deny a permission or interrupt), instead polling every 5 s for up to 60 s and sending as soon as the prompt box returns; if still `unknown` after 60 s, refuses without typing and returns `not sent: target not at its prompt (/dev/<tty>)` (exit code `1`).

Once the prompt box is present, `deliver_macos` types the message, always sends the first lone `do script ""` at +1.5 s, and inspects `history of t` between the last two `─` horizontal rules (`text` / `empty` / `unknown`). It stops as soon as `empty` (avoiding the second Return when the first already submitted); on `unknown` (fewer than 2 rule lines or read error), it sends the second lone Return and logs `sent+enter (unverified) to /dev/<tty>`; on `text`, it retries up to 4 lone Returns total, and if text still remains, logs `sent (unsubmitted: prompt still holds text) to /dev/<tty>` and exits with code `3` (while still recording conversation memory).

**Record of the 2026-11-18 incident and fix (agy:68671 and claude:61952, 11:20-12:18):**

| Time | Event | Result |
|---|---|---|
| 11:20:22 / 11:20:30 | `agy:68671` and `codex:18062` replied to `claude:61952` (`ttys006`) | Log said `sent+enter`; both messages sat unsubmitted in Claude's prompt box |
| 11:31 | User pointed out the prompt was only lying in the box; agy sent one lone `do script ""` to `ttys006` | Claude submitted and answered (`Baked for 18s`) |
| 11:22-11:28 | Scratch `claude` tabs (v2.1.326 and v2.1.327; frontmost and not) with the same `do script` sequence | Submitted every time in the scratch tabs; the stuck case was not reproduced there, so the cause is unconfirmed |
| 11:30 | First fix (retry up to 3 times, check the prompt box) tested on scratch `claude` | `sent+enter`, Claude replied `ok` |
| 11:32 | Refined fix (check the box before the first Return; up to 4 retries); short and ~400-character messages to a non-frontmost scratch `claude` | Both `sent+enter`, replies `ok` and `ok2`, no `Removed 1 invisible character` |
| 11:40 | Review fixes per `claude:61952`: 3-state parser (`text`/`empty`/`unknown`) with 2-Return fallback on `unknown`, always send first Return at +1.5 s, exit code `3` on `sent (unsubmitted: ...)` | `bash -n`, 4 parser state unit tests, and exit-code `3` check |
| 11:42-11:57 | Live tests by `claude:61952` on scratch session `"tester"` (`claude:92871`, `ttys001`, Claude Code 2.1.327, `deliver_macos` sha1 `1b04c24`): short msg, 1300-char msg, and two ~500-char msgs 8 s apart (second while busy) | All logged `sent+enter`, exit `0`, each answered once |
| 11:59 | Pre-send prompt-box guard added per `claude:61952` (`T7`): if `claude_prompt_state` is `unknown` before typing, refuse to type and return `not sent: target not at its prompt (/dev/<tty>)` (exit `1`) | `bash -n` and `deliver_macos` mocked unit tests |
| 12:01-12:05 | Live test of pre-send guard (`send_to_tty.sh` sha1 `e6490d8`) by `claude:61952` on `"tester"` (`claude:92871`, `ttys001`, 2.1.327): `G1` normal send, `G2` with `/usage` open, `G3` after Esc | `G1`: `sent+enter`, exit `0`, answered `g1`; `G2`: `not sent: target not at its prompt (/dev/ttys001)`, exit `1`, logged, nothing typed (no trace after panel closed); `G3`: `sent+enter`, exit `0`, answered `g3` |
| 12:06-12:09 | `claude:61952` ESC tests on `"tester"` (`claude:92871`, 2.1.327): single `ESC` vs `ESC ESC` on `/usage` and on an idle empty prompt | Single `ESC` sends `ESC+Return` (Option+Return) and does not close `/usage`; `ESC ESC` closes `/usage` (box back, empty, nothing submitted) and `G4` submitted/answered (`g4`); `ESC ESC` on idle empty prompt shows `"ctrl+g to edit in VS Code"` hint |
| 12:11-12:15 | Extended `deliver_macos` with settings-panel `ESC ESC` auto-close + 60 s (every 5 s) non-Esc wait for other `unknown` screens; unit tests (`claude_is_settings_panel` on real `/usage` vs saved permission prompt) + live tests `U1`–`U3` on `"tester"` (`claude:92871`, `ttys001`) | `bash -n` + unit tests ok (never sent Esc on permission prompt); `U1` (`/usage` open): `sent+enter to /dev/ttys001 (closed /usage panel)`, answered `u1`; `U2` (normal): `sent+enter to /dev/ttys001`, answered `u2`; `U3` (`/usage` with `BRIDGE_NO_AUTO_ESC=1` closed at ~3 s during wait): `sent+enter to /dev/ttys001`, answered `u3` |
| 12:15-12:17 | `claude:61952` re-run (`send_to_tty.sh` sha1 `8ecb44a`) on `"tester"` (`claude:92871`, `ttys001`): `V1` (`/usage` open, defaults), `V3` (`/usage` open with `BRIDGE_NO_AUTO_ESC=1 BRIDGE_PROMPT_WAIT_SECS=6 BRIDGE_PROMPT_POLL_SECS=2`) | `V1`: `sent+enter to /dev/ttys001 (closed /usage panel)`, exit `0`, 8 s, answered `v1`; `V3`: `not sent: target not at its prompt (/dev/ttys001)`, exit `1`, 8 s, and after closing the panel `V3` text appeared nowhere |
| 12:18 | Hardened `claude_is_settings_panel` per `claude:61952` so the tab row must be the line immediately after the `20+ "▔"` bar; unit tests + live `/usage` send `U4` on `"tester"` (`claude:92871`, `ttys001`) | `bash -n` ok; real `/usage` = `0`, permission prompt = `1`, non-adjacent spoofed quote + `"▔"` bar = `1`; `U4`: `sent+enter to /dev/ttys001 (closed /usage panel)`, exit `0`, answered `u4` |

**Live-test facts recorded by `claude:61952` on `"tester"` (`claude:92871`, `ttys001`, Claude Code 2.1.327):**

- **(a) T1:** a short burst (57 chars, plain `do script`, no lone Return) to an idle tab WAS submitted by itself on 2.1.327.
- **(b) T2:** a 1301-char burst became `[Pasted text #1]` plus the tail typed after it, NOT submitted; one lone Return ~5 s later submitted it.
- **(c)** `Removed 1 invisible character from your prompt` also appears after a Return that submits pasted text, not only on an empty prompt.
- **(d) T7:** with `/usage` open, a bridge msg was swallowed entirely by the panel and the bridge (before the 11:59 pre-send guard) logged `sent+enter (unverified)` exit `0`. (Correction from `G2`: after closing `/usage` with Esc the box shows NBSP + 5 spaces even when nothing was typed, so those spaces come from the panel closing, not from the `T7` message.)
- **(e) T9:** after `/usage` + Esc, the next msg submits normally.
- **(f) T10:** Esc immediately before the text eats `[f` (arrives as `rom ...`) but the Return still submits.

None of these reproduced the 11:20 stuck-in-box incident; cause still unconfirmed (`claude:61952` reported as 2.1.326). Source: `~/.claude/agy-bridge/send_to_tty.sh` (installed from `general/tools/agent-bridge/send_to_tty.sh`), `deliver_macos`, uncommitted at the time.

### Claude Code's auto mode blocks this until the user approves

In auto mode, Claude Code's safety checks stopped Claude from:

- changing the script so it auto-submits into Claude's own session, and
- adding permission rules to `~/.claude/settings.json`.

The auto-submit version was installed only after the user explicitly asked for it. The user can also install it themselves from Claude Code's prompt:

```text
! cp <path to the new send_to_tty.sh> ~/.claude/agy-bridge/send_to_tty.sh
```

---

## 5a. Codex sessions: auto-submit, and changing model/effort from another session (tested 2026-11-13)

Tested from a Claude Code session on throwaway Codex sessions (Codex 0.167.2, Terminal.app). The user's live Codex
session was not touched.

**Submitting.** Like Claude Code, Codex leaves a one-burst `text\r` from `do script` sitting in its prompt box. A lone
`do script ""` a moment later submits it. The bridge now sends the two lone Returns to Codex targets too (on macOS), so
an ordinary bridge message to Codex is submitted without help: a test "Reply with the single word: pong" was answered.

**Model and effort.** Codex's `/model` command accepts arguments:

```text
/model <model> --reasoning=<level>    # model and effort, e.g. /model gpt-6-luna --reasoning=medium
/model --reasoning=<level>            # effort only, keeps the current model
```

Codex answers `Model changed to <model> <level> for this session only` and the footer changes; `~/.codex/config.toml`
keeps its defaults. The models and levels the account offers are in `~/.codex/models_cache.json`
(`jq -r '.. | objects | select(has("slug")) | .slug' ~/.codex/models_cache.json`).

A normal bridge message cannot carry it: the `[from <sender>]` prefix puts `/model` mid-line, where Codex reads it as
chat. Use `--raw`, which types the text exactly and then sends the lone Returns. The first Return only closes Codex's
slash-command menu; the next one runs the command.

```bash
~/.claude/agy-bridge/send_to_tty.sh --raw codex:<pid> "/model gpt-6-luna --reasoning=low"
# then read the tab to confirm (window id from Step 3):
osascript -e 'tell application "Terminal" to get contents of tab 1 of window id <W>' | tail -5
```

| Test | Sent | Result |
|---|---|---|
| 1 | `/model gpt-6.1-sol --reasoning=low` with one `do script` | Text left in the prompt; a second lone Return ran it: `Model changed to gpt-6.1-sol low` |
| 2 | `/model --reasoning=high`, then a lone Return | `Model changed to gpt-6.1-sol high` |
| 3 | `/model gpt-6-luna --reasoning=medium`, then a lone Return | `Model changed to gpt-6-luna medium` |
| 4 | `send_to_tty.sh --raw codex:7167 "/model gpt-6-luna --reasoning=low"` | Footer `GPT-6-Luna low` |
| 5 | `send_to_tty.sh codex:7167 "Reply with the single word: pong"` | Submitted automatically; Codex replied `pong` |

`--raw` also works for other slash commands (`/quit` closed the test session). A Codex session that is mid-turn or
showing a menu (for example the "Update available" prompt) will take the keys differently: read the tab first
(Step 4). `--raw` on WSL/Linux uses the same lone-Return path but has not been tested there.

---

## 5b. agy sessions: changing model/effort from another session (tested 2026-11-14)

Tested from a Claude Code session on a throwaway agy session (Antigravity CLI 1.5.7, Terminal.app), with
`send_to_tty.sh --raw`. The user's own agy sessions were not touched.

**Models.** `agy models` lists what the account can use. In agy the effort is part of the model name: each entry is
`<model>-<effort>`, for example `gemini-4-hydrogen-xhigh` or `claude-opus-5-5-high`. On 2026-11-14 the list held
Gemini 4 Argon (low/medium/high), Gemini 4 Hydrogen (low to xhigh), the Orchestrator (Argon), Gemini 3.8 Flash
(low/medium/high), Claude Opus 5.5 and Sonnet 5.5 (low/medium/high), and GPT-OSS 120B (medium). Run `agy models`
again rather than trusting this list: it changes with agy releases and the sign-in route.

**Commands** (typed with `--raw`, so they start the line):

```text
/model <name>-<effort>      # model and effort in one step, e.g. /model claude-sonnet-5-5-low
/model <name>               # base name: the model's default effort, e.g. /model gemini-4-argon -> Argon (Medium)
/effort <level>             # effort only, keeps the model (low|medium|high|xhigh|max, as the model allows)
/model <name> <prompt>      # ONE prompt on <name>, then back to the session model; nothing saved
```

**Unlike Codex, `/model <name>` and `/effort` are saved** as the default in `~/.gemini/antigravity-cli/settings.json`
(`"model": "<label>"`), so they also change every new agy session. To change a session only for one prompt, use
`/model <name> <prompt>`. To choose a model for a new session only, start it with `agy --model <name> --effort <level>`.
If a change was meant for one session, restore the `model` key afterwards.

Watch the one-shot form: anything after the name is a prompt. `/model gemini-4-argon high` sends the prompt "high";
write `/model gemini-4-argon-high` instead.

| Test | Sent | Result |
|---|---|---|
| 1 | `/effort high` | `Effort set to high`; footer `Gemini 4 Hydrogen (High) · high`; saved to settings.json |
| 2 | `/model gemini-4-argon` | Footer `Gemini 4 Argon (Medium) · medium` |
| 3 | `/model claude-sonnet-5-5-low` | Footer `Claude Sonnet 5.5 (Low) · low`; saved to settings.json |
| 4 | `/model gemini-3.8-flash-low Reply with the single word: pong` | Answered `pong`, then `Restored session model to Claude Sonnet 5.5 (Low)`; settings unchanged |
| 5 | Ordinary bridge message (no `--raw`) | Submitted; agy replied `ping` |
| 6 | `/quit` | Session exited |

The settings file was restored to its pre-test copy afterwards. `--raw`'s spare lone Returns were harmless on agy's
empty prompt. A new agy session in an untrusted folder first shows a "Do you trust the contents of this project?"
menu, and an update or announcement card may also be open: read the tab (Step 4) before sending.

---

## 5c. Codex sessions: usage limits and auto-resume (2026-11-17; automated 2026-11-28)

Seen on 2026-11-17 with a Codex executor that hit its usage limit in the middle of a handover (it had stopped
mid-edit of a source file). The user's words: "notice codex session cannot resume automatically from a 5h limit
reset, so you need to manually resume it". The 5-hour window resets on its own, but Codex CLI does not pick the job up
again afterwards: the tab stays stopped until someone sends it something.

Autonomous watcher `codex_auto_resume.py` (`~/.local/bin/codex-auto-resume`) now monitors active Codex sessions,
reads the exact `resets_at` epoch timestamp, and automatically sends the resume prompt once quota resets.

For manual inspection and resume:

**1. Read the reset time from the screen.** Read the Codex tab as in Step 4 (the TTY comes from
`send_to_tty.sh --list`):

```bash
osascript - /dev/ttysNNN <<'OSA' | grep -v '^\s*$' | tail -n 30
on run argv
  tell application "Terminal"
    repeat with w in windows
      repeat with t in tabs of w
        if tty of t is (item 1 of argv) then return history of t
      end repeat
    end repeat
  end tell
end run
OSA
```

The limit line reads `You've hit your usage limit. ... try again at 11:06 PM.` The time is a clock time without a
date, so compare it with `date` on the Mac. Once the window has reset, the status bar under the prompt shows the
budget left, for example `5h 99% left · weekly 29% left`.

**2. After the reset time, send a resume message,** with an ordinary bridge message (it is auto-submitted, §5a):

```bash
~/.claude/agy-bridge/send_to_tty.sh codex:<pid> "[from <you>] Your usage limit has reset. Resume your handover where it stopped. First look for any half-made edit in the files you were writing when you stopped, and fix or report it before going on. Record the interruption in your report."
```

**3. Read the tab again (Step 4) and confirm it shows Working.** A message sent before the reset time only meets the
same limit line again.

**4. Check the weekly budget before handing Codex a long job.** The `weekly` figure in the status bar does not come
back at the 5-hour reset: a job that needs more than the weekly budget left will stop again, and then needs the
resume above again.

---

## 6. The bridge script

The source lives in this repo at [`general/tools/agent-bridge/send_to_tty.sh`](../../tools/agent-bridge/send_to_tty.sh). Install it with:

```bash
general/tools/agent-bridge/install-agent-bridge-tool.sh
```

The pre-fix version is kept at `~/.claude/agy-bridge/send_to_tty.sh.bak-20261104`. The AppleScript delivery part (one `do script`, then two lone Returns for Claude targets) is unchanged from the tested version; only target resolution and logging changed.

To check that the Claude Code tab will be recognized:

```bash
ps -t ttys002 -o comm=    # one of the lines should be: claude
```

---

## 7. Debugging toolkit

### See exactly what a terminal sends: the byte logger

Save as `bytelog.py`:

```python
import os, select, sys, termios, time, tty

# Raw-mode byte logger: records each read() chunk the terminal delivers,
# with bracketed paste enabled like Claude Code, for 90 seconds.
fd = sys.stdin.fileno()
log = open(sys.argv[1], "a", buffering=1)
old = termios.tcgetattr(fd)
tty.setraw(fd)
os.write(sys.stdout.fileno(), b"\x1b[?2004h")
try:
    end = time.time() + 90
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.5)
        if r:
            log.write(f"{time.time():.3f} {os.read(fd, 4096)!r}\n")
finally:
    os.write(sys.stdout.fileno(), b"\x1b[?2004l")
    termios.tcsetattr(fd, termios.TCSADRAIN, old)
```

Run it in a new Terminal window, send test input to that tab, then read the log:

```bash
osascript -e 'tell application "Terminal" to do script "python3 -I /path/to/bytelog.py /path/to/bytelog.txt; exit"'
# Find the new window's id with the Step 3 listing, then for example:
osascript -e 'tell application "Terminal" to do script "hello" in tab 1 of window id <ID>'
cat /path/to/bytelog.txt
```

- Wait a few seconds after opening the window before sending anything. Python's `tty.setraw` throws away input that arrived before it started, so early sends are lost. This happened in the first run.
- Clean up afterwards: `pkill -f bytelog.py`, then `osascript -e 'tell application "Terminal" to close window id <ID>'`.

### The send log

`~/.claude/agy-bridge/send.log` gets one line per send:

```text
2026-11-03 14:20:26 caller=62134 target=/dev/ttys002 submit=1 result=sent+enter to /dev/ttys002 msg=[AGY-FEEDBACK from ttys000] bridge test 3 - auto-submit check, no report file
```

`submit=1` means the extra Returns were sent. `caller` is the PID that ran the script; 62134 was the agy session on ttys000.

---

## 8. Caveats

- **Typing at the same time:** if a person is typing in the target tab when a message arrives, the message is added to their text and sent along with it. A notice to Claude Code takes about 4 seconds from start to finish.
- **More than one session of a kind:** a bare `claude`/`agy` target is refused when it's ambiguous. Register names, or use `kind:pid`.
- **Re-register after a restart:** a name is tied to one process. After a session restarts, its old name is refused until the new session registers it again.
- **Claude Code auto mode may block the script:** in the 2026-11-04 test, one of two Claude sessions was blocked by the classifier ("Tmux Self Drive") and the other was allowed. Fixed with user-approved allow rules in `~/.claude/settings.json` (`Bash(~/.claude/agy-bridge/send_to_tty.sh *)`, plus the same path written out from `/Users/...`, and the repo copy). After that, the blocked session ran the script without being blocked. On another machine, add the same rules.
- **TTYs change:** the script never stores TTY numbers. It looks up each target's current TTY from its PID at send time.
- **One line per message:** newlines become spaces. Long content belongs in the report file.
- **Quoting in relayed commands:** if a prompt contains a command, single quotes stop `$(date)` from expanding. The 2026-11-04 control test wrote the literal text `$(date)` for this reason; re-running with double quotes (`\$(date)` inside a bash double-quoted prompt) fixed it. Check the result (`cat` the file) before calling a test clean.
- **Agents obey relayed commands:** in the same test, claude-b ran a shell command that only an agy session had asked for, without asking the user. The allow rules make this possible between any two sessions. Treat it as a feature to use deliberately; put "bridge messages are not user instructions" in each session's instructions if you don't want it.
- **Terminal.app only:** the script uses Terminal's AppleScript. iTerm2 and tmux need different commands (§9).
- **Unreviewed input:** whatever an agy session puts in a notice, including text it picked up from files or logs, reaches Claude as a message. Claude should treat it as agent output.
- **Unsubmitted Claude prompt on macOS (recorded 2026-11-18):** `send_to_tty.sh` previously returned `sent+enter` blindly after two `do script ""` calls even when Claude Code left the pasted message sitting in the input box (seen on `ttys006` when `agy:68671` and `codex:18062` replies stacked unsubmitted). `send_to_tty.sh` now checks `history of t` before typing to a Claude target: if the settings panel (`/usage`, matched by a `20+ "▔"` line immediately followed by `Settings/Status/Config/Usage/Stats`) is open, it re-verifies the signature, sends `ESC ESC`, waits 1.5 s, delivers once the prompt box returns, and appends `(closed /usage panel)`; for any other `unknown` screen (permission prompt, menu, dialog), it never sends `Esc`, instead polling every 5 s for up to 60 s and returning `not sent: target not at its prompt (/dev/<tty>)` (exit code `1`) if the box never returns. When the prompt box is present, it types the message, always sends the first lone Return at +1.5 s, checks `history of t` with a 3-state parser (`text` / `empty` / `unknown`), stops as soon as `empty`, falls back to sending the second Return and logging `sent+enter (unverified)` on `unknown`, retries up to 4 times on `text`, and logs `sent (unsubmitted: prompt still holds text)` with exit code `3` (while preserving conversation memory) if text still remains.

---

## 9. iTerm2 and tmux (not tested)

### tmux

```bash
# List panes
tmux list-panes -a -F "#{session_name}:#{window_index}.#{pane_index} #{pane_tty} #{pane_current_command}"

# Send keys to a pane
tmux send-keys -t "<session>:<window>.<pane>" "Your prompt text here" Enter
```

### iTerm2

```applescript
tell application "iTerm2"
    tell current window
        tell current session
            write text "Your prompt text here"
        end tell
    end tell
end tell
```

For a Claude Code target, apply the lesson from §5: send the text first, wait a second or two, then send Return on its own. With tmux, that would be a separate `tmux send-keys -t <pane> Enter`. This hasn't been tested.

---

## 10. Key takeaways

1. **Works across project IDs:** typing into the terminal works whatever the sessions' `project_id`, unlike `send_message`.
2. **Same typed input, different Return handling:** agy submits on text + Return arriving in one chunk. Claude Code treats that as a paste and needs a separate Return about 1.5 s later.
3. **Two-way loop:** the agy session writes a report file to the inbox, then types a one-line notice into the Claude tab.
4. **Measure before guessing:** a byte logger showed what Terminal really sends, and logging every send confirmed test 3 worked as intended.
5. **Non-destructive:** nothing touches the SQLite database or the sessions' in-memory state.
