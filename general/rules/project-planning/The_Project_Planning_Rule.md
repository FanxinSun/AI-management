# The Project Planning Rule: one PLAN.md, one execution order, sub-plans as steps

**Rule (set by the user on 2026-09-23), in the user's words:**

> for a project, if it's multi-outcome, then it should have one and only one PLAN.md; for its multiple lanes, samely
> have their own one and only one sub-plan.md respectively; within the plan, there should be one and only one
> execution order. Their positions and file structure should be like:
>
> ```text
> project_root/
> ├── PLAN.md
> └── plan/
>     ├── PLAN_lane0.md
>     ├── PLAN_lane1.md
>     └── lane0_subplan_A/
>         ├── A-0.md
>         ├── A-1.md
>         └── subplan_A-0/
>             ├── A-0-0.md
>             └── A-0-1.md
> ```
>
> for single-outcome project, it's similarly be:
>
> ```text
> project/plan/
> ├── PLAN.md
> └── subplan_A/
>     ├── A-0.md
>     ├── A-1.md
>     └── subplan_A-0/
>         ├── A-0-0.md
>         └── A-0-1.md
> ```
>
> each sub-plan is a single execution step from the main PLAN.md

It binds every agent session on every machine: Claude Code, agy, Codex, Gemini and any other agent, whether manager,
executor or workflow subagent. It adds to every other rule and relaxes none. The user added to it three times; each
addendum is below with the user's words.

The quotations are the rule. The rest says how sessions apply it. Where the two seem to differ, the quotation wins,
and in any doubt the session asks the user.

## The layout

| File | Where it lives | What it is |
|---|---|---|
| `PLAN.md` | the project root (multi-outcome project), or `<project>/plan/` (single-outcome project); never both | the project's one and only plan |
| `PLAN_lane<N>.md` | `plan/`, beside a root `PLAN.md` | lane N's one and only sub-plan |
| `<X>-<n>.md`, for example `A-0.md` | `plan/lane<N>_subplan_<X>/`, or `plan/subplan_<X>/` in a single-outcome project | step n of sub-plan X |
| `<X>-<n>-<m>.md`, for example `A-0-0.md` | `subplan_<X>-<n>/` inside that directory, and so on downwards | step m of step `<X>-<n>` |

- **A lane is one outcome** of a multi-outcome project. A project with a single outcome has no lane files.
- **A sub-plan file is one execution step of the plan above it.** `A-0.md` is one step of sub-plan A, and `A-0-0.md`
  is one step of `A-0`. A step gets a file, and a directory below it, only when it needs that detail.
- **One execution order per plan.** Every plan and sub-plan holds a single sequence of steps, never two competing
  orderings.
- **Never a second plan file at the same level.** No `PLAN_v2.md`, no `PLAN_final.md`, no draft beside the plan.
  Update the one plan in place; git keeps the earlier versions.
- **A plan file is known by its name.** It is a Markdown file whose name has `plan` or `subplan` as a whole word, in
  any letter case, where `_`, `-` and `.` separate the words: `PLAN.md`, `PLAN_lane0.md`, `PLAN_v2.md`,
  `test-plan.md`, `sub-plan.md`. Such a name is allowed only at the positions in the table. Notes, reviews, reports
  and ledgers take names without that word: `planning-notes.md` is fine, `plan-notes.md` is not. This document's own
  file name says "Planning" for that reason.

## Addendum: every AI agent works from the same plan files (user, 2026-09-24)

> a plan may be processed by different AI agents, like Codex, ClaudeCode, Antigravity, CLM, etc; all agents keep
> sharing the same planing/subplaning docs (one and only one PLAN rules maintained across different AI agents), only
> with their watermarks/ledgers in separated docs for machine/ai-agentic reference only

> This means every AI agent uses the same canonical plans and subplans. Agent watermarks and ledgers stay in separate
> reference documents and must not become competing plans.

- **No agent keeps its own plan.** Every agent that works on the project reads and updates the same plan and sub-plan
  files. No copy, fork or variant per agent.
- **Ledgers are separate, and are not plans.** An agent's watermarks and ledgers (execution logs, state stamps,
  agent-specific notes) live in their own documents, for machine reference only. They are named as ledgers, never
  named or shaped like a plan file, and never carry an execution order of their own.

## Addendum: taking a project over from another AI agent (user, 2026-09-25)

> new addendum to the previous planning rule:
> 1. when takeover or continue halfway of a project (from other AI agents like Codex/GLM/Antigravity, not another
> session of Claude Code), FIRST do git push, to keep the initial taken-over state retrievable at anytime; if no git
> repo existing, create a private new one then push;
> 2. The takeover should be thorough, including reading every line of all planning docs; when updating the planning
> docs, it should also be thorough, making sure every line of every planning doc is reviewed and up-to-date
> 3. when updating existing planning doc, obey "increase-only" principle: keep all the original terms/phases/steps in
> the planning docs as it is; for those you want to cross out, just add comment saying "retired", never delete the
> original contents.

The user restated it in the same message:

> 1. Snapshot first: commit the initial state as needed, push, and verify it. Create a private repository if none
> exists.
> 2. Increase-only planning: retain all original content; add explicit “retired” annotations and replacements without
> deleting originals.
> 3. Complete review: read every line of all planning documents during takeover and every planning update.

- **Who it is for.** The words were given to Claude Code sessions, and they leave out "another session of Claude
  Code". This document reads them for every agent: a takeover is from a different AI agent (Claude Code from Codex,
  agy from Claude Code, Codex from agy), not from another session of the same agent.
- **Snapshot first.** Before any other action: commit the state as found, push, and verify the push, so the state
  taken over can be retrieved at any time.
- **Where the snapshot goes.** To a repository the user owns; if the project has none, a new private one. If the
  project's remote is public, or is not the user's, the push is gated like any other push
  ([The Regular Remote Push Rule](../regular-remote-push/The_Regular_Remote_Push_Rule.md),
  [The Others' Repositories Regulation](../../regulations/others-repositories/The_Others_Repositories_Regulation.md)):
  ask the user where the snapshot goes, before anything else.
- **Complete review.** Read every line of every planning document at the takeover, and again at every later update of
  the planning documents: every line is reviewed and brought up to date.
- **Increase-only.** Keep all original terms, phases and steps as they are. To cross something out, mark it
  "retired" and put the replacement beside it. Never delete original content.

## Addendum: a submodule is a project of its own (user, 2026-10-09)

The user's words, relayed by a manager session:

> a new submodule of an existing project should be allowed to have/edit its own canonical PLAN.md and consequential
> subplans

- **The project boundary is the git repository.** A directory that is its own git repository (it has its own `.git`,
  as one added with `git submodule add` has) is a project of its own, with its own `PLAN.md`, lane files and
  sub-plans, independent of the plan of the project around it.
- **A directory inside the same git repository is not a separate project.** No second plan tree below an existing
  one. A folder that is meant to be a submodule becomes its own git repository first.

## Who changes a plan

This rule says where plans live and what shape they have. Who may change them follows the seats
([The Executor Regulations](../../regulations/executor-regulations/The_Executor_Regulations.md)): making the plan is
the manager's work, and an executor does not change the plan. It inserts the manager's exact texts when told to,
insert-only (Part A, rule 13).

## Plan files from before the rule

A plan file outside the layout (a `PLAN_B01.md`, a `plan_v2.md`, a second `PLAN.md` further down) is not edited any
further. Reading it and deleting it are fine: move its content into the canonical files, then delete it.

## Check

```bash
/usr/bin/python3 -I ~/AI-management/general/tools/handover-lint/check_spec.py --plan-layout <project_dir>
/usr/bin/python3 -I ~/AI-management/general/tools/handover-lint/check_spec.py --plan-layout <path/to/planned-file.md>
```

- Each plan file that is not canonical is printed as `ERROR [PLAN_LAYOUT] <path>:1: <reason>`. The last line is
  `Checked <N> markdown file(s): <P> plan file(s) by name, <E> not canonical`. Exit status 0 means none, 1 means at
  least one.
- A file path that does not exist yet is checked as a planned file, so a name and place can be tested before the
  file is written.
- Run it after creating, renaming or moving a plan file, and before dispatching a handover that points to one. The
  ordinary run of `check_spec.py` on a Markdown file makes the same check on that file.
- The check sees names and positions. It cannot see a second execution order inside a plan, or a plan kept under a
  name without the word. Those stay the session's duty.

What refuses a wrong plan file at write time:

- **Claude Code on the WSL machine:** a plan-file guard hook denies creating or editing a plan file that is not
  canonical, in every session. It was set on 2026-09-24, after a Claude Code session that held the rule wrote
  `PLAN_B01` to `PLAN_B12`, `PLAN_finish` and `PLAN_shared`.
- **agy, Codex, Gemini, and Claude Code elsewhere:** nothing refuses the write. The session runs the check itself.

## Paste-in form

For a `CLAUDE.md`, `AGENTS.md`, or the "Rules" of a handover:

```markdown
## Project plans: one PLAN.md, one execution order, sub-plans as steps (set by the user, 2026-09-23)

A project has one and only one PLAN.md: at the project root for a multi-outcome project, with one
plan/PLAN_lane<N>.md per lane, or in <project>/plan/ for a single-outcome project. Sub-plan files (A-0.md in
subplan_A/, A-0-0.md in subplan_A-0/, and so on) are each a single execution step of the plan above them, and every
plan holds exactly one execution order. Never a second plan file at the same level (no PLAN_v2.md, no draft beside
the plan) and no plan root below another in the same git repository; a submodule that is its own git repository is
its own project. Every AI agent reads and updates the same plan files; an agent's own ledgers and notes live in
separate files that are never named or shaped like plans. Taking a project over from another AI agent: snapshot first
(commit, push, verify; a private repository if there is none), read every line of every planning document, and edit
increase-only (mark an item "retired", never delete it). Check a project with
`~/AI-management/general/tools/handover-lint/check_spec.py --plan-layout <project>`. Full text:
The_Project_Planning_Rule.md in the AI-management repository.
```

## Where it is in force

- Claude Code on the WSL machine: section 3 of `~/.claude/CLAUDE.md` (since 2026-09-23, each addendum on its date),
  the session-start reminder, and the plan-file guard hook.
- Every agent: rule 20 of [`EXECUTOR_RULES_BLOCK.md`](../../regulations/executor-regulations/EXECUTOR_RULES_BLOCK.md),
  which `install-executor-rules.sh` installs into agy's global rules and into the Codex and Claude Code
  executor-rules skills; the required reading list of
  [The Mandatory Repo-Read Rule](../mandatory-repo-read/The_Mandatory_Repo_Read_Rule.md); and the manager's checklist
  in [`HANDOVER_RULES.md`](../../regulations/executor-regulations/HANDOVER_RULES.md).

Where it is installed; nothing is listed until it is:

```bash
grep -rln --exclude='*.bak*' -e "Project plans" -e "Plan files: one PLAN.md" ~/.claude/CLAUDE.md ~/.gemini/config ~/.codex/skills ~/.claude/skills 2>/dev/null
```

## Origin

The user gave the rule and its addenda to Claude Code sessions on the WSL machine between 2026-09-23 and 2026-10-09,
where it has been section 3 of the machine rules since. It was recorded here on 2026-11-26 at the user's word:
"record the PLAN.md + subplans RULE to ~/AI-management repo, merge into its currrent scope so that not only claude,
but all other agents like ayg/codex can also follow it".
