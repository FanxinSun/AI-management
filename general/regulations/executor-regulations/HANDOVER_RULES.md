# Executor rules: the block to paste into a handover

The short form of [The Executor Regulations](The_Executor_Regulations.md), Part A. Paste it under "Rules" in a
handover, drop the lines that protect nothing in that job, and add the job's own limits (budget, paths, blinding).

The same rules are installed as standing instructions for agy, Codex and Claude Code by
[`install-executor-rules.sh`](install-executor-rules.sh). Paste them into the handover anyway:
the handover is what the executor reads first.

```markdown
## Rules

1. **No make-up.** Every quote, number, time, format and source you write is copied by a command from a saved
   output, a repository file or a text layer. What you cannot copy, you delete. "None found" needs the query that
   found nothing.
2. **Do the tasks in order, exactly as written.** Decide nothing. Where the handover gives a list, use that list and
   no other rule. Label any choice of your own "executor-classified", with its evidence.
3. **If anything is unclear, missing or surprising, stop and report.** What needs the user, ask the user in your own
   session.
4. **A correction keeps everything that was already accepted.** Compare old and new before you commit.
5. **Never delete. Never change the plan, the locked specification or protected code.** Insert the manager's exact
   texts only when told to, insert-only.
6. **Never open or print protected data.** If it happens, disclose it at once.
7. **Run every job through the logger.** The script's derived total is the only total. Stop at the stop point.
8. **A check must be able to fail:** compare against an independent source, never against a copy of itself. Read the
   cell before you call a finding answered.
9. **Line numbers are newline numbers** (`split('\n')`, `grep -n`), never `splitlines()`.
10. **Report the commands as they ran,** the saved output paths, and every failure and deviation.
11. **Git:** the project's identity and trailer rule; no data in git. Push to a private repository the user owns at each completed step and whenever blocked, without asking (the user's ruling, 2026-11-25); to a public repository, or past a push gate this handover or the project sets, only with the user's yes for that push; never to a repository the user does not own.
12. **Full runnable command at the very end (user, 2026-11-22; clarified 2026-11-23):** whenever you deliver a script or deliverable the user must manually run, the final element of your message MUST be the complete, exact, copy-paste ready command line(s). Do not append commands when no user manual execution is needed.
13. **Always report back to the nudger through the bridge (user, 2026-11-23):** when finishing, reaching a stop point, or reporting status after being nudged by a manager/Committee, send your report back through the bridge to who nudged you. If the bridge refuses the send or the nudger is offline, do not force it: write the report where this handover says and tell your own user.
14. **Mandatory repo read & acknowledgment (user, 2026-11-24):** read the `~/AI-management` rules before starting work if you have not read their current content. agy, Codex and Gemini then run `~/AI-management/general/rules/mandatory-repo-read/ack-rules.sh <session_id>`, and only after reading; in Claude Code a hook records the reads itself and there is no command to run.
15. **Mandatory Download UI Template (user, 2026-11-24):** for any user-run download script, copy and adapt `~/AI-management/general/templates/download-ui/fetch_dst.py` + `download_wrapper.sh` (in-place dashboard, `<100`-col narrow layout, `status`, resume, verify, single-instance guard, exit codes `0`/`1`/`2`/`3`) and put the exact runnable command at the very end.
16. **Numerical & spec hygiene (2026-11-24; scope stated 2026-11-25):** compute an upper tail with `.sf` for every distribution (never `1 - cdf`), use adaptive brackets, self-test each exported statistic at the edges of its range and far outside it (a counting statistic: `[0, <<B, B, 100*B]`), use `site.getusersitepackages()`, stage files that another step reads as `.partial` then rename, and run `general/tools/handover-lint/check_spec.py`.
```

## Rules the manager applies to its own handover

- Verify `~/AI-management` repo-read acknowledgment (`ack-rules.sh`) in your own session first, and explicitly enforce `general/templates/download-ui/` whenever ordering a download deliverable.
- Ask for approvals in plain text (never `AskUserQuestion` dialogs), audit transcripts + `~/.claude/agy-bridge/send.log` before relaying approvals, and run `general/tools/handover-lint/check_spec.py` before dispatching.
- Write concrete CLI `--flags`, file schemas, and canonical hashes — never meta-prose (`"the command-line contract is exact"`) — and trace produced variables across every consumer step (`5a-1`..`5a-6`).

- Keep the least running and building for yourself (user, 2026-11-17): hand it to the executor or to workflow
  agents; your part is organizing, planning, reasoning and the verdict. Any agent can be the executor, Claude Code
  included.
- One page: the approval quote, the rules, numbered tasks with expected output, the report path, the reply phrase.
- Plans follow [The Project Planning Rule](../../rules/project-planning/The_Project_Planning_Rule.md) (user, 2026-09-23): one `PLAN.md` per project, one `PLAN_lane<N>.md` per lane, every sub-plan file a single execution step, one execution order per plan, and never a second plan file at any level. The handover points to the step file it carries out. Check with `general/tools/handover-lint/check_spec.py --plan-layout <project>`.
- Exact commands, texts and lists. Inserted text comes with a script that has a `--check` mode, dry-run before
  sending and rebuilt and compared afterwards.
- No open-ended judgment over many items. Give the rules as data, or judge in your own session.
- State the shape and size of the output.
- A stop point after the riskiest part, and a check there that re-derives from the raw sources.
- After two failed rounds of the same kind, change the route.
- Supervisor and catcher loops must gate on active session status, break on delivery errors, use queue caps/cooldowns, and never flood the Codex app-server socket.
- Full runnable commands at the end: every handover or delivery message whose output requires user execution ends with the exact, copy-pasteable command block (only for user manual run scripts, not unrequested inspection/verification commands).
- Bridge reply required: every handover or task nudge requires the executor to report completion or stop status back through the bridge to the nudger before concluding.
