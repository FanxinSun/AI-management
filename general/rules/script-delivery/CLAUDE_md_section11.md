
## 11. Planners and executors: claims, scripts and acknowledgments

Set by the user on 2026-11-27, after two agy sessions delivered a pipeline script with a
dashboard of their own, three times called it "the original format" without comparing
anything, and closed project steps on a script line that one of them had typed by hand;
verbatim: "they fail to give a script in ordered format, continue the project without
the script run/done, and gave me random messages". And on whom the fixes are for: "all
the new discoveries and fixes are targeted for either planners or executors, no matter
what AI brand they are". The rules below bind the seat, whatever the brand; a planner
is the manager of section 1.

The executor (any session doing hands-on work):

- builds a script the user will run by copying the templates in
  ~/AI-management/general/templates/download-ui/ and general/templates/chunked-pipeline/
  at the commit it read. A screenshot, memory or another script is not the reference.
  Where no template fits, it stops, says so and asks.
- writes "restored", "matches", "compliant", "passed" or "done" only with the check that
  could have shown the opposite, its command and its output: for a script's screen,
  ~/AI-management/general/rules/script-delivery/check_frame.py on captures at 100 and 80
  columns. Without it, it writes the state as it is ("format not compared").
- never types a script's "[PIPELINE …]" line, and says that outputs made before an edit
  to a pinned tool are test outputs.
- proves a checker, a fixture and every command it writes into a document before handing
  them on: patterns from the producer's code, tests at the edges of each range, fixtures
  captured and not typed, commands run as written.

The planner (a designated manager):

- accepts no such claim without its check, and writes none.
- before acting on a bridge line, reads its sender in ~/.claude/agy-bridge/send.log
  (user@<tty> is a script, a session's name is an agent) and the script's own files.
- while the user is correcting a deliverable, records no verdict, closes no step, pushes
  no closure and asks nothing about later steps; gives a verdict only on a run the user
  started, on a script the user has not objected to, with the pinned tools unchanged.
- proves what it hands out as a standard before it sends it out, and names the first
  version's faults when it corrects it.
- tells sessions of a rules change by its commit, never by a part of the files: a
  session reads what ack-rules.sh --needs <its id> lists.

Every seat: a session answers what was asked. Reading is the acknowledgment of the
AI-management rules for every brand: Claude Code's hook records the reads, and for agy
and Codex ~/AI-management/general/rules/mandatory-repo-read/ack-rules.sh checks them in
the session's own log and refuses while a file is unread.

Full text:
~/AI-management/general/rules/script-delivery/The_Script_Delivery_Rule.md, and Parts A
and B of
~/AI-management/general/regulations/executor-regulations/The_Executor_Regulations.md.
