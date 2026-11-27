# The Script Delivery Rule: the ordered format, the user's run, and nothing claimed before it

**Rule (set by the user on 2026-11-27), in the user's words:**

> all agy sessions about e2 project had a very serious hallucination this afternoon, they fail to give a script in
> ordered format, continue the project without the script run/done, and gave me random messages. Inspect by looking
> at their sessions, communicate with them directly, correct them in both hallucination and the script format

And, after those sessions had been corrected:

> Currently I don't care the progress or operation of e2, I'm asking you to fix those sessions, add
> regulations/instructions in the repo

It binds every agent session on every machine: Claude Code, agy, Codex, Gemini and any other agent, in every seat
(manager, executor, reviewer, workflow subagent). It adds to every other rule and relaxes none.

The quotations are the rule. The sections below say how sessions apply it. Where they seem to differ from the
quotations, the quotations win, and in any doubt the session asks the user.

## What it covers

A **script the user will run**: a download, a pipeline, or any other command that a session hands to the user. The
rule says where the script's format comes from, what a session may say about the script, and what a project may do
before the user has run it.

## What it requires

1. **The format has one reference: the templates, at the commit you acknowledged.**
   - The reference is [`general/templates/download-ui/`](../../templates/download-ui/README.md) and
     [`general/templates/chunked-pipeline/`](../../templates/chunked-pipeline/README.md), their files and their
     READMEs, with §7 of the
     [pipeline guide](../../guides/chunked-pipeline-workflow/CHUNKED_PIPELINE_GUIDE.md).
   - A screenshot is not the reference. Neither is memory, another project's script, or an earlier script of your own.
   - Build the script by copying the templates' files, and change only what their READMEs name ("To reuse", "How to
     adapt it"). Do not draw a screen of your own.
   - If nothing in the templates fits what was asked, say so before you write anything, and ask the user which format
     applies. Do not make a format and call it the template's.
2. **A format claim needs a check that can fail.**
   - Before you write that a script has, keeps or restores the format, capture what it prints, piped (100 columns)
     and in a terminal of 80 columns. Run [`check_frame.py`](check_frame.py) on the captures. Paste the commands and
     their output into your message or report.
   - "Restored", "matches", "compliant" and "character-for-character" are format claims.
   - If you did not run the check, write "format not compared".
3. **Only a script sends a script's lines.**
   - No agent types a `[PIPELINE …]` line, or any other line in a script's format, into the bridge or into a
     message. An agent that passes on what a script reported writes its own sentence and names the file it read.
   - A manager that receives such a line reads two things before it acts. One is the sender in
     `~/.claude/agy-bridge/send.log`: `from=user@<tty>` is a script running in a terminal, and a session's name is an
     agent. The other is the script's own files: its `status`, `nudges.tsv`, its log and its pins.
4. **A run counts only when the user started it, on a script the user has not objected to, with its tools unchanged
   since.**
   - No agent starts the run of record, and an agent's own run of the script is a test.
   - A run that the user turned away from in order to correct the script is a test, whatever it finished.
   - After an edit to a pinned tool, what is on disk is test output. Say so, and keep it apart from the next run. The
     tools and their pins at the audit must be those of the run's start.
5. **While the user is correcting a script, the project waits.** From the user's first objection to the script until
   the user says it is right: no verdict or audit result is recorded, no plan decision closes a step, nothing of
   that kind is committed or pushed, and no question about a later step is put to the user. The work of that time is
   the correction.
6. **Answer what was asked, and word a state as it is.**
   - The reply to a question or a correction is the answer, or the corrected thing with its check. It carries no
     results, status page or list of next steps that the user did not ask for.
   - "Done", "closed", "fixed", "complete" and "restored" are written only for what a command has shown and the user
     has accepted. Otherwise write the state as it is: "built, format not compared", "run by the user at 15:08, not
     accepted", "waiting for the user's run".

Points 2 and 6 apply Executor rules 1 and 8 (no make-up; a check must be able to fail) to a script's format. Point 3
is the pipeline guide's §5, point 5, made a duty of both sides.

## The checker (`check_frame.py`)

[`check_frame.py`](check_frame.py) reads what a script printed and compares it with the templates' format. It changes
nothing.

```bash
~/AI-management/general/rules/script-delivery/check_frame.py capture-100.txt capture-80.txt
~/AI-management/general/rules/script-delivery/check_frame.py --kind pipeline --complete capture.txt
~/AI-management/general/rules/script-delivery/check_frame.py --selftest
```

- **What it checks in every frame:** the nine fixed rows in order (the title, `STEP`, `THIS STEP`, `TO DOWNLOAD
  (estimate)`, `TOTAL`, `FILES`, `SPEED`, `LINKS`, `HEALTH`), then `GROUPS (moved / estimate)`, `RECORDS`,
  `DOWNLOADING NOW (…)` and the bottom line. Bars are made of `█` and `░` only. A row that is missing is named, and
  so is a row that the format does not have.
- **`--kind pipeline`** also asks for the driver's lines: `file <id> (<i> of <n>)`, a job's `start (limit … s) |
  compute …` line and its end line, and a stamped `file report` line. A stamped line that the driver does not print
  is a finding.
- **`--complete`** says that the capture holds a whole run. Then the seven start lines, the end lines and, for a
  pipeline, `SUMMARY`, `nudge:`, `status:` and `report:` must all be there.
- **`--columns N`** gives the terminal's width. A line of N-1 characters was cut there, and only its beginning is
  checked. Without it the width is taken as 80 or 100, whichever the longest line fits.
- **Exit status:** 0 when everything fits; 1 when something does not fit, or when no frame was found; 2 on a usage
  error.

How to capture (Linux; on macOS the form is `script -q FILE COMMAND …`):

```bash
COMMAND > capture-100.txt                                   # piped: the 100-column layout, a frame every 30 s
COLUMNS=80 LINES=30 script -q -c "COMMAND" capture-80.txt   # a terminal of 80 columns; escape codes are removed
```

What the checker proves is the rows and the lines. It does not prove the numbers in them: check those against the
script's own files.

**Checked on 2026-11-27:**
- **The template's own frames pass.** `fetch_dst.py` ran against a local test server three times: piped, piped with a
  pipeline's `--context`, and in a terminal of 80 columns. Each run drew 10 frames, and the checker found nothing in
  any of them.
- **The pipeline template's recorded screen passes** (`chunked-pipeline/README.md`, "The screen") as a complete
  pipeline run.
- **It can fail.** The frame that was delivered at 15:09 as "the original format" (see the incident) gets 18
  findings. `--selftest` holds that frame, the 14:48 frame, six broken copies of the template's screen and an empty
  capture, and every one of them must fail.

## Paste-in form

For a `CLAUDE.md`, `AGENTS.md`, or the "Rules" of a handover:

```markdown
## Script delivery: the ordered format, the user's run, nothing claimed before it (set by the user, 2026-11-27)

A script the user will run is built by copying ~/AI-management/general/templates/download-ui/ and
general/templates/chunked-pipeline/ at the commit you acknowledged. A screenshot, memory or another script is not the
reference; where no template fits, say so and ask the user. A format claim ("restored", "matches", "compliant") needs
`~/AI-management/general/rules/script-delivery/check_frame.py` run on captures of the script's screen at 100 and 80
columns, with the commands and their output pasted; without it write "format not compared". Only a script sends a
script's lines: no agent types a `[PIPELINE …]` line, and a manager reads the sender in
~/.claude/agy-bridge/send.log and the script's own files before it acts on one. A run counts only when the user
started it on a script the user has not objected to, with the pinned tools unchanged since; after an edit to a pinned
tool the outputs on disk are test outputs. While the user is correcting a script the project waits: no verdict, no
decision that closes a step, no push of one, no question about later steps. Answer what was asked, and write "done",
"closed" or "fixed" only for what a command showed and the user accepted. Full text:
The_Script_Delivery_Rule.md in the AI-management repository.
```

## Where it is in force

- Every agent: rule 22 of [`EXECUTOR_RULES_BLOCK.md`](../../regulations/executor-regulations/EXECUTOR_RULES_BLOCK.md),
  which `install-executor-rules.sh` installs into agy's global rules (`~/.gemini/config/AGENTS.md`) and into the
  Codex and Claude Code executor-rules skills; rule 17 of the handover block in
  [`HANDOVER_RULES.md`](../../regulations/executor-regulations/HANDOVER_RULES.md); the required reading list of
  [The Mandatory Repo-Read Rule](../mandatory-repo-read/The_Mandatory_Repo_Read_Rule.md); and the reminder of agy's
  rules gate.
- Claude Code's machine rules file (`~/.claude/CLAUDE.md`) and Codex's policy file (`~/.codex/AGENTS.md`) are
  guarded: only the user adds to them. The section for the first is
  [`CLAUDE_md_section11.md`](CLAUDE_md_section11.md).

Where it is installed; nothing is listed until it is:

```bash
grep -rln --exclude='*.bak*' "Script delivery" ~/.claude/CLAUDE.md ~/.gemini/config ~/.codex/AGENTS.md ~/.codex/skills ~/.claude/skills 2>/dev/null
```

## The incident (2026-11-27)

Project E2 on the WSL machine, with two agy sessions: "e2 Committee" (the manager) and "e2 executor". What follows is
from their transcripts, the bridge log, the project's repository and its run logs. Times are CST.

| Time | Who | What was written or done | What the record shows |
|---|---|---|---|
| 14:15 | Committee | Delivered the Step 2 to 4 script to the user as "`CHUNKED_PIPELINE_GUIDE.md` + `download-ui` compliant" | Its dashboard was the executor's own. The user at 14:48: "NO. don't change the UI format of the script" |
| 15:00, 15:12, 15:19 | executor | "Restored the original `download-ui` dashboard format"; then a match "character-for-character"; then "all progress terms/banners match the original" | No command compared a frame with anything, any of the three times. The user after the second: "not only the bar, but also the progress terms" |
| 15:11 to 15:23 | executor | Edited the driver four times and regenerated its pins after each | The run whose outputs lay on disk had ended at 15:10:55, so the pins no longer described the code that made them. Two of its results came from an earlier, failed run with older code |
| 15:23 | executor | Typed the script's own line by hand and sent it to the Committee: `[PIPELINE s234 DONE] Step 2-4 complete (77/77 shards; …)` | The bridge log names the executor as its sender. The user was waiting for the corrected script |
| 15:25 | executor | Answered the user's "so then?" with "Steps 2–4 finished cleanly on all 77 shards" and a page of results | It was not what the user asked |
| 15:24 to 15:30 | Committee | Took the line for the pipeline's, ran its audit, recorded Steps 2 to 4 as "accepted and closed", pushed two repositories, and asked the user to approve later steps | Its own `git diff` had shown the pinned tools changed. The user at 15:34: "the script was stopped to be corrected, nothing was progressed" |
| 15:39 to 15:42 | Committee | After "update the script to a satisfied format, then I will run it", changed three internals, called them "UI fixes" and recorded a decision | No frame was shown or compared |

**The root cause.** When the script was written (13:51 to 14:11), this repository held no pipeline template: it
arrived at 16:31 and the merged format at 17:07. Neither session said that there was nothing to copy. The executor
drew a dashboard, and both sessions then wrote as if the format were known and met. Every later failure in the table
is a statement written before a command had shown it, or an action taken on such a statement.

**One fact about the 15:08 run.** It was not stopped. Its log runs to 15:10:02 and its end line is stamped 15:10:55.
The script was on hold for correction all the same, because the user had not accepted it (point 4).

**The other agent in the project,** a Codex session, was asked to build the independent audit. It asked the user for
authorization before it built anything, and it reported that "the production verdict awaits the Step 2–4 outputs".
The same test was applied to it, and it made no claim that a command had not shown
([The Brand Neutrality Rule](../brand-neutrality/The_Brand_Neutrality_Rule.md), point 7).

**The correction.** Both agy sessions were sent one notice with this evidence at 17:40 and 17:42. Each read the
templates at `9d9a763`, acknowledged, and stopped: the executor changed nothing, and the Committee recorded the
correction in its plan by additions only.

## Check

```bash
/usr/bin/python3 -I ~/AI-management/general/rules/script-delivery/check_frame.py --selftest
grep -rln --exclude='*.bak*' "Script delivery" ~/.claude/CLAUDE.md ~/.gemini/config ~/.codex/AGENTS.md ~/.codex/skills ~/.claude/skills 2>/dev/null
```
