# Multi-Agent Coordination and Dispatch Rules

> **Scope (stated 2026-11-25).** This gate governs one setup: an agy Manager session and an agy Executor session in
> the same working directory that dispatch to a Claude review session. `send_to_tty.sh` enforces it only when the
> sender is an agy session. It does not govern a Claude Code manager that nudges its own executor; on the WSL
> machine that is section 1 of the machine rules in `~/.claude/CLAUDE.md`.

## 1. Hard Dispatch Gate: Manager and Executor Completion Before Review Dispatch

**Rule Statement:**
> **Only when both the Manager session (`custom-llm-manager`) and the Executor session (`executor`) have finished working (both in `[STOPPED]` idle state), dispatch to the review session (`claude`) is allowed.**

### Detailed Protocol & Invariants:

1. **Strictly Sequential Execution**:
   - Review dispatch to `claude` is prohibited while either the Manager or Executor session is actively running commands, editing files, or running tests.
   - Standard workflow:
     1. **Manager**: Plans, briefs, and delegates specific implementation tasks to the Executor.
     2. **Executor**: Executes implementation, runs verification tests, and returns feedback to Manager.
     3. **Manager**: Audits executor output, runs full test suite & privacy leak scans, updates ledgers, and commits cleanly to git.
     4. **Stop Gate**: Both Manager and Executor finish all active tasks and enter `[STOPPED]` state.
     5. **Review Dispatch**: Only now may a notification or review request be dispatched via `send_to_tty.sh` to `claude`.

2. **Clean Working Tree Requirement**:
   - The git working tree must be completely clean (`git status` clean) with all changes committed and pushed before any review dispatch.

3. **Ledger Integrity**:
   - All decision rows (`D-`) and experiment/verification rows (`E-`) must be appended and committed to the repository before requesting review.
