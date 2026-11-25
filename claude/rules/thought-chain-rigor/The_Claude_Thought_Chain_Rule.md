# The Claude Thought-Chain & Guardrail Rule

**Set on 2026-11-24** after diagnosing four defect classes across **e1 Committee** (`claude:3008`), **Papers Supervisor** (`claude:12906`), and **e1 executor** (`claude:3693`) during E1 Step 5a.

**Revised on 2026-11-25** at the user's word, after a review by the Supreme-Committee session: T3 and T4 say where their E1-specific items apply, T4 covers every distribution, the switches that bypass a guard are the user's (T1), and the write-time hygiene hook refuses only what an edit adds.

This rule strengthens Claude Code sessions — whether sitting in the **Manager / Committee**, **Supervisor / Reviewer**, **Executor**, or **subagent** seat — against premature shortcuts, unverified environment/consumer assumptions, broken cross-step contracts, and silent numerical tail bugs.

---

## 1. The Five Mandatory Thought-Chain Habits

### T1. Plain-Text Approvals & Provenance Audit (Never TUI Picker Dialogs)
- **Why:** On 2026-11-24 (`D89`/`D90`), `e1 Committee` opened an interactive `AskUserQuestion` selector dialog twice (`16:06:56` and `16:11:09`). Incoming `send_to_tty.sh` Enter keystrokes from `Papers Supervisor` and `codex:374060` auto-selected `"Approve, cap 9,000 s (Recommended)"` and `"Hold, not yet"`, triggering premature execution under false user approval.
- **Rule:**
  1. Never invoke `AskUserQuestion` (or any TUI selector picker) for user approvals, compute caps, pushes, or unblinding. Ask the user in plain text at the end of your turn.
  2. Before recording or relaying any approval in a plan or handover, verify in the originating session's transcript (`~/.claude/projects/*/<sessionId>.jsonl`) and `~/.claude/agy-bridge/send.log` that the answer is plain user text — no `[from ...]` prefix, no `AskUserQuestion` `tool_result`, and no bridge send into that TTY within ±5 s. Quote the exact timestamp and text.
  3. The Claude guardrail hook (`ai-management-claude-guardrails.sh`) mechanically denies `AskUserQuestion`, and `send_to_tty.sh` inspects both Claude's JSONL transcript and WSL/macOS/tmux console buffers before typing.
  4. The switches that bypass these guards (`AI_MGMT_ALLOW_ASK_DIALOG=1`, `BRIDGE_FORCE_SEND=1`, `BRIDGE_FORCE_DISPATCH=1`, and `AI_MGMT_RULES_GATE_OFF=1` for the rules gate) are the user's. No agent sets one without the user's word in its own session. A bridge send that is refused is reported, not forced: the rule that an executor must report back through the bridge is never a reason to type into an open dialog (added 2026-11-25).

### T2. Consumer-First & Binary-First Verification Chain (Never Assume Compatibility)
- **Why:** `REPLY.md` §3.2 claimed reusing `step2_analysis.cc`'s open `.vars` writer enabled `plots_5_5.py` / `numbers_5_5.py` to read first-look rows (false: they hardcode `open_*.txt` and `'OPEN '`) and enabled K7's EM-veto variants (false: `MAX_EM_FRAC` omits per-jet $E_{\text{EM}}$); §3.5 implied `~/sw` provided `scipy` (`~/sw/rivet-4.1.3/bin/python3` lacks `scipy`, only `/usr/bin/python3` has it); and `5a-1` checked against `sim_diag` without reading lines 308/618–621 (`sim_diag` prints `MISMATCH` for all `in_U` events).
- **Rule:** Before stating in any plan, review, or handover that Script B reads Output A, that Columns X compute Metric Y, or that Runtime Z has Library L:
  1. **Open Script B** and check its exact file glob, line-prefix filter, and column parser.
  2. **Write the algebraic formula for Y** and map every symbol to an exact column name present in X.
  3. **Run `<exact_python_binary> -c "import ..."`** before naming an interpreter path.

### T3. Concrete Interface Contracts & Cross-Step Consistency Matrix (No Meta-Prose)
- **Why:** Writing `"The command-line contract is exact"` without flags (`5a-1.md`) blocked Codex (`5a-1`); pinning `runs_1998_188.6.tsv` inside the production router without specifying the synthetic test gate broke `5a-4`'s original rehearsal plan (`D92 (d)`); `5a-2` computed `B_err` while `5a-3` and `first_look_stats.py` dropped `B_err` completely; and `5a-6` added `--sim` across three rounds (`D94`–`D95`).
- **Rule:**
  1. Never write placeholder prose (`"contract is exact"`, `"standard options"`). Specify every literal `--flag`, path pattern, `key=value` schema and exit code. Where a step writes files that another step reads, also specify the `.partial` staging + atomic rename behavior and the canonical SHA-256 pins. What a blinded analysis must not print (E1's stdout digit-suppression rule) belongs in that project's plan. Scope stated 2026-11-25: staging, pins and print rules are not asked of a step that has none, and an executor that applies a digit-suppression rule to a script whose job is to print numbers breaks that script.
  2. When decomposing a workflow (`step-1 .. step-N`), trace every produced quantity (`B_err`, `--sim` paths, `sigma_band`, reach artifacts) through an explicit **Producer $\to$ Consumer** check, and design test/rehearsal modes so canonical production pins never conflict with synthetic harnesses.
  3. Run `~/AI-management/general/tools/handover-lint/check_spec.py` on new/revised sub-plans, handovers, and scripts before dispatching.

### T4. Numerical, Statistical & Path Portability Hygiene
- **Why:**
  - `1 - stats.norm.cdf((q - qa) / (2 * sqa))` rounded to `0.0` in IEEE-754 float64 at $z \ge 8.2924$, crashing `limit()` / `upper_limit()` in `reach.py` v2 and `first_look_stats.py` for **all** $n \in \{0,\dots,37\}$.
  - Hardcoded bounds (`bounds=(-5, 20)` / `[-5, 60]`) silently clamped $\hat\mu$ on large excesses (`D92 (d)`) and deficits, corrupting curvature `sigma_mu`.
  - Self-tests checked only `q0(0, ...)` without calling `limit(0, ...)`, `mu_hat`, or `sigma_mu` across extreme regimes.
  - Hardcoded `.local/lib/python3.14/site-packages` broke 10-year portability; `reach.py` v1 mixed `smear=ON` and `smear=OFF` across offset comparisons; and §3.5 confused exact-Poisson `3.00` with asymptotic CCGV `1.9207`.
- **Rule:**
  1. Never compute an upper tail as `1 - cdf(x)`, for any distribution: not `1 - stats.norm.cdf(x)`, not `1 - ndtr(x)`, not `1 - stats.chi2.cdf(q, 1)` (exactly `0.0` from $q = 70.1$). Always use the survival function, `stats.norm.sf(x)` or `dist.sf(x)` (or `scipy.special.log_ndtr`, `dist.logsf`). The loss starts well before the exact zero: `1 - stats.norm.cdf(z)` is already 7% off at $z = 8$ (widened 2026-11-25).
  2. Never silently clamp MLE/profile bounds; expand search brackets adaptively until extrema or sign changes are strictly bracketed, and report `ValueError`/boundary status cleanly.
  3. Self-test **every** exported statistic at the edges of its range and far outside the expected one, not only at the nominal point. For a counting statistic (`q0`, `z_signed`, `mu_hat`, `sigma_mu`, `upper_limit`, `expected`) that means all four regimes: `n = 0`, deep deficit (`n << B`), nominal (`n ≈ B`), and large excess (`n = 100 * B`). Scope stated 2026-11-25: the four-regime grid is for counting statistics; another statistic is tested at the edges that it has.
  4. Never hardcode Python minor versions (`python3.14`); use `site.getusersitepackages()` or `sysconfig`.
  5. Keep counterfactual/sensitivity tables strictly *ceteris paribus* (vary one truth parameter per comparison) and match exact-vs-asymptotic reference targets to the formula actually implemented.

### T5. Supervisor Seat Boundaries & Header-Addendum Reconciliation
- **Why:** While `REPLY.md` line 8 asserted *"ran one calculation of my own that reads no E1 file"*, `Papers Supervisor` compiled and executed `sigcheck.cc` over 24 E1 simulation `.dump` files (`35,987` events) outside E1's compute logger, violating both its read-only header claim and the Manager/Supervisor vs Executor seat split (`The_Executor_Regulations.md` Part B & Rule 7).
- **Rule:**
  1. A Supervisor or Reviewer session under a read-only/independent brief may run pure mathematical scripts with zero project-file reads, but must hand C++ builds or multi-file runs over project `.dump`/data files to the project's logged Executor route.
  2. Whenever appending an `Addendum` or `Erratum`, update/annotate any superseded statement in the top header (`Limits kept`, `What I ran`, `Approved cap`) so no top-of-file summary misleads a reader.

---

## 2. Mechanical Enforcement (`claude-guardrails/`)

Installed via `claude/hooks/claude-guardrails/install-claude-guardrails-hook.sh` (also called by `./install-all.sh`):

1. **`PreToolUse` / `askguard` (`AskUserQuestion`):** Blocks TUI dialog pickers by default to prevent cross-agent keystroke spoofing.
2. **`PreToolUse` / `codehygiene` (`Write|Edit|MultiEdit` on `.py` files):** Refuses an edit that **adds** a `1 - cdf(...)` upper tail (any distribution) or a hardcoded `.local/lib/python3.<N>/site-packages`. Since 2026-11-25 the check is `check_spec.py --hook`: it parses the file as it would be after the edit, so comments and docstrings are ignored (and string literals are ignored for `1 - cdf`, while path literals in code remain checked), a hunk or line that already had the pattern is left alone, and a line marked `# handover-lint: allow` is skipped. The earlier text match refused comments, strings, and any edit to a line containing `1 - norm.cdf(`, and missed the two-line form and every distribution but the normal.
3. **`SessionStart|SubagentStart|UserPromptSubmit` / `thoughtchain`:** Injects the compact T1–T5 checklist, canonical bridge path, and `check_spec.py` reminder into every Claude session and subagent.
4. **Cross-agent bridge dialog guard (`send_to_tty.sh` + `conin_inject.ps1`):** Refuses to send Enter into Claude JSONL sessions with open `AskUserQuestion`/`ExitPlanMode`/`Artifact` calls or visible console picker footers.

See [`CLAUDE_md_section6.md`](CLAUDE_md_section6.md) for the optional paste-in summary for `~/.claude/CLAUDE.md`.
