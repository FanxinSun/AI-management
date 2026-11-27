# omni — Lightweight Multi-Agent Poe-Style CLI: the plan

**Status:** A-0 to A-6 pending. Wave 1 is A-0 to A-3, Wave 2 is A-4 to A-6.
**Canonical:** `plan/PLAN.md` of the project `general/tools/omni/` (this file), with one file per execution step under
`plan/subplan_A/` and `plan/subplan_A/subplan_A-<n>/`, laid out by The Project Planning Rule
(`general/rules/project-planning/The_Project_Planning_Rule.md`). The project has a single outcome, so it has one plan
and one execution order: section 2, A-0 to A-6. There is no other plan document.
**Replaces** the first draft `PLAN.md` at the project root (2026-11-26, before the planning rule was read), whose scope,
hard limits, command contracts and acceptance criteria are all kept below. Step names moved as follows:
O-0 is now A-0, O-1 is A-1, O-2 is A-2, O-3 is A-4, O-4 is A-5, O-5 is A-6; A-3 is new (a stop point and audit after
Wave 1, so that the riskiest foundation is checked before the rest is built on it).
**Paths** in this plan and its step files are relative to `general/tools/omni/`, unless they start with `$HOME` or
`${OMNI_HOME}`.
**Who changes this plan:** the planner session (`AI CLI Committee`). Executors read it and never edit anything under
`plan/` except an exact insert the planner gives them. Their logs, reports and watermarks live outside `plan/`, in files
whose names do not carry the word plan.

## 1. Scope and hard limits

`omni` is one lightweight command-line tool and scrollback REPL that puts `claude`, `agy` and `codex` (plus optional
OpenAI-compatible and Anthropic HTTP endpoints) into a single shared conversation, in the style of poe.com:

- several accounts stay logged in at once, even several of the same CLI;
- the active agent can be switched in the middle of a thread (`@handle`, `/switch`);
- `/compare` asks another agent the same prompt and shows its answer under a quoted copy of the prompt;
- after every reply a shortcut bar offers `Compare` chips for the other agents;
- `/summarize` makes one agent merge all answers into consensus, differences, unique insights and a verdict.

Decided by the user, 2026-11-26 (plain text): the tool lives in this repository under `general/tools/omni/`; the UI is
lightweight (scrollback REPL, not a full-screen TUI); no extra agent CLIs in v1 beyond `claude`, `agy`, `codex` and the
HTTP adapter; the planner session orders the work and chooses the executors.

Hard limits, for every step:

1. The repository is public. Executors commit locally and never push without the user's yes for that push.
2. No tracked file under `general/tools/omni/` may contain an absolute home path, an e-mail address, an account id, a
   token or any credential. Everything per-user lives under `${OMNI_HOME:-$HOME/.local/share/omni}` (directories mode
   `0700`, files mode `0600`).
3. `omni` never writes to `$HOME/.claude`, `$HOME/.codex` or `$HOME/.gemini`. A default-account handle only points at
   them. Per-turn model changes are passed as command-line flags, never saved into another tool's settings.
4. Prompts reach every child process through stdin, never through argv and never through terminal keystrokes.
5. Python 3 standard library only, plus optional `rich` for rendering (plain-text fallback when it is missing). Never
   hardcode a Python minor version; use `site.getusersitepackages()` or `sysconfig`. Number lines with `split('\n')`,
   never `splitlines()`. Files that another step reads are written as `<name>.partial` and then `os.replace`d.

## 2. The execution order

1. **A-0** (pending): host stream-schema probe and sanitized fixtures → [`subplan_A/A-0.md`](subplan_A/A-0.md)
2. **A-1** (pending): multi-account profile vault, `omni/vault.py` → [`subplan_A/A-1.md`](subplan_A/A-1.md)
   - A-1-0: vault layout, `0700`/`0600` guards, atomic JSON store → [`subplan_A/subplan_A-1/A-1-0.md`](subplan_A/subplan_A-1/A-1-0.md)
   - A-1-1: `import-default`, isolated `login`, `list`/`status`/`remove`, cooldown mark → [`subplan_A/subplan_A-1/A-1-1.md`](subplan_A/subplan_A-1/A-1-1.md)
3. **A-2** (pending): normalized streaming adapters, `omni/adapters/` → [`subplan_A/A-2.md`](subplan_A/A-2.md)
   - A-2-0: `StreamEvent`, `AgentAdapter`, stdin subprocess harness → [`subplan_A/subplan_A-2/A-2-0.md`](subplan_A/subplan_A-2/A-2-0.md)
   - A-2-1: `agy` and `codex` adapters → [`subplan_A/subplan_A-2/A-2-1.md`](subplan_A/subplan_A-2/A-2-1.md)
   - A-2-2: `claude` adapter and verified-TLS HTTP adapter → [`subplan_A/subplan_A-2/A-2-2.md`](subplan_A/subplan_A-2/A-2-2.md)
4. **A-3** (pending): Checkpoint 1, a cross-vendor audit of A-0 to A-2 → [`subplan_A/A-3.md`](subplan_A/A-3.md)
5. **A-4** (pending): turn DAG, transcript ledger and cross-agent context → [`subplan_A/A-4.md`](subplan_A/A-4.md)
   - A-4-0: SQLite store and append-only transcript, `omni/store.py` → [`subplan_A/subplan_A-4/A-4-0.md`](subplan_A/subplan_A-4/A-4-0.md)
   - A-4-1: history chain, blind versus `--with-prev` compare, delta sync, `omni/context.py` → [`subplan_A/subplan_A-4/A-4-1.md`](subplan_A/subplan_A-4/A-4-1.md)
6. **A-5** (pending): compare and summarize engine, REPL, CLI and installer → [`subplan_A/A-5.md`](subplan_A/A-5.md)
   - A-5-0: parallel compare and four-section synthesis, `omni/compare.py` → [`subplan_A/subplan_A-5/A-5-0.md`](subplan_A/subplan_A-5/A-5-0.md)
   - A-5-1: scrollback REPL, `omni/repl.py` → [`subplan_A/subplan_A-5/A-5-1.md`](subplan_A/subplan_A-5/A-5-1.md)
   - A-5-2: one-shot CLI, launcher, installer, README → [`subplan_A/subplan_A-5/A-5-2.md`](subplan_A/subplan_A-5/A-5-2.md)
7. **A-6** (pending): Checkpoint 2, the final cross-vendor audit and release gate → [`subplan_A/A-6.md`](subplan_A/A-6.md)

Executors: `omni-tree` (agy, `gemini-4-hydrogen-high`) is the only writer of the tool's files and carries out A-0 to A-2
(order TREE-01) and A-4 to A-5 (order TREE-02). `omni-audit` (codex, `gpt-6.2-sol` at medium effort) carries out A-3
(order AUDIT-01) and A-6 (order AUDIT-02), read-only, from a `git archive` snapshot. The orders are untracked files in
`.omni-work/orders/`.

## 3. Producer to consumer map

| Produced by | Artifact or type | Consumed by |
|---|---|---|
| A-0 | `tests/fixtures/{claude,agy,codex}_stream.jsonl` | A-2-1, A-2-2 (adapter parsers and their tests) |
| A-1-0 | `ProfileSpec`, `${OMNI_HOME}/accounts.json` | A-1-1, A-2 (`get_adapter(profile)`), A-5 |
| A-1-1 | child `env` dict per profile, cooldown mark | A-2 (subprocess environment), A-5 (`accounts` output) |
| A-2-0 | `StreamEvent`, `RunOptions`, `AgentAdapter` | A-2-1, A-2-2, A-4, A-5 |
| A-2 | `get_adapter(profile).run(prompt, opts)` | A-5-0 (compare, summarize) |
| A-4-0 | `Store`, turn rows, transcript file | A-4-1, A-5 |
| A-4-1 | `build_prompt_packet(...)` | A-5-0, A-5-1 |
| A-5-0 | `run_compare`, `run_summarize` | A-5-1, A-5-2 |
| A-2 and A-5 | `git archive` snapshots | A-3 and A-6 (audits) |

## 4. Acceptance criteria

- `omni ask`, `omni compare` and `omni summarize` work live against `claude`, `agy` and `codex`.
- Two profiles of the same provider can be logged in at the same time, and the default accounts are untouched.
- The sha256 of `$HOME/.claude/settings.json`, `$HOME/.codex/config.toml` and
  `$HOME/.gemini/antigravity-cli/settings.json` is identical before and after every test run.
- `check_spec.py --strict` and `check_spec.py --plan-layout` report nothing over the tool's tree.
- Each unit-test file fails first and then passes, with both runs saved.
- Pushing to the public remote happens only after the user says yes to that push.
