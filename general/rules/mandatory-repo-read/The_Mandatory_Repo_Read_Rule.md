# The Mandatory Repo-Read & Download UI Rule

**Rule (set by the user on 2026-11-24), in the user's words:**

> serius bug. the claude e6 Committee and e6 executor skipped reading rules, didn't follow the rules to give a download script, and further failed to give a correct format/UI twice. Make the rules in repo more strict/clear to follow, and make sure any session to read the whole repo at least once before start to work. For brand new session, read at the very beginning; for old session but not acknowleged, read after resume

It binds every agent session on every machine: Claude Code, agy, Codex, and Gemini — whether Committee, Manager, Executor, or subagent. It adds to every other rule and relaxes none.

---

## 1. Mandatory Repo Read & Acknowledgment Gate

Every session MUST read the entire `~/AI-management` rule set **at least once** before doing any substantive work (planning, handovers, edits, script generation, or reviews):

- **Brand new session:** read at the very beginning of the session before starting any task.
- **Old / resumed session not yet acknowledged:** read immediately upon resume before continuing work. For every brand it means that a listed file has changed since the session read it, and then only those files are read again: `ack-rules.sh --needs <session_id>` lists them. For a declared id (Gemini, manual) they are the files changed since its last acknowledgment.

### Required reading list (in `~/AI-management`)

1. `README.md`
2. `general/rules/mandatory-repo-read/The_Mandatory_Repo_Read_Rule.md` (this file)
3. `general/regulations/executor-regulations/The_Executor_Regulations.md`
4. `general/regulations/others-repositories/The_Others_Repositories_Regulation.md`
5. `general/rules/regular-remote-push/The_Regular_Remote_Push_Rule.md`
6. `claude/rules/ten-years-retention/The_10_Years_Rule.md`
7. `claude/rules/ultracode-workflow/The_Ultracode_Rule.md`
8. `general/rules/multi-agent-dispatch/MULTI_AGENT_DISPATCH_RULES.md`
9. `general/regulations/executor-regulations/EXECUTOR_RULES_BLOCK.md`
10. `general/regulations/executor-regulations/PLANNER_RULES_BLOCK.md`
11. `general/regulations/executor-regulations/HANDOVER_RULES.md`
12. `general/templates/download-ui/README.md`
13. `general/templates/chunked-pipeline/README.md`
14. `general/guides/chunked-pipeline-workflow/CHUNKED_PIPELINE_GUIDE.md`
15. `claude/rules/thought-chain-rigor/The_Claude_Thought_Chain_Rule.md`
16. `general/tools/handover-lint/README.md`
17. `general/rules/project-planning/The_Project_Planning_Rule.md`
18. `general/rules/brand-neutrality/The_Brand_Neutrality_Rule.md`
19. `general/rules/script-delivery/The_Script_Delivery_Rule.md`
20. Platform bridge guide as applicable: `general/guides/agent-control-macos/How_to_Control_Agent_Sessions_macOS.md` or `general/guides/agent-control-wsl/How_to_Control_Agent_Sessions_WSL.md`.

### How to acknowledge

**Reading is the acknowledgment, for every brand.** What differs is where the proof of the reading is kept.

**Claude Code (since 2026-11-25).** The rules-gate hook records each listed file that the session reads
whole with the Read tool, by content, and refuses the session's other tools until every listed file is read. There is
no command to run and none that can record it: `ack-rules.sh claude-<session_id>` only reports what is read. After a
commit the hook asks only for the listed files whose content changed. The list the hook uses is
[`reading-list.txt`](reading-list.txt) beside this file: items 1 to 19 above and the platform's bridge guide. Keep the
two in step, and keep host and hardware fixes out of these files (they go in `fix/`), because every change to a listed
file sends every session back to read it.

**agy and Codex (since 2026-11-27): checked in the session's own log.** [`ack_reads.py`](ack_reads.py) looks in the
log that the session itself writes: agy's transcript, or Codex's session log.
- **What counts as read:** the text that the session's tools returned, after the file last changed, holds the
  file's lines from the first to the last. Several calls may share one file. A part of a file does not count, and
  neither does a read made before the file's last change.
- **What to read:** `ack-rules.sh --needs <session_id>` lists the files that are still unread, one path per line.
  The list comes from this command, never from a nudge.
- **agy:** the gate lists the unread files in its notice, and it records the acknowledgment by itself as soon as
  the session's log holds them all. The id is `agy-<conversation_id>` (the `conversationId` passed by the hook).
- **Codex:** run `ack-rules.sh codex-<pid>` with the pid of the running session, or `codex-<thread_id>`. It records
  the acknowledgment, or it names the unread files and exits 1.

```bash
~/AI-management/general/rules/mandatory-repo-read/ack-rules.sh --needs <session_id>   # the files still to read
~/AI-management/general/rules/mandatory-repo-read/ack-rules.sh <session_id>           # record it; exit 1 while a file is unread
~/AI-management/general/rules/mandatory-repo-read/ack-rules.sh --list                 # every session: "reads checked" or "declared"
```

**Gemini, a manual id, and a session whose log is not found: by declaration.** `ack-rules.sh <session_id>` records
the acknowledgment at the current `HEAD`, and `--list` shows it as "declared". Never declare without having read the
files. A planner who needs more than the session's word asks for the commands and their output.

Also state explicitly in your first substantive response after reading that you have read `~/AI-management` rules.

---

## 2. Mandatory Download Script & UI Template Rule (Non-Negotiable)

Whenever a task involves downloading datasets, files, or artifacts that the user will run:

1. **You MUST deliver a runnable download script** — never tell the user to run raw `curl`/`wget` commands or invent an ad-hoc downloader (`tqdm`, line-by-line `print` spam, single-threaded fetch).
2. **You MUST copy and adapt `~/AI-management/general/templates/download-ui/fetch_dst.py` and `~/AI-management/general/templates/download-ui/download_wrapper.sh`:**
   - Keep the **in-place dashboard UI** (`\033[<n>A\033[J`, refreshed every 5 s on TTY / 30 s when piped): overall progress + ETA, windowed speeds, one bar per record/group, active files being fetched, and the **narrow layout below 100 columns**.
   - Keep the **`status` subcommand** (read-only, creates nothing, checks done/partial/bad/missing with no network), **automatic default folder** on bare `./wrapper.sh`, **Ctrl-C safe HTTP Range resume**, **size + checksum verification** (`*.bad` on failure, `fetch-log.tsv`, `SHA256SUMS`), **single-instance guard** skipping self/ancestors/descendants/`caffeinate`, and **exit codes `0` / `1` / `2` / `3`**.
   - Test through the exact launch wrapper (including `status` and `<100` col narrow layout) before delivering.
3. **Rule 14 (Full runnable command at the very end):** the final element of your closing message MUST be the complete, exact, copy-paste-ready command line(s) (with `cd <repo>` or absolute paths, and all options) for the user to run.
4. **Chain downstream data processing per `CHUNKED_PIPELINE_GUIDE.md` (amended 2026-11-27):** whenever the task includes data processing, skimming, filtering, or validation after download, do **not** stop silently after writing `SHA256SUMS`. Follow [`general/guides/chunked-pipeline-workflow/CHUNKED_PIPELINE_GUIDE.md`](../../guides/chunked-pipeline-workflow/CHUNKED_PIPELINE_GUIDE.md): chain download -> verification -> processing/skimming -> automated checks -> bridge wakeup (`send_to_tty.sh` to Manager/Committee) inside an unattended resumable script (and keep raw downloads until independent Manager acceptance on bounded disk).
5. **Prove the format before you claim it (2026-11-27):** capture the script's screen at 100 and 80 columns, run `~/AI-management/general/rules/script-delivery/check_frame.py` on the captures, and paste the commands and their output with the delivery. Without it write "format not compared". Build the script by copying the templates' files, and where no template fits what was asked, say so and ask the user. See [`The_Script_Delivery_Rule.md`](../script-delivery/The_Script_Delivery_Rule.md).

---

## 3. Enforcement Hooks (`claude/hooks/rules-gate/`, `claude/hooks/claude-guardrails/`, `agy/hooks/rules-gate/`)

- **Claude Code:** [`claude/hooks/rules-gate/install-claude-rules-gate-hook.sh`](../../../claude/hooks/rules-gate/install-claude-rules-gate-hook.sh) installs `~/.claude/hooks/ai-management-rules-gate.sh` on `PreToolUse`, `PostToolUse` (`Read`), `SessionStart`, `UserPromptSubmit` and `SubagentStart` (rewritten 2026-11-25).
  - `PostToolUse` records each listed file the session reads whole (its git blob id, in `~/.ai-management/rules-read/claude-<session_id>`). A read with an offset or a limit, and a subagent's read, do not count.
  - `PreToolUse` refuses every other tool until every listed file is read at its current content. Reading a listed file, and reading the machine rules file `CLAUDE.md`, stay allowed. A subagent rides on its session's record.
  - Session start and every prompt print what is unread, with `(changed since you read it)` on a file read before at an older content.
  - The gate fails open on an internal error, and `AI_MGMT_RULES_GATE_OFF=1` is the user's off switch; no agent sets it.
  - Before 2026-11-25 the gate was a note plus a self-declared acknowledgment tied to `HEAD`: nothing was refused, a session could acknowledge without opening a file, and every commit, whatever it changed, told every session to read everything again.
- **Claude Guardrails:** [`claude/hooks/claude-guardrails/install-claude-guardrails-hook.sh`](../../../claude/hooks/claude-guardrails/install-claude-guardrails-hook.sh) installs `~/.claude/hooks/ai-management-claude-guardrails.sh` to block `AskUserQuestion` pickers and edits of a `.py` file that add a `1 - cdf` upper tail or a hardcoded Python minor path, and injects T1–T5 reminders.
- **Antigravity (`agy`):** [`agy/hooks/rules-gate/install-agy-rules-gate-hook.sh`](../../../agy/hooks/rules-gate/install-agy-rules-gate-hook.sh) installs `~/.gemini/config/hooks/ai-management-rules-gate.sh` in `~/.gemini/config/hooks.json` on `SessionStart` and `PreInvocation`. Since 2026-11-27 the hook first runs `ack-rules.sh --auto agy-<conversationId>`: when the session's own log holds every listed file, whole, the acknowledgment is recorded and the hook is silent. Otherwise its notice lists the unread files (`ack-rules.sh --needs`), at `SessionStart` and at most every 120 s at `PreInvocation`. The hook injects a notice; it does not refuse a tool, so a planner looks at `ack-rules.sh --list`.
- **Codex and Gemini:** no hook. Codex acknowledges with `ack-rules.sh codex-<pid>`, which checks its session log; Gemini declares.

---

## 4. Paste-in form

For a `CLAUDE.md`, `AGENTS.md`, or handover rules:

```markdown
## Mandatory AI-management repo read & Download UI rule (set by the user, 2026-11-24)

Every session (brand new at startup; resumed/old immediately upon resume if it has not read the current rules) MUST
read the ~/AI-management rules (the files listed in general/rules/mandatory-repo-read/reading-list.txt) before starting
work. Reading is the acknowledgment: in Claude Code a hook records the reads and refuses other tools until every
listed file is read; for agy and Codex `~/AI-management/general/rules/mandatory-repo-read/ack-rules.sh <session_id>`
looks in the session's own log, records the acknowledgment when every file was read whole, and names the unread files
otherwise (`--needs <session_id>` lists them); Gemini declares it with the same command, only after reading.
For any user-run download task, you MUST copy and adapt `~/AI-management/general/templates/download-ui/fetch_dst.py` and
`download_wrapper.sh` keeping the exact in-place dashboard UI, narrow <100-col layout, `status` mode, resume,
verification, single-instance guard, and exit codes, chain downstream data processing + checks + bridge wakeup per
`general/guides/chunked-pipeline-workflow/CHUNKED_PIPELINE_GUIDE.md` whenever processing follows download, and end your
response with the exact copy-paste runnable command.
```

---

## 5. Incident & Check

- **Incident (2026-11-24):** `claude e6 Committee` and `e6 executor` skipped reading `~/AI-management` rules, failed to deliver a download script, and failed twice to produce the required download UI/format.
- **Incident (2026-11-27):** a Claude Code session told two agy sessions that the rules had changed, named two files
  to read and asked for the acknowledgment. One read three of the nine changed files and acknowledged; the other read
  five whole and four in part, and acknowledged. Nothing checked an agy or Codex acknowledgment. Since then
  `ack_reads.py` reads the session's own log, the agy gate lists the unread files and records the acknowledgment by
  itself, and `--list` shows "reads checked" or "declared".
- **Check:**
  ```bash
  ~/AI-management/general/rules/mandatory-repo-read/ack_reads.py --selftest
  ~/AI-management/general/rules/mandatory-repo-read/ack-rules.sh --list
  grep -rln --exclude='*.bak*' -e "Mandatory AI-management repo read" -e "mandatory-repo-read/reading-list.txt" ~/.claude/CLAUDE.md ~/AGENTS.md ~/.gemini/config ~/.codex/skills ~/.claude/skills 2>/dev/null
  ```
