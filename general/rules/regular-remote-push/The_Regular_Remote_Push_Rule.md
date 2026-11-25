# The Regular Remote Push Rule: supervisor-reviewable progress and blockers in git

**Rule (set by the user on 2026-11-23), in the user's words:**

> all the projects with git repo should push to the remote regularly with descriptions enough for a supervisor to review the progress and blockers situation from the git repo's contents sorely

It binds every agent session on every machine: Claude Code, agy, Codex, and Gemini, whether manager, executor, or workflow subagent, across all user-owned projects that have a git repository with a remote. It adds to every other rule; by the user's ruling of 2026-11-25 it also replaces the executors' blanket "no push" for private repositories the user owns (see "Interaction with other regulations").

The quotation above is the rule. The sections below say how sessions apply it. Where they seem to differ from the quotation, the quotation wins, and in any doubt the session asks the user.

## What it requires

1. **Push regularly:** push to the remote at every meaningful milestone, completed step/handover, or whenever a blocker stops progress. Do not let progress or blocker state sit only in local commits, uncommitted files, or local chat transcripts.
2. **Supervisor-reviewable solely from the repo:** a supervisor reading *only* the remote git repository (without terminal logs, chat history, or local machine access) must be able to determine:
   - **Progress:** what is done, what changed, and what was verified (with exact commands/counts/receipts where applicable).
   - **Blockers:** what is blocked, why (exact error, missing dependency, or decision needed), and what unblocks it.
   - **Next step:** what happens next once unblocked or after the milestone.
3. **Two places to record it:**
   - **Descriptive commit messages:** explain the milestone, outcome, and any open blockers clearly (never bare `wip`, `update`, or `fix`).
   - **Up-to-date in-repo progress/plan/status files:** keep the project's status, plan, or ledger file (for example `plan/PLAN.md`, `PROGRESS.md`, or the project's status/ledger doc) current in the same commit/push.

## Interaction with other regulations

This rule adds to existing regulations. One of them changed with the user's ruling of 2026-11-25, the executors' "no push":

- **Others' Repositories Regulation (rule 12):** this push rule applies *only* to repositories the user owns. A repository the user does not own falls under that regulation: never push to, branch, or modify it without the user's direct approval. (Corrected 2026-11-25: the line used to say that the regulation applies only to the user's own repositories.)
- **No data or secrets in git (rule 11):** never commit or push private data, credentials, tokens, or protected inputs. Describe data-dependent blockers in text without leaking protected content.
- **Standing permission for private repositories (the user's ruling, 2026-11-25).** The executor rules used to say "no push unless the user approved it", which left this rule without effect for every handover: the executor committed and waited, and a supervisor still could not review from the remote. The Supreme-Committee session put this to the user with the proposal "for private repositories you own, 'push regularly' is a standing permission; public repositories and the OSS review gate stay ask-each-time", and the user answered "agree all with you, fix as you proposed". So a session pushes to a private repository the user owns at milestones, completed steps and blockers, without asking.
- **Push gates that stay:** a public repository (the user, 2026-07-30: "DO NOT PUSH ANYTHING TO THOSE PUBLIC REPOS OR DOMAINS WITHOUT MY PERMISSION"); the OSS contribution track, where the user reviews a change before any commit or push; and any project, plan or handover that requires the user's yes for each push. There, commit the status/progress update locally and ask the user to approve the push promptly.
- **Private and the user's, or gated:** check the remote (`gh repo view --json isPrivate,owner`, or the host's equivalent). If it cannot be established that the remote is private and the user's, treat the push as gated.

## Paste-in form

For a `CLAUDE.md`, `AGENTS.md`, or the "Rules" of a handover:

```markdown
## Regular remote pushes for supervisor review (set by the user, 2026-11-23)

"all the projects with git repo should push to the remote regularly with descriptions enough for a supervisor to review
the progress and blockers situation from the git repo's contents sorely". For every user-owned project with a git
remote: commit and push regularly (at milestones, completed steps, and whenever blocked) with descriptive commit
messages and up-to-date in-repo status/plan files (progress, verification state, blockers, and next steps) so a
supervisor can review the situation solely from the remote repository. For a private repository the user owns this
is the standing permission to push (the user, 2026-11-25); a public repository, or a project with a push gate,
still needs the user's yes for each push. Never push data/secrets, and never push to repositories the user does not
own without direct approval. Full text: The_Regular_Remote_Push_Rule.md in the AI-management repository.
```

## Where it is in force

- Rule 16 of [`EXECUTOR_RULES_BLOCK.md`](../../regulations/executor-regulations/EXECUTOR_RULES_BLOCK.md) (installed into `~/.gemini/config/AGENTS.md`, `~/.codex/skills/executor-rules/SKILL.md`, and `~/.claude/skills/executor-rules/SKILL.md`).
- The machine rules file of Claude Code on the WSL machine (`~/.claude/CLAUDE.md`, section 8), since 2026-11-25. It was not in that file before, although this document said so.

## Origin

Set by the user on 2026-11-23 in the `AI-management` agy session so a supervisor reviewing any project's remote git repository can assess progress and blockers without needing access to local terminals or agent session logs.

## Check

```bash
grep -rln --exclude='*.bak*' "Regular remote pushes" ~/.claude/CLAUDE.md ~/.gemini/config ~/.codex/skills ~/.claude/skills 2>/dev/null
```
