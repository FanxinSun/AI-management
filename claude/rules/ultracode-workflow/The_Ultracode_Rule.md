# The Ultracode Rule: self-started workflows, lower-effort subagents

**Rule (set 2026-11-10):** a Claude Code session may start a dynamic workflow on its
own judgment even when ultracode is off; every subagent of that workflow runs at an
effort level strictly below the main session's, on the same model or a less capable
one; and the main session may stop the workflow and carry on single-threaded once the
subagents are no longer needed.

On the WSL machine the rule is section 5 of `~/.claude/CLAUDE.md`, and a one-sentence
version opens every session through the SessionStart reminder hook. The portable text
is [`CLAUDE_md_section5.md`](CLAUDE_md_section5.md).

## The three parts

1. **Self-start.** Ultracode itself is a session setting that only the user can toggle
   (`/effort ultracode`). The rule makes the decision to orchestrate the session's own:
   when it judges a workflow necessary, it starts one with the Workflow tool in the
   middle of its work and decides how many subagents to use. The rule is the user's
   standing, explicit opt-in, so no keyword or toggle is needed.
2. **Lower effort, same or lower model.** By default an `agent()` call inherits the
   main session's effort and model. Under this rule every call sets `effort` strictly
   lower: a main session at `max` gives its agents `xhigh` at most, and how much lower
   is the main session's call. A session at `low` has nothing lower to give, so it
   works single-threaded. The model may be the same or a less capable one, never a
   more capable one.
3. **Stop when no longer needed.** The main session may stop a running workflow (the
   TaskStop tool, or `x` in `/workflows`) and finish the work itself. Completed
   agents' results stay saved, so the run can be relaunched later.

Order of effort levels: `low` < `medium` < `high` < `xhigh` < `max`.
Order of models: Fable > Opus > Sonnet > Haiku.

## In a workflow script

```js
// main session: Fable at max
const a = await agent(prompt, { effort: 'xhigh' })                // same model, one level lower
const b = await agent(prompt, { effort: 'high', model: 'opus' })  // lower effort and a weaker model
```

Never omit `effort`: an agent without it runs at the main session's level.

## How it fits the responsibility split

Amended by the user on 2026-11-10: handing work to an executor is an option for a
manager, not an obligation. For settled hands-on work a manager picks one of three
routes:

- a handover to a visible executor session;
- doing the job itself, on its own judgment or at the user's direct demand;
- a workflow inside its own session, under this rule.

Any session may use a workflow within its own work, including an executor on its
handed-over job. In a manager's workflow the agents do the hands-on work and collect
evidence; the manager still makes the decisions, checks what comes back, and gives the
verdicts.

## How to apply on another machine

```bash
claude/rules/ultracode-workflow/install-ultracode-rule.sh          # appends the section to ~/.claude/CLAUDE.md
claude/rules/ultracode-workflow/install-ultracode-rule.sh FILE     # or to another CLAUDE.md
```

The installer appends the portable section once, backs up an existing file to
`<file>.bak-ultracode`, and does nothing when the section is already there. It refuses
to touch `~/.claude/CLAUDE.md` while `~/.claude/settings.json` denies edits to it; on
such a machine the section goes in through the user's guard-lift procedure.

A machine that installed the section before the 2026-11-10 amendment keeps the old
last paragraph, because the installer skips a file that already has the section.
Replace that paragraph by hand there with the one in
[`CLAUDE_md_section5.md`](CLAUDE_md_section5.md).

Sessions already running pick the rule up at their next prompt on a machine with the
rule-refresh hook, and at their next start everywhere else.

## Check

```bash
grep -n 'Dynamic workflows (ultracode)' ~/.claude/CLAUDE.md
```
