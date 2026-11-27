# Handover & Statistical Script Pre-Flight Linter (`check_spec.py`)

Added on **2026-11-24** after inspecting multi-agent failures in E1 Step 5a across `e1 Committee` (`claude:3008`), `Papers Supervisor` (`claude:12906`), and `e1 executor` (`claude:3693`).

`check_spec.py` catches four structural and numerical defects **before** a handover, sub-plan, review reply, or statistics script is committed or dispatched:

## What It Checks

### On `.md` documents (handovers, sub-plans, review replies)
1. **`ERROR [META_CONTRACT]`** — Rejects meta-prose placeholders such as `"The command-line contract is exact"` when the document defines zero literal `--flag` CLI options (caught `5a-1.md` blocking `codex:374060`).
2. **`ERROR [RETIRED_PATH]`** — Flags references to removed pre-reorganization `AI-management` paths (`AI-management/agy-bridge/send_to_tty.sh`, `rules-gate/ack-rules.sh`, `executor-rules/...`, `download-ui-template/...`, old `How_to_Control_Other_Agy_Sessions_*.md`) while permitting installed runtime directories like `~/.claude/agy-bridge/` and bare prose labels like `` `rules-gate/` ``. <!-- handover-lint: allow -->
3. **`WARN [APPROVAL_PICKER_PATTERN]`** — Warns on quoted `"(Recommended)"` picker selections in approval records (`D89`/`D90`) or `"Do not ask the user again"` relays lacking an audited timestamp (`HH:MM` / ISO UTC). <!-- handover-lint: allow -->
4. **`WARN [ADDENDUM_HEADER_DRIFT]`** — Warns when a document gains an `## Addendum` / `## Erratum` section while its top header still asserts an unannotated absolute claim such as `"reads no E1 file"` (`REPLY.md` line 8 vs `sigcheck.cc`).
5. **`WARN [HOLD_WITHOUT_USER]`** (added 2026-11-27, planner rule 18) — Warns on a line that holds a session from its work until another session acts (a handover, the Committee, a manager, a nudge) and does not name the user's direct instruction as what lifts the hold. Example: `change no file in tools/ until the Committee's handover`, from the correction notice of 2026-11-27, which an executor then held up against its own user's request. Quotations are not holds: text in backticks or quotation marks, `>` lines and fenced blocks are skipped, and so is a negated wait ("do not wait for the Committee"). On 2026-11-27 it found nothing in this repository's documents, and 13 lines in the older handovers of `~/.claude/handover/`. All 13 are holds that only a manager's word lifts.

### On `.py` scripts
1. **`ERROR [NORM_CDF_TAIL]`** — Rejects `1 - stats.norm.cdf(...)` or `1 - ndtr(...)`, which suffers catastrophic float64 cancellation to `0.0` at $z \ge 8.2924$ (`reach.py` v2 and `first_look_stats.py` crashing `limit()`/`upper_limit()` for $n \in \{0,\dots,37\}$); use `stats.norm.sf(...)`.
   **`ERROR [CDF_TAIL]`** (added 2026-11-25) is the same finding for every other distribution: `1 - stats.chi2.cdf(q, 1)` (exactly `0.0` from $q = 70.1$), `1.0 - norm(0, 1).cdf(z)`, or the two-line form through a temporary. The error is already 7% at $z = 8$. Comments and string literals are never findings.
2. **`ERROR [HARDCODED_PY_MINOR_SITE]`** — Rejects hardcoded `.local/lib/python3.<N>/site-packages` path literals (`first_look_stats.py`), enforcing `site.getusersitepackages()` or `sysconfig` for 10-year portability (`#` comments and docstrings mentioning the pattern are ignored).
3. **`WARN [SPLITLINES_LINE_NUM]`** — Flags `.splitlines()`, which splits on `\x0c` form feeds in PDF text layers instead of `\n` (Executor Rule 9).
4. **`WARN [FIXED_BOUND_MINIMIZE]`** — Flags `minimize_scalar(..., method='bounded', bounds=(const, const))`, which silently clamps MLEs on large excesses/deficits (`D92 (d)` clamping $\hat\mu$ at `60` / `-5`).

### On plan files (added 2026-11-26)
1. **`ERROR [PLAN_LAYOUT]`** — a Markdown file that is a plan file by name (`plan` or `subplan` as a whole word of the name, in any letter case, with words split at `_`, `-` and `.`) but does not sit where [The Project Planning Rule](../../rules/project-planning/The_Project_Planning_Rule.md) puts plan files: one `PLAN.md` per project (at the project root or in `<project>/plan/`, never both), `plan/PLAN_lane<N>.md` beside a root `PLAN.md`, and no plan root below another in the same git repository (a directory with its own `.git` is its own project). `PLAN_v2.md`, `test-plan.md` and a second `PLAN.md` further down are findings; `planning-notes.md` is not a plan file by name. The check reads the path only, so the `handover-lint: allow` marker does not waive it. Files under agent configuration, caches, installed packages and `/tmp` are left alone, unless `--plan-layout` names the path. On 2026-11-26 the verdict was compared with the Claude Code plan-file guard on 43 paths (24 refused, 19 allowed): identical.

## Usage

```bash
# Built-in unit self-test
/usr/bin/python3 -I ~/AI-management/general/tools/handover-lint/check_spec.py --selftest

# Lint handovers, plans, or Python scripts before dispatching
/usr/bin/python3 -I ~/AI-management/general/tools/handover-lint/check_spec.py path/to/handover.md path/to/stats.py
/usr/bin/python3 -I ~/AI-management/general/tools/handover-lint/check_spec.py --strict path/to/plan/

# Check only the plan-file layout: a whole project, or one file path before the file is written
/usr/bin/python3 -I ~/AI-management/general/tools/handover-lint/check_spec.py --plan-layout path/to/project/
/usr/bin/python3 -I ~/AI-management/general/tools/handover-lint/check_spec.py --plan-layout path/to/project/plan/PLAN_lane2.md
```

`--plan-layout` prints each finding as `ERROR [PLAN_LAYOUT] <path>:1: <reason>`, then the line `Checked <N> markdown file(s): <P> plan file(s) by name, <E> not canonical`, and exits 0 when nothing is found and 1 otherwise.

A finding on a line that ends with `handover-lint: allow` (in a comment) is skipped. Use it for a deliberate exception and give the reason on the same line.

## As a write-time hook (`--hook`, added 2026-11-25)

`check_spec.py --hook` reads a Claude Code `PreToolUse` JSON on stdin and exits 10, with one line of reason, when a `Write`, `Edit` or `MultiEdit` of a `.py` file **adds** a `NORM_CDF_TAIL`, `CDF_TAIL` or `HARDCODED_PY_MINOR_SITE` finding. It parses the file as it would be after the edit, so:

- `#` comments and docstrings are ignored (and string literals are ignored for `1 - cdf`, while path literals in code remain checked for `HARDCODED_PY_MINOR_SITE`);
- an edit that only touches a hunk or line which already had the finding is let through (removing an old finding in one function does not excuse adding a new finding elsewhere);
- a line marked `handover-lint: allow` is skipped;
- any doubt (unreadable file, syntax error, an edit that would not apply) lets the edit through.

The Claude guardrails hook (`claude/hooks/claude-guardrails/`) calls it. Before 2026-11-25 that hook matched text: it refused comments, test strings and any edit of a line in an upstream file that already contained `1 - norm.cdf(`, and it missed the two-line form and every other distribution.
