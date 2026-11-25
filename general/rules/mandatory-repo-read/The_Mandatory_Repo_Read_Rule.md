# The Mandatory Repo-Read & Download UI Rule

**Rule (set by the user on 2026-11-24), in the user's words:**

> serius bug. the claude e6 Committee and e6 executor skipped reading rules, didn't follow the rules to give a download script, and further failed to give a correct format/UI twice. Make the rules in repo more strict/clear to follow, and make sure any session to read the whole repo at least once before start to work. For brand new session, read at the very beginning; for old session but not acknowleged, read after resume

It binds every agent session on every machine: Claude Code, agy, Codex, and Gemini — whether Committee, Manager, Executor, or subagent. It adds to every other rule and relaxes none.

---

## 1. Mandatory Repo Read & Acknowledgment Gate

Every session MUST read the entire `~/AI-management` rule set **at least once** before doing any substantive work (planning, handovers, edits, script generation, or reviews):

- **Brand new session:** read at the very beginning of the session before starting any task.
- **Old / resumed session not yet acknowledged:** read immediately upon resume before continuing work. For agy and Codex "not acknowledged" also means acknowledged at an older `git HEAD` commit. For Claude Code it means that a listed file has changed since the session read it, and then only the changed files are read again.

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
10. `general/regulations/executor-regulations/HANDOVER_RULES.md`
11. `general/templates/download-ui/README.md`
12. `claude/rules/thought-chain-rigor/The_Claude_Thought_Chain_Rule.md`
13. `general/tools/handover-lint/README.md`
14. `general/rules/project-planning/The_Project_Planning_Rule.md`
15. Platform bridge guide as applicable: `general/guides/agent-control-macos/How_to_Control_Agent_Sessions_macOS.md` or `general/guides/agent-control-wsl/How_to_Control_Agent_Sessions_WSL.md`.

### How to acknowledge

**Claude Code (since 2026-11-25): by reading.** The rules-gate hook records each listed file that the session reads
whole with the Read tool, by content, and refuses the session's other tools until every listed file is read. There is
no command to run and none that can record it: `ack-rules.sh claude-<session_id>` only reports what is read. After a
commit the hook asks only for the listed files whose content changed. The list the hook uses is
[`reading-list.txt`](reading-list.txt) beside this file: items 1 to 14 above and the platform's bridge guide. Keep the
two in step, and keep host and hardware fixes out of these files (they go in `fix/`), because every change to a listed
file sends every session back to read it.

**agy, Codex, Gemini and manual runs: by declaration, after reading.** Record the acknowledgment for your session ID
at the current `HEAD` commit, and never without having read the files:

```bash
~/AI-management/general/rules/mandatory-repo-read/ack-rules.sh <session_id>
```

- For **agy** sessions: use `agy-<conversation_id>` (the `conversationId` passed by the hook).
- For **Codex** / **Gemini** / **manual** runs: use `codex-<thread_or_pid>` or `gemini-<id>`.

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

---

## 3. Enforcement Hooks (`claude/hooks/rules-gate/`, `claude/hooks/claude-guardrails/`, `agy/hooks/rules-gate/`)

- **Claude Code:** [`claude/hooks/rules-gate/install-claude-rules-gate-hook.sh`](../../../claude/hooks/rules-gate/install-claude-rules-gate-hook.sh) installs `~/.claude/hooks/ai-management-rules-gate.sh` on `PreToolUse`, `PostToolUse` (`Read`), `SessionStart`, `UserPromptSubmit` and `SubagentStart` (rewritten 2026-11-25).
  - `PostToolUse` records each listed file the session reads whole (its git blob id, in `~/.ai-management/rules-read/claude-<session_id>`). A read with an offset or a limit, and a subagent's read, do not count.
  - `PreToolUse` refuses every other tool until every listed file is read at its current content. Reading a listed file, and reading the machine rules file `CLAUDE.md`, stay allowed. A subagent rides on its session's record.
  - Session start and every prompt print what is unread, with `(changed since you read it)` on a file read before at an older content.
  - The gate fails open on an internal error, and `AI_MGMT_RULES_GATE_OFF=1` is the user's off switch; no agent sets it.
  - Before 2026-11-25 the gate was a note plus a self-declared acknowledgment tied to `HEAD`: nothing was refused, a session could acknowledge without opening a file, and every commit, whatever it changed, told every session to read everything again.
- **Claude Guardrails:** [`claude/hooks/claude-guardrails/install-claude-guardrails-hook.sh`](../../../claude/hooks/claude-guardrails/install-claude-guardrails-hook.sh) installs `~/.claude/hooks/ai-management-claude-guardrails.sh` to block `AskUserQuestion` pickers and edits of a `.py` file that add a `1 - cdf` upper tail or a hardcoded Python minor path, and injects T1–T5 reminders.
- **Antigravity (`agy`):** [`agy/hooks/rules-gate/install-agy-rules-gate-hook.sh`](../../../agy/hooks/rules-gate/install-agy-rules-gate-hook.sh) installs `~/.gemini/config/hooks/ai-management-rules-gate.sh` in `~/.gemini/config/hooks.json` on `SessionStart` and `PreInvocation`. Brand new sessions are gated at `SessionStart`; resumed/old unacknowledged sessions are gated at `PreInvocation` until `ack-rules.sh agy-<conversationId>` matches current `HEAD`.

---

## 4. Paste-in form

For a `CLAUDE.md`, `AGENTS.md`, or handover rules:

```markdown
## Mandatory AI-management repo read & Download UI rule (set by the user, 2026-11-24)

Every session (brand new at startup; resumed/old immediately upon resume if it has not read the current rules) MUST
read the ~/AI-management rules (the files listed in general/rules/mandatory-repo-read/reading-list.txt) before starting
work. In Claude Code a hook records the reads and refuses other tools until every listed file is read; agy, Codex and
Gemini then run `~/AI-management/general/rules/mandatory-repo-read/ack-rules.sh <session_id>`, only after reading.
For any user-run download task, you MUST copy and adapt `~/AI-management/general/templates/download-ui/fetch_dst.py` and
`download_wrapper.sh` keeping the exact in-place dashboard UI, narrow <100-col layout, `status` mode, resume,
verification, single-instance guard, and exit codes, and end your response with the exact copy-paste runnable command.
```

---

## 5. Incident & Check

- **Incident (2026-11-24):** `claude e6 Committee` and `e6 executor` skipped reading `~/AI-management` rules, failed to deliver a download script, and failed twice to produce the required download UI/format.
- **Check:**
  ```bash
  ~/AI-management/general/rules/mandatory-repo-read/ack-rules.sh --list
  grep -rln --exclude='*.bak*' -e "Mandatory AI-management repo read" -e "mandatory-repo-read/reading-list.txt" ~/.claude/CLAUDE.md ~/AGENTS.md ~/.gemini/config ~/.codex/skills ~/.claude/skills 2>/dev/null
  ```
