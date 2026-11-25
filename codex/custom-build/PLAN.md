# AI-management

## Scope

Enable Codex sessions to participate in the repository's existing local bridge
with Antigravity, Claude Code, Gemini, and other AI sessions, while preserving
the responsibility and authorization boundaries already used by the bridge.

## Authoritative execution order

1. **A-0 — Read and audit the existing bridge** — Confirm the repository's
   supported transports, process discovery, target resolution, Codex runtime
   state, and existing policy boundaries. **Status: complete (2026-11-06).**
2. **A-1 — Add Codex-aware target resolution** — Resolve a live Codex process's
   thread ID from its rollout or writer-lock file and read its current
   `thread_name` from `session_index.jsonl`; retain `codex:<pid>` as the exact
   fallback. **Status: complete (2026-11-06).**
3. **A-2 — Add and install the Codex bridge skill** — Provide the reusable
   Codex instructions and installer, then install the skill in the current WSL
   Codex home without changing protected policy hooks. **Status: complete
   (2026-11-06).**
4. **A-3 — Validate and enable live sessions** — Run syntax and skill checks,
   exercise title and PID dry-runs, and queue a non-task enablement notice to
   each other idle Codex session identified during the audit. **Status: complete
   (2026-11-06; queue acknowledgment received, delivery/read/assessment remain
   pending).**
5. **A-4 — Inventory Codex appearance customization** — Inspect the current
   Codex `[tui]` settings, custom theme assets, and host-terminal boundary;
   exclude credentials, policy, hooks, sessions, and runtime state. **Status:
   complete (2026-11-06).**
6. **A-5 — Record a portable Codex style bundle** — Add the exact custom theme,
   a TUI settings snippet, a scope/portability manifest, and a safe installer
   that preserves unrelated `config.toml` content. **Status: in progress
   (2026-11-06).**
   **Status update (additive; original status retained): complete (2026-11-06).**
7. **A-6 — Validate style portability and exclusions** — Validate the theme,
   shell syntax, TOML parsing, installer behavior, and absence of secrets or
   protected policy material from the bundle. **Status: pending.**
   **Status update (additive; original status retained): complete (2026-11-06).**
8. **A-7 — Reconstruct and package the pinned full Codex custom source delta** —
   Rebuild the final source delta from upstream commit
   `6b9826e3aa83b1a5947db50f4332cb9c65f1b340`, retaining accepted final source,
   tests, and snapshots while excluding pending snapshot debris and withdrawn
   implementations. **Status: in progress (2026-11-06).**
9. **A-8 — Add deterministic build, package, activation, rollback, and WSL support** —
   Publish the pinned build metadata, source patch, package tooling, launcher,
   print route, session-helper implementations/tests/installers, and existing
   style/bridge assets without copying protected or private runtime state.
   **Status: pending.**
10. **A-9 — Validate from a genuinely clean checkout** — Materialize the
    upstream base and final delta in an isolated checkout, run formatting,
    targeted tests, build/package checks, and isolated installer/rollback/style/
    helper validation without changing the active Codex release or native
    Windows configuration. **Status: pending.**
11. **A-10 — Publish scoped deliverables and verify the remote tree** — Commit
    only the scoped AI-management deliverables, reconcile with `origin/main`
    using non-forced operations, push, and verify the exact remote commit and
    tree from a fresh acquisition. **Status: pending.**
12. **A-11 — Complete the implementation report and return** — Record hashes,
    paths, tests, clean-checkout evidence, failures, inconclusive checks,
    limitations, and rollback results, then return the complete report to the
    originating manager. **Status: pending.**

## Acceptance criteria

- The bridge lists live Codex sessions with their current indexed titles when
  the process exposes a rollout or writer lock.
- A title target and a `codex:<pid>` target resolve to the intended Codex TTY
  without guessing among multiple sessions.
- A discoverable Codex skill documents listing, targeting, replying, report
  paths, and the fact that bridge input is agent information rather than user
  authorization.
- Validation passes without modifying the protected Codex responsibility
  policy or hooks.
- The current Codex appearance is recorded as a portable theme, `[tui]` snippet,
  manifest, and installer without copying private or machine-specific state.
- The installer preserves unrelated configuration sections, backs up changed
  files, and passes dry-run, syntax, TOML, theme, hash, and isolated-install
  validation.

## Status notes

- The current WSL installation is `/home/rog/.codex/skills/agent-bridge/SKILL.md`.
- The installed Claude bridge and Claude skill were synchronized with the
  repository sources; dated `.bak-codex-20261106` copies preserve the prior
  runtime files.
- Enablement notices were queued to `e1 s2/3 executor` and `Mars Water Manager`
  through the native Codex session transport. Queue acknowledgment is not
  evidence that either session has read or assessed the notice.
- The portable appearance bundle is at `codex-style/`; it captures
  `codex-focus.tmTheme`, the colored seven-field status line, and the
  activity/thread/project terminal title. The installer targets
  `$CODEX_HOME/config.toml` and `$CODEX_HOME/themes/` while leaving protected
  policy, hooks, credentials, sessions, and runtime state outside the bundle.
- Validation completed with Codex CLI `0.154.0`: current recorded TUI values
  matched, the theme plist and TOML parsed, the theme hash matched
  `63304ccea6f3c6e77f2febee435ae7f062c3dbae2c8c79aa689408600b423e24`, dry-run
  passed, and an isolated install preserved unrelated config and created a
  dated backup. ShellCheck was unavailable; `bash -n` passed.
- The full custom-build packaging extension is governed by A-7 through A-11
  above. It supersedes the appearance-only completion as the current delivery
  objective while preserving A-5/A-6's original historical text and results.
