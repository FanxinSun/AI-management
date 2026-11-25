# The Others' Repositories Regulation: no change to a repository the user does not own

**Regulation (set by the user on 2026-11-17), in the user's words:**

> without User's direct approval, any modification/merge/pull request of repo (or git/repo like resources) not
> belonged to User is strictly prohibited

It binds every agent session on every machine: Claude Code, agy, Codex and Gemini, whether manager, executor or
workflow subagent. It adds to every other rule and relaxes none.

The quotation above is the regulation. The sections below say how sessions apply it. Where they seem to differ from
the quotation, the quotation wins, and in any doubt the session asks the user.

## What it covers

- **Whose resources: anything the user does not own.**
  - Repositories: upstream projects, other people's and organizations' repositories, and forks that belong to
    someone else.
  - Repo-like resources: anything else that holds shared content and takes contributions, such as a project's issue
    tracker, wiki, releases or package registry, a gist, or a model or dataset repository.
  - If it is not certain that the user owns it, treat it as not the user's.
- **Which actions: any change, by any route** (git, a web page, an API, or a CLI such as `gh` or `glab`):
  - pushing anything: commits, branches, tags, force-pushes, deletions;
  - opening, updating, approving, merging or closing a merge request or pull request;
  - merging, and editing through the host's web editor or API;
  - opening an issue, commenting, reviewing or labelling;
  - forking, the first step of a pull request.
- **When unsure whether an action is covered, treat it as covered** and ask.
- **Reading is not covered:** cloning, fetching, `ls-remote`, reading pages. A project may hold back reads as well,
  as `pythia8-clusterjet` does for its upstream project (its `plan/PLAN.md`, D18).
- **The user's own repositories are outside this regulation.** Their own rules still apply, for example "each push
  needs the user's yes".

## What counts as the user's direct approval

- **The user's own yes, for that action.** A manager's or another session's word is not the user's approval.
- **A general permission does not reach it.** "Commit on your calls" or "go ahead with the step" covers no change to
  a resource the user does not own.
- **One approval covers one action.** Approving a draft does not approve sending it. Approving one push does not
  approve the next.
- **An executor** needs the user's words for that action, quoted exactly in its handover. If it is unsure what they
  approve, it asks the user in its own session.

## Paste-in form

For a `CLAUDE.md`, agy's or Codex's standing rules, or the "Rules" of a handover:

```markdown
## Others' repositories (set by the user, 2026-11-17)

"without User's direct approval, any modification/merge/pull request of repo (or git/repo like resources) not
belonged to User is strictly prohibited". This covers any change, by any route, to a repository or repo-like
resource (issue tracker, wiki, releases, registry, gist) that the user does not own: pushes, branches and tags,
merge and pull requests, merges, web or API edits, issues and comments, forks. Reading is not covered. Only the
user's own yes for that one action lifts it; a manager's or another session's word does not. If unsure whether the
user owns it, or whether an action is covered, ask the user. Full text: The_Others_Repositories_Regulation.md in
the AI-management repository.
```

## Where it is in force

Installed on 2026-11-17 as a standing instruction at the user's word: agy's global rules, the Codex and Claude
executor-rules skills, and rule 12 of `general/regulations/executor-regulations/EXECUTOR_RULES_BLOCK.md`. Claude
Code's machine rules file on the WSL machine (`~/.claude/CLAUDE.md`) carries it as section 7 since 2026-11-25; until
then that file did not have it, although this document said so.

## Origin

The user gave it on 2026-11-17 to the Claude Code session "Pythia8 bug Investigator" (project `pythia8-clusterjet`),
which was investigating a suspected defect in an upstream project. Earlier that day, in the same session, the user had
given two narrower instructions, recorded in that project's `plan/PLAN.md` as D17 and D18:

- "no touching other people's repo yet, no pull request"
- "no merge request yet, no actions there without my permissions"

The regulation makes them one standing rule, for every session and every repository the user does not own.

## Check

Where it is installed; nothing is listed until it is. Search for the heading, not the quotation: the quotation is
line-wrapped differently in each copy, so a search for "belonged to User" misses them (on 2026-11-25 it found none).

```bash
grep -rln --exclude='*.bak*' "Others' repositories" ~/.claude/CLAUDE.md ~/.gemini/config ~/.codex/AGENTS.md ~/.codex/skills ~/.claude/skills 2>/dev/null
```
