
## 11. Script delivery: the ordered format, the user's run, nothing claimed before it

Set by the user on 2026-11-27, after two agy sessions delivered a pipeline script with a
dashboard of their own, three times called it "the original format" without comparing
anything, and closed project steps on a script line that one of them had typed by hand;
verbatim: "they fail to give a script in ordered format, continue the project without
the script run/done, and gave me random messages".

- The format of a script the user will run has one reference: the templates in
  ~/AI-management/general/templates/download-ui/ and general/templates/chunked-pipeline/
  at the commit the session read. The script is built by copying their files. A
  screenshot, memory or another script is not the reference. Where no template fits,
  the session says so and asks the user.
- A format claim ("restored", "matches", "compliant") needs a check that can fail: the
  session captures the script's screen at 100 and 80 columns, runs
  ~/AI-management/general/rules/script-delivery/check_frame.py on the captures, and
  pastes the commands and their output. Without it, it writes "format not compared".
- Only a script sends a script's lines. No session types a "[PIPELINE …]" line. A
  manager that receives one reads the sender in ~/.claude/agy-bridge/send.log
  (user@<tty> is a script, a session's name is an agent) and the script's own files
  before it acts.
- A run counts only when the user started it, on a script the user has not objected to,
  with the pinned tools unchanged since. After an edit to a pinned tool, what is on disk
  is test output.
- While the user is correcting a script the project waits: no verdict, no decision that
  closes a step, no push of one, no question about later steps.
- A session answers what was asked, and writes "done", "closed" or "fixed" only for what
  a command showed and the user accepted.

Full text:
~/AI-management/general/rules/script-delivery/The_Script_Delivery_Rule.md.
