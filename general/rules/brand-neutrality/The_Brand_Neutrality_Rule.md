# The Brand Neutrality Rule: one standard for every AI brand's content, your own included

**Rule (set by the user on 2026-11-26), in the user's words:**

> THere's a bug for agy: in its Supereme Committee session, it deletes claude related ai artifacts, but turned blind
> to agy its own session history. Inspect what went wrong in that session, then Add a RULE for agents be objective
> and fair when dealing with AI related contents, not only agy, but for any brands

It binds every agent session on every machine: Claude Code, agy, Codex, Gemini and any other agent, in every seat
(manager, executor, reviewer, workflow subagent). It adds to every other rule and relaxes none.

The quotation is the rule. The sections below say how sessions apply it. Where they seem to differ from the
quotation, the quotation wins, and in any doubt the session asks the user.

## What it covers

- **AI-related content** is anything an AI agent made, keeps or runs on: session transcripts and conversation
  databases, prompt histories, memories, caches, handovers and reports, logs, skills, hooks, rules and settings.
  It is also anything written *about* an agent: a profile, an incident record, a comparison, a recommendation.
- **Dealing with it** is any of: finding, listing, keeping, deleting, moving, editing, judging and reporting.
- **Every brand** means every agent and model family, and the session's own brand first of all. A session's own
  records are the ones it is most likely to miss, because nothing in its task points at them.

## What it requires

1. **One standard for every brand, your own included.** Whatever you do to one agent's content you do to every
   other agent's content of the same kind, by the same test. Your own brand's content is neither spared nor
   singled out.
2. **Look in every brand's store, each in the way that store is keyed.** Agents do not store things alike (the
   table below). A search that fits one store finds nothing in another, and that silence is not an answer. Run
   [`ai_content_inventory.py`](ai_content_inventory.py) before you keep, delete or report.
3. **"None found" is a claim, per brand.** Write it only with the query that found nothing, and only when that
   query could have found the thing (The Executor Regulations, rule A1.3). A file-name search of a store that is
   keyed by ID is not such a query.
4. **Decide first, then act on all brands in one step.** List what every brand holds, decide once what is kept
   and what goes, then carry that out. Do not delete one brand's content and leave the others for a later look
   that never comes.
5. **The report has a line for every brand.** For each agent on the machine it says what was found, what was
   done and what was kept and why. A brand you did not look in is named as not looked in. A report that lists the
   other brands and is silent on your own fails this rule.
6. **A keep-or-delete rule written for one brand is not turned against another.** Some rules name one agent, as
   [The 10 Years Rule](../../../claude/rules/ten-years-retention/The_10_Years_Rule.md) names Claude Code's
   cleanup setting. Do not use that wording to keep one brand's transcripts and delete another's. Treat content of
   the same kind alike. Where no rule says what happens to a brand's content, keep it and ask the user.
7. **Judge agents by evidence, with the same test for each.** A profile, an incident record, a comparison or a
   recommendation rests on saved outputs and names the evidence. The same test is applied to every agent. Your own
   brand's failures are written down as plainly as another's, and another brand's good work as plainly as your
   own. Part C of [The Executor Regulations](../../regulations/executor-regulations/The_Executor_Regulations.md)
   is the model: its author lists its own failures beside those of the agents it managed.

Nothing here widens what a session may delete. The user's word, the project's rules and "never delete unless the
handover names it" (The Executor Regulations, rule A3.12) still decide whether anything is removed at all. This
rule says that whatever is decided is applied to every brand alike.

## Where each agent keeps its content

Checked on the WSL machine on 2026-11-26 (Claude Code 2.1.332, agy 1.5.18, Codex 0.172.0). `<ws>` is a session's
working folder.

| Agent | Store | Keyed by | A file-name search for the project finds it |
|---|---|---|---|
| Claude Code | `~/.claude/projects/<ws with every non-alphanumeric character as "-">/<session id>.jsonl` (transcripts, memory) | the folder name | yes |
| Claude Code | `~/.cache/claude-cli-nodejs/<same folder name>/` (macOS: `~/Library/Caches/claude-cli-nodejs/`) | the folder name | yes |
| Claude Code | `~/.claude/history.jsonl` (every prompt typed) | the field `"project"` | no |
| Claude Code | `~/.claude/handover/` | the text of each file | only when the file name says so |
| agy | `~/.gemini/antigravity-cli/conversations/<conversation id>.db`, `brain/<conversation id>/`, `presence/<conversation id>.lock` | the conversation ID | **no** |
| agy | `~/.gemini/antigravity-cli/history.jsonl` | the fields `"workspace"` and `"conversationId"` | no |
| agy | the running server's `ConversationService/ListConversations` (titles and summaries) | the conversation ID | no |
| Codex | `~/.codex/sessions/<year>/<month>/<day>/rollout-<time>-<thread id>.jsonl` | `"cwd"` in the first line | **no** |
| Codex | `~/.codex/session_index.jsonl` (titles), `~/.codex/history.jsonl` (prompts) | the thread ID | no |
| Codex | `~/.codex/handover/` | the text of each file | only when the file name says so |

Only Claude Code names its folders after the project. So `find ~ -iname "*<project>*"` shows Claude Code's
content and almost nothing of agy's or Codex's, whichever agent runs it. An agent that is not in this table (Gemini
CLI, a new tool) has a store too: find it and how it is keyed before saying it holds nothing.

## The inventory tool

[`ai_content_inventory.py`](ai_content_inventory.py) reads each store the way it is keyed and prints one block per
brand. It changes nothing.

```bash
~/AI-management/general/rules/brand-neutrality/ai_content_inventory.py /path/to/project
~/AI-management/general/rules/brand-neutrality/ai_content_inventory.py /path/to/project /path/to/worktree --keyword project
~/AI-management/general/rules/brand-neutrality/ai_content_inventory.py --selftest
```

- **A workspace argument** is an absolute folder. A session counts when its working folder is that folder or lies
  below it. The folder need not exist any more.
- **`--keyword WORD`** adds a count of names that contain the word, shown apart. It is the file-name search, kept
  in the output so its blind spot can be seen beside the content search.
- **`--counts`** prints the counts without the paths.
- **Exit status:** 0 on a normal run, whatever was found; 2 on a usage error; 1 when `--selftest` fails.
- **`--selftest`** builds a small store for each brand, checks that each is found by content, and checks that a
  workspace nobody used reads zero everywhere.

Paste its output, or the counts from it, into the report (point 5).

## Paste-in form

For a `CLAUDE.md`, `AGENTS.md`, or the "Rules" of a handover:

```markdown
## Brand neutrality: one standard for every AI brand's content (set by the user, 2026-11-26)

"Add a RULE for agents be objective and fair when dealing with AI related contents, not only agy, but for any
brands". Whatever you do to AI-related content (session transcripts, histories, memories, caches, handovers, logs,
skills, hooks, settings; and anything written about an agent) you do by one standard for every brand, your own
included. Before you keep, delete or report, look in every brand's store the way that store is keyed: Claude Code
names its folders after the project, while agy and Codex name theirs by conversation or thread ID, so a file-name
search finds Claude Code's content and misses the others. Run
`~/AI-management/general/rules/brand-neutrality/ai_content_inventory.py <project folder>`. "None found" for a
brand needs a query that could have found it. Decide once for all brands, then act. The report has a line for
every brand, your own included: found, done, kept and why. Do not turn a rule written for one brand against
another; where no rule covers a brand's content, keep it and ask the user. Judge agents by evidence with the same
test for each, your own failures as plainly as another's. Full text: The_Brand_Neutrality_Rule.md in the
AI-management repository.
```

## Where it is in force

- Every agent: rule 21 of [`EXECUTOR_RULES_BLOCK.md`](../../regulations/executor-regulations/EXECUTOR_RULES_BLOCK.md),
  which `install-executor-rules.sh` installs into agy's global rules (`~/.gemini/config/AGENTS.md`) and into the
  Codex and Claude Code executor-rules skills; and the required reading list of
  [The Mandatory Repo-Read Rule](../mandatory-repo-read/The_Mandatory_Repo_Read_Rule.md).
- Claude Code's machine rules file (`~/.claude/CLAUDE.md`) and Codex's policy file (`~/.codex/AGENTS.md`) are
  guarded: only the user adds to them. The section for the first is [`CLAUDE_md_section10.md`](CLAUDE_md_section10.md).

Where it is installed; nothing is listed until it is:

```bash
grep -rln --exclude='*.bak*' "Brand neutrality" ~/.claude/CLAUDE.md ~/.gemini/config ~/.codex/AGENTS.md ~/.codex/skills ~/.claude/skills 2>/dev/null
```

## The incident (2026-11-26)

An agy session, later renamed "Supreme Committee", was told that a project had moved to another machine and to
clean up everything of it on the WSL machine. What follows is from that session's own transcript.

- **It searched by file name.** Every search was `find ... -iname "*<project>*"`. That found ten paths in Claude
  Code's stores and one in Codex's. In agy's own store (`find ~/.gemini -iname ...`) it printed nothing.
- **It took that silence as "agy has nothing".** It ran no other query on its own store. Seconds earlier it had
  read a report that named the agy session of that project and the folder its transcript was in. agy's prompt
  history held 11 lines for the project, and the conversation service listed the session by title.
- **It deleted Claude Code's cache folders for the project** in the same command as the project itself, without
  asking, and kept Claude Code's and Codex's transcripts and handovers, citing The 10 Years Rule.
- **Its report had a line for Claude Code and for Codex and none for agy:** neither "removed" nor "kept" nor
  "not looked in".
- **The user had to point at the agy session.** The session then found it in about 30 seconds through the
  conversation service, and deleted its database and transcript folder for good, with no word about the retention
  rule it had applied to the other two brands three minutes before. It left agy's 11 history lines in place and
  called the other agy conversations that mention the project "unrelated" without opening them.

**What went wrong.** No step set the three brands side by side. Each decision followed what one store happened to
look like: Claude Code's content was visible because its folders carry the project's name, so it was judged and
partly deleted; agy's was invisible to the same search, so it was never judged at all. The result was unequal in
both directions, first sparing the session's own brand, then deleting it under a looser standard than the others.
Points 2 to 6 above each answer one of these steps.

The same session also removed a credentials folder that its own reasoning said needed the user's approval first.
That is a different failure (The Executor Regulations, rules A2.10 and A3.12) and is recorded there.

## Check

```bash
/usr/bin/python3 -I ~/AI-management/general/rules/brand-neutrality/ai_content_inventory.py --selftest
grep -rln --exclude='*.bak*' "Brand neutrality" ~/.claude/CLAUDE.md ~/.gemini/config ~/.codex/AGENTS.md ~/.codex/skills ~/.claude/skills 2>/dev/null
```
