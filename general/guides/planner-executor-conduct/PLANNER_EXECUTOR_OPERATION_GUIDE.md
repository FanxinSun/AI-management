# Planner-Executor Multi-Agent Operation Guide (`committee` + `tree` / `prep` / `runner` / `audit`)

This guide documents the operational regulation and conduct patterns refined while running a multi-agent compiler campaign (`ingot`) across four parallel executor terminals conducted by a single Planner/Manager (`committee`). It complements [`The_Executor_Regulations.md`](../../regulations/executor-regulations/The_Executor_Regulations.md), [`MULTI_AGENT_DISPATCH_RULES.md`](../../rules/multi-agent-dispatch/MULTI_AGENT_DISPATCH_RULES.md), and [`How_to_Control_Agent_Sessions_macOS.md`](../agent-control-macos/How_to_Control_Agent_Sessions_macOS.md).

---

## 1. Architecture & Role Split (`1 Planner + 4 Specialized Executors`)

Splitting execution into **four dedicated roles** eliminates write contention, mixes cheap speed with high-rigor oversight, and lets verification overlap with implementation:

| Seat | Role | Workspace Discipline | Why This Seat Exists Separately |
|---|---|---|---|
| **`committee`** (Planner / Manager) | Architecture, task ordering, quota/model governance, verdicting | Coordinates via written order files + bridge; delegates building, running, and auditing | Keeps context small and strategic; prevents the orchestrator from getting buried in multi-hour test logs or compiler traces. |
| **`tree`** | Source code implementation, unit suites, branch merges, immutable snapshot exports | **Sole writer** to the primary git repository (`~/ingot`) | Single-writer invariant eliminates `git index.lock` races, half-committed tree reads, and conflicting edits. |
| **`prep`** | Targeted evaluation harnesses, refusal triage, mathematical residual verification, next-wave blueprints | Dedicated scratch/eval folder (`~/ingot-corpora/build/P1`), **read-only** against immutable exported snapshots | Keeps harness scripting, triage, and deep `ingotc` blueprint reading off `tree`'s critical path while building implementation specs ready for the next wave. |
| **`runner`** | High-volume end-to-end execution, PCH-cached regression suites, randomized/fuzz parity vs oracle (`MATLAB`) | Dedicated run folder (`~/ingot-corpora/build/R1`), **read-only** against immutable exported snapshots | Runs hundreds/thousands of generated or corpus programs with dual comparators (`compare_l72` + `cx11`) continuously without blocking source development. |
| **`audit`** | Independent forensic verification of commits, transcripts, job logs, SHA-256 hashes, and counts | Dedicated audit folder (`~/ingot-corpora/build/CX`), **read-only** against explicit permitted paths on a **different model vendor** (Codex) | Eliminates single-model blind spots and self-grading bias; reconciles every number directly from raw logs and git objects. |

### The Single-Writer + Immutable-Snapshot Rule

Never let `prep`, `runner`, or `audit` evaluate directly against `tree`'s live git working tree while `tree` is actively committing or switching branches.

- Whenever `tree` reaches a milestone commit `<sha>`, it exports an immutable archive copy (`tip-<sha>` or `tip-full-<sha>` via `git archive`).
- `prep` and `runner` target only that exported directory (building isolated template PCH caches keyed by runtime header SHA-256).
- Even if `tree` moves on to the next task or checks out another branch, in-flight evaluations remain bit-for-bit reproducible.

---

## 2. Conducting the Swarm Effectively

### File-Based Orders + Short Bridge Dispatches

- Write every task assignment to a versioned markdown order file (e.g., `TREE-9-...md`, `P1-23-...md`, `R1-31-...md`, `CX-54-...md`) containing:
  - Target snapshot path, branch/identity rules, single-core (`-j1`) constraint, explicit transcript/log/report paths, concrete pass criteria, and what to report back.
- Send only a concise one-line wake-up via `~/.claude/agy-bridge/send_to_tty.sh <target> "..."` pointing to the order file.
- **Why:** Bridge messages flatten newlines and must stay brief; durable order files survive context compactions, session restarts, and post-pause relocations, and give `audit` an unambiguous spec to verify against.

### Pipelined Milestone Handoffs

Structure waves so **implementation**, **fast verification**, **heavy regression**, and **independent audit** pipeline cleanly:

1. `tree` completes a feature slice on the development branch (`lite-runtime`) and exports `tip-<sha>` **before** merging into downstream/release branches (`full-runtime`).
2. `prep` runs targeted feature suites first (`eval_nextwave.py`, `eval_l73d.py`) — fast feedback in minutes.
3. Only after `prep` confirms expected unlocks and `0` regressions does `tree` merge into `full-runtime` (`TREE-9`) and export `tip-full-<sha>`.
4. Meanwhile, in parallel:
   - `runner` runs `L-7-2` randomized Parity + legacy non-I/O suites (`l16`, `l16b`, `l82b`, `l83`, `l84`) against stable exports.
   - `prep` prepares next-wave file-by-file blueprints (`P1-18` `parse14`, `P1-21` I/O follow-ups, `P1-22` struct inference) and deeper mathematical residual proofs (`P1-24`).
   - `audit` trails one step behind (`CX-48`..`CX-58`), auditing commits, fail-first/pass transcripts, and P1/R1 JSONL logs in parallel.

### Reactive Wakeup & Non-Invasive Progress Inspection

- **Do not poll executors over the bridge.** Every bridge ping interrupts or wakes an active/idle session and consumes turns/quota.
- Use `GIT_OPTIONAL_LOCKS=0 git -C <repo> log --oneline`, `ls -lt <results>/`, and output-file sizes/tails on disk first.
- When an `agy` tab appears stalled for an unusually long time (e.g., >15–20 minutes with no commit or transcript growth), inspect its Terminal.app tab passively via AppleScript using `history of t` (never `contents of t`, which dereferences the tab reference instead of reading text). Only nudge the executor if a subprocess is genuinely stuck (e.g., waiting on stdin or masked exit failure).

---

## 3. Controlling Precision & Preventing Silent Drift

Multi-agent pipelines amplify silent errors unless every stage enforces deterministic checks:

1. **Test-First Transcripts (Fail-First + Pass):**
   - Require `tree` to record both a failing run (non-zero exit, e.g., `taskN-fail-first.txt`) before implementing a feature and a passing run (`exit=0`, `taskN-pass.txt`) afterward, stamped with `commit=$(git rev-parse HEAD)`.
2. **Strict Structural Guards & Sync Drift = 0:**
   - Run automated project guards (`check_no_home_paths.py`, `check_headers`, `check_ref_tolerance`, `check_reachable`, `check_untested`, `check_lite_drift`, forbidden-symbol grep) on every sync. Zero drift and zero hardcoded home paths are hard gates.
3. **Mandatory Append-Only Job Loggers (`JSONL`):**
   - `prep` and `runner` log every compiler `check`, `build`, `compile`, `link`, and `run` invocation to an append-only JSONL ledger (`jobs_p1_*.jsonl` / R1 job log). Reports must derive job counts, non-zero exit counts, and wall-time sums strictly from the JSONL file (Executor Rule 7).
4. **Dual-Comparator Verification & Mathematical Residual Proofs:**
   - Numeric outputs are verified by two independent comparators (`compare_l72` + `cx11`).
   - Do **not** blindly trust raw bitwise/ULP counters when linear algebra decompositions have sign/near-zero ambiguities: in `L-7-3f` (`qr`), `_KEY_U64` reported `~8.7e18` ULPs on `4x3` matrices solely where mathematical zero entries (`±1e-16`) crossed `0.0`. Instead of relaxing ULP cutoffs or guessing, dispatch a dedicated verification order (`P1-24`) computing exact factorization residuals (`max |Q*R - A*P| <= 2.22e-15`), orthogonality (`max |Q'*Q - I| <= 6.66e-16`), and element-wise deltas (`<= 4.16e-15`) to separate benign IEEE zero-crossing from real defects.
5. **Explicit Permitted-Path Sandboxing for `audit`:**
   - When sealed or restricted directories (`chmod 000`) exist anywhere under a parent workspace tree, every `CX-*` order must list the **exact permitted files and subdirectories** explicitly and forbid recursive parent scans (`find ~` / `find ~/corpora`). This guarantees both sandbox/data-boundary compliance and deterministic audit scope.
6. **Cross-Model Independent Audit:**
   - Have `audit` check SHA-256 checksums, non-zero exit classifications (distinguishing check refusals vs expected runtime-error tests like `fo_bad_mode` vs real crashes), git parent chains, unsigned identity compliance, and export archive parity (`diff -r` vs `git archive <sha>`). Every discrepancy caught by `audit` (e.g., `fc_bad_fid` exiting `0` vs `fo_bad_mode` exiting `1` in `CX-55`, or historical vs slice nonzero counts in `CX-56`) is corrected immediately in the record.

---

## 4. Model & Effort Settings Rationale

Selecting model + reasoning effort per seat balances accuracy, throughput, and quota longevity:

| Seat | Model & Effort Used | Why This Setting Works |
|---|---|---|
| **`committee`** | **Plan-Execute Two-Phase** (Planning model + fast Execution model) | Strategic decisions, order architecture, and recovery stay on the planning model, while routine file creation and bridge dispatches execute fast without burning frontier reasoning budget on boilerplate. |
| **`tree`** | **`agy` · `gemini-4-hydrogen-high`** | Modifying multi-file compiler frontends/backends (`sema.py`, `codegen.py`, C++ runtime headers) and resolving three-way merge conflicts safely requires high reasoning accuracy. |
| **`prep`** | **`agy` · `gemini-4-hydrogen-high`** | Writing sound static-analysis blueprints (`P1-7`, `P1-18`, `P1-21`, `P1-22`), debugging subtle `KeyError` / `ParseError` edge cases, and diagnosing numeric residuals require high reasoning accuracy. |
| **`runner`** | **`agy` · `gemini-4-hydrogen-medium`** | Executing established single-core test scripts, managing PCH caches, and collecting dual-comparator ledgers are procedural; `medium` effort cuts quota usage and latency without sacrificing accuracy. |
| **`audit`** | **`codex` · `GPT-6.2-Sol medium`** | Cross-vendor diversity catches correlated blind spots from the Gemini executors/planner, reads raw JSONL/git logs rigorously, and uses **zero Gemini weekly quota** while auditing every single step. |

**Hard Model Cap Rule:** Keep `agy` executors strictly on compliant Hydrogen (`gemini-4-hydrogen-*`) or Sonnet (`claude-sonnet-*`) tiers; never silently upgrade bulk executors onto scarce high-cost tiers (e.g., Argon/Carbon/Neon/Opus).

---

## 5. Adjustments Made During Conduct (Real Campaign Lessons)

During the campaign, several real operational issues required live course corrections:

1. **Quota-Gated Pacing & Batching (`>= 70%` Threshold):**
   - Check `agy -p "/usage"` periodically at milestone boundaries.
   - As Gemini Weekly Limit Remaining approached `70%` (`76% -> 72% -> 70% -> 69%`):
     - First, put `prep` and `audit` into **standby** between `tree` / `runner` milestones instead of launching speculative extra tasks, saving remaining quota strictly for critical-path `TREE-9` (`full-runtime` sync) and `P1-25`/`R1-33` parity verification.
     - Keep `audit` (Codex) busy draining backlog while Gemini executors hold.
     - Once Gemini Weekly dropped to `69%` (`< 70%`), stop all new dispatches, allow only already in-flight final verification jobs (`R1-33`, `TREE-9`) to drain, and cleanly pause.
2. **Post-Pause Relocation & Workspace Convergence (`~/ingot`):**
   - Previously, `prep`, `runner`, and `audit` had been launched inside scratch folders (`build/P1`, `build/R1`, `build/CX`), causing bridge directory listings and future resumes to fragment across folders.
   - At pause, as each executor went idle (`prep`, `audit`, then `runner`), terminate its old process cleanly (`kill -TERM <pid>`), `cd` to the canonical project root (`~/ingot`), and resume using exact `--conversation <id>` / `codex resume <thread_id>` in its original Terminal.app tab (`ttys002`, `ttys003`, `ttys004`).
   - **Codex Directory Prompt Trap:** Resuming Codex from a *different* working directory than the thread's recorded `cwd` opens an interactive `Working directory · resume` picker defaulting/highlighting `4. Always use current directory` rather than immediately accepting text input. Check Codex visually / via `history of t` and send a bare Return to confirm option `4` so the session settles cleanly at `› Ask Codex to do anything` in `~/ingot`.
3. **Environment & Pipeline Bug Recovery:**
   - **Linker `PATH` shadowing (`tree`):** A `full-runtime` run failed `ld` when `miniconda3/bin/python3-config` shadowed Homebrew `python3.13`, and a subshell `echo "exit=$rc"` masked the non-zero return code. **Adjustment:** Always prepend `/usr/local/opt/python@3.13/libexec/bin` ahead of `miniconda3` on `PATH` and propagate `exit $rc` explicitly.
   - **Subshell Exit & Script Path Verification (`tree`):** Missing explicit `set -euo pipefail` / `exit $rc` hid partial failures until `tree` checked the raw transcript; never rely on summary lines alone when transcripts contain `ld:` / `FAIL`.
   - **Mid-Stream Rules Gate Updates (`AI-management` `HEAD` bumps):** When `~/AI-management` received new commits mid-session (`5941223`), every newly woken session triggered `[MANDATORY AI-MANAGEMENT RULES GATE]`. **Adjustment:** Include `(read & ack ~/AI-management at <HEAD> first if not yet done)` in every next order file right after a rules repo update so executors clear the gate before touching project tools.
   - **Hung Command Triage (`ttys000`):** When a tab stalled with a background command (`task-*`) running >20 minutes without transcript growth, inspecting `history of t` revealed an unbuffered vs missing-file wait; nudging the executor via bridge to inspect/kill the hung child task with `manage_task` and re-run with `-u` unbuffered output recovered cleanly without restarting the whole conversation.
4. **macOS Terminal & Bridge Hygiene:**
   - Preserve fixed tab-to-role assignments (`ttys000`=`tree`, `ttys001`=`committee`, `ttys002`=`runner`, `ttys003`=`prep`, `ttys004`=`audit`) and never message unrelated Terminal tabs.
   - Note that terminating and restarting an executor creates a new PID (`send_to_tty.sh --list` shows the old `NAME` as a stale PID until re-registered), while `agy` window `TITLE` (e.g., `ingot-prep`, `ingot-runner`) stays live across `/resume` in the same tab. When waking relocated sessions next round, re-register `--register <name>` as part of startup if needed.

---

## 6. Quick Reference Checklists

### Before Dispatching a Wave
- [ ] Single writer (`tree`) only owns git commits; `prep`/`runner`/`audit` point to immutable `tip-<sha>` exports.
- [ ] Order file written with exact input paths, single-core flag (`-j1`), logger path, report path, and sealed-directory exclusions.
- [ ] `agy -p "/usage"` checked against quota reserve floor (`>= 70%`).
- [ ] If `~/AI-management` `HEAD` changed since last order, tell executors to read & `ack-rules.sh` at the new `HEAD` first.

### For Every `audit` (`CX-*`) Order
- [ ] Enumerate exact permitted files/subdirectories only; explicitly forbid recursive scans over parent directories containing sealed datasets.
- [ ] Verify git identity (signed vs intentionally unsigned project rule), parent links, fail-first non-zero exit vs pass exit `0`, export archive diff (`0` missing / `0` changed), JSONL job totals, and SHA-256 digests.

### At Quota Pause (`< 70%`)
- [ ] Stop dispatching new work immediately; allow active atomic verification rounds to finish cleanly or save checkpoint.
- [ ] As each executor finishes and goes idle, `kill -TERM <old_pid>`, `cd <canonical_repo_root>`, and resume `--conversation` / `codex resume` in its original tab.
- [ ] Verify Codex `Working directory · resume` picker is confirmed (`4. Always use current directory`) and check `send_to_tty.sh --list` so all executors sit idle in `<canonical_repo_root>`.
