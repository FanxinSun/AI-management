# AI-management

Tools, regulations, rules, templates, and configuration guides for multi-agent CLI coordination, cross-session terminal control, and CLI UI customisations for **Antigravity (`agy`)**, **Claude Code**, **Codex**, and **Gemini**.

---

## Why Let Your AI Read & Install This Repo?

Having your AI agent (or team of agents) read and install this repository fundamentally upgrades how autonomous AI sessions behave on your machine. Instead of isolated, unpredictable, and hallucination-prone agents, you get a disciplined, interconnected, and production-ready multi-agent engineering environment:

### 1. Hallucination-Free, Disciplined Agent Execution
* **Zero Make-Up (Rule 1)**: Every number, metric, path, error, and quoted line must come directly from real tool output or files. Agents are barred from inventing facts or guessing file states.
* **Strict Plan Adherence (Rule 2 & 5)**: Agents follow ordered handover plans step-by-step. They cannot silently alter specifications, delete user code, or take unauthorized shortcuts.
* **Anti-Regression & Independent Verification (Rule 4 & 8)**: Work already verified is strictly preserved. Every test and check must be capable of failing on an independent source rather than trivially validating against a copy of itself.
* **Copy-Paste Ready Deliverables (Rule 14)**: Whenever manual user execution is required, agents must provide the exact, full runnable command at the very end of their response.

### 2. Autonomous Cross-Terminal Multi-Agent Collaboration (`send_to_tty`)
* **Breaks Agent Silos**: Enables agents running across different terminal tabs or multiplexers (Windows Terminal, tmux, macOS Terminal) to message each other, dispatch work, and coordinate complex pipelines.
* **Manager-Executor Workflows**: Planners and managers can orchestrate specialized worker agents (runners, auditors, preparers) and receive completion signals automatically via `send_to_tty reply "<status>"`.
* **Collision-Free Terminal Injection**: Built-in dialog and state detectors check whether the target session is at an idle prompt or awaiting interactive user input before sending keystrokes, preventing corrupted sessions.

### 3. Automated Guardrails & Quality Assurance
* **Interactive Picker Blocker**: Intercepts fragile TUI selection prompts (`AskUserQuestion`), forcing verifiable plain-text approvals with clear provenance trails.
* **Numerical & Code Hygiene**: Hooks refuse edits introducing `1 - cdf` floating-point precision loss in statistical functions (enforcing `.sf`) and prevent brittle hardcoded `python3.X` site-packages paths.
* **Pre-Flight Spec Linter (`check_spec.py`)**: Automatically detects vague handover contracts, missing CLI flags, and formatting drift before handovers are executed.
* **Repository Safety (Rule 11 & 12)**: Strictly gates git push operations and protects unowned/third-party repositories from unauthorized modifications.

### 4. Production-Grade Templates & UI Telemetry
* **Standardized Download Dashboard**: Provides a battle-tested threaded downloader (`fetch_dst.py` + `download_wrapper.sh`) with in-place live redraws, `<100`-col layout, HTTP Range resumption, and POSIX exit codes.
* **Live Terminal Telemetry**: Adds Claude-style statusline pills (`[WORKING]` / `[STOPPED]`), color badges (`/color`), and live braille tab spinners for `agy`, alongside the distraction-free `codex-focus` style bundle for Codex.
* **Host Friction Fixes**: Bundles out-of-the-box fixes for fast WSL2 screenshot clipboard pasting (~80–115 ms), keyboard remapping, chassis lighting, and socket starvation.

### 5. Turnkey Installation
Running `./install-all.sh` configures hooks, skills, and `$PATH` utilities across all supported agent CLIs on your system in seconds.

---

## Repository Organization

The repository is organized cleanly at the top level into 5 folders — **target AI brand** (`general/`, `claude/`, `agy/`, `codex/`) plus **`fix/`** (host/hardware/WSL fixes) — and subdivided by **usage category** (`regulations/`, `rules/`, `templates/`, `guides/`, `tools/`, `hooks/`, `skills/`, `style/`, `custom-build/`), with **one case per folder**.

---

## 1. General (All AI Brands Applicable) — `general/`

### Regulations (`general/regulations/`)
* **[Executor Regulations](general/regulations/executor-regulations/The_Executor_Regulations.md)**  
  Strict rules for `agy`, Codex, and Claude Code sessions acting as executors (no made-up facts, apply given lists exactly, keep what was verified), rules for the manager who orders them, agent profiles, and incident history. The rules bind the seat, whatever the brand: [`EXECUTOR_RULES_BLOCK.md`](general/regulations/executor-regulations/EXECUTOR_RULES_BLOCK.md) for the executor and [`PLANNER_RULES_BLOCK.md`](general/regulations/executor-regulations/PLANNER_RULES_BLOCK.md) for the planner are installed for agy, Codex and Claude Code by [`install-executor-rules.sh`](general/regulations/executor-regulations/install-executor-rules.sh), and [`HANDOVER_RULES.md`](general/regulations/executor-regulations/HANDOVER_RULES.md) is the block to paste into a handover.
* **[Others' Repositories Regulation](general/regulations/others-repositories/The_Others_Repositories_Regulation.md)**  
  Set by the user on 2026-11-17: without the user's direct approval, no modification, merge, or pull request on a repository (or repo-like resource) that the user does not own.

### Rules (`general/rules/`)
* **[Mandatory Repo-Read & Download UI Rule](general/rules/mandatory-repo-read/The_Mandatory_Repo_Read_Rule.md)**  
  Set by the user on 2026-11-24: every brand new session (at startup) and every resumed/old unacknowledged session MUST read `~/AI-management` rules before working. In Claude Code a hook records the reads and refuses other tools until every file on [`reading-list.txt`](general/rules/mandatory-repo-read/reading-list.txt) is read; for agy and Codex [`ack-rules.sh`](general/rules/mandatory-repo-read/ack-rules.sh) checks the reads in the session's own log ([`ack_reads.py`](general/rules/mandatory-repo-read/ack_reads.py)) and refuses an acknowledgment while a file is unread. Also enforces copying/adapting `general/templates/download-ui/` for all user-run download scripts.
* **[Regular Remote Push Rule](general/rules/regular-remote-push/The_Regular_Remote_Push_Rule.md)**  
  Set by the user on 2026-11-23: all user-owned projects with a git repo must push to the remote regularly (at milestones and whenever blocked) with descriptive commit messages and up-to-date in-repo status files.
* **[Multi-Agent Coordination & Dispatch Rules](general/rules/multi-agent-dispatch/MULTI_AGENT_DISPATCH_RULES.md)**  
  Hard dispatch gate: review dispatch to Claude Code is strictly gated until both Manager and Executor sessions have finished working (both in `[STOPPED]` state).
* **[Project Planning Rule](general/rules/project-planning/The_Project_Planning_Rule.md)**  
  Set by the user on 2026-09-23: a project has one and only one `PLAN.md`, one `PLAN_lane<N>.md` per lane, sub-plan files that are each a single execution step, and one execution order per plan. Every AI agent works from the same plan files; a takeover from another agent starts with a snapshot push and edits increase-only. Checked by `check_spec.py --plan-layout`.
* **[Brand Neutrality Rule](general/rules/brand-neutrality/The_Brand_Neutrality_Rule.md)**  
  Set by the user on 2026-11-26: an agent treats every AI brand's content (transcripts, histories, caches, handovers, and what is written about an agent) by one standard, its own brand included. Each brand's store is read the way it is keyed, with [`ai_content_inventory.py`](general/rules/brand-neutrality/ai_content_inventory.py); a report has a line for every brand.
* **[Script Delivery Rule](general/rules/script-delivery/The_Script_Delivery_Rule.md)**  
  Set by the user on 2026-11-27: a script the user will run is built by copying the templates; a claim about its format needs [`check_frame.py`](general/rules/script-delivery/check_frame.py) run on a capture of its screen; only a script sends a script's lines; a run counts only when the user started it on a script the user has not objected to; and while the user is correcting a script, the project waits.

### Templates (`general/templates/`)
* **[Download UI Template](general/templates/download-ui/README.md)**  
  Mandatory parallel threaded download interface: [`fetch_dst.py`](general/templates/download-ui/fetch_dst.py) and [`download_wrapper.sh`](general/templates/download-ui/download_wrapper.sh) with in-place dashboard redraw, `<100`-col narrow layout, `status` mode, HTTP Range resume (and byte ranges on parallel connections), verification, `caffeinate`-safe single-instance guard, and exit codes `0`/`1`/`2`/`3`. Since 2026-11-27 it is built from e7's downloader, with the dashboard the user merged row by row from e6's and e7's (guide §7).
* **[Chunked Pipeline Template](general/templates/chunked-pipeline/README.md)**  
  The AI-free all-in-one split script (2026-11-27), built from e7's: [`all_in_one.sh`](general/templates/chunked-pipeline/all_in_one.sh), [`pipe.py`](general/templates/chunked-pipeline/pipe.py), [`download_one.sh`](general/templates/chunked-pipeline/download_one.sh), [`run_logged.py`](general/templates/chunked-pipeline/run_logged.py) and [`verify_download.py`](general/templates/chunked-pipeline/verify_download.py). File by file it runs the download, the logged jobs, the keep until the manager accepts the file, and the logged deletion, with one bridge line per file; at the end of a split come the report and the nudge. It first matched e7's own driver exactly; its format is now the one the user merged row by row from e6's and e7's (guide §7).

### Tools (`general/tools/`)
* **[Agent Bridge (`send_to_tty.sh`)](general/tools/agent-bridge/send_to_tty.sh)**  
  Cross-session terminal relay (`send_to_tty.sh` + [`conin_inject.ps1`](general/tools/agent-bridge/conin_inject.ps1) + [`install-agent-bridge-tool.sh`](general/tools/agent-bridge/install-agent-bridge-tool.sh)) for sending prompts, `--raw` slash commands, and replies across `agy`, Claude Code, Codex, and Gemini tabs on macOS, WSL2/Windows Terminal, and Linux/tmux, with pre-send Claude JSONL + console (`CONOUT$`/`history`/`tmux`) dialog guards.
* **[Handover & Statistical Spec Linter (`check_spec.py`)](general/tools/handover-lint/README.md)**  
  Pre-flight checker for handovers, sub-plans, review replies, and statistical scripts: catches placeholder `"contract is exact"` specs lacking CLI flags, retired paths, `(Recommended)` picker approval patterns, Addendum/header drift, `1 - cdf` float64 tail cancellation (any distribution), hardcoded `python3.<N>` site-packages paths, `.splitlines()`, and plan files outside the layout of the Project Planning Rule (`--plan-layout`).

### Guides (`general/guides/`)
* **[Chunked Download–Process–Delete Pipeline Guide](general/guides/chunked-pipeline-workflow/CHUNKED_PIPELINE_GUIDE.md)**  
  AI-free chunked/split pipeline pattern (from E6 & E7): bounded-disk download → verify → skim/process → independent check → logged deletion → report → bridge nudge/watch loop, standardized exit codes, gates, and field lessons.
* **[Planner-Executor Multi-Agent Operation Guide](general/guides/planner-executor-conduct/PLANNER_EXECUTOR_OPERATION_GUIDE.md)**  
  Operational guide for running 1 Planner (`committee`) + 4 specialized Executors (`tree`, `prep`, `runner`, `audit`): role boundaries, immutable snapshots, precision/audit controls, model/effort tiering, quota pause & relocation, and live failure recovery.
* **[How to Control Agent Sessions (macOS)](general/guides/agent-control-macos/How_to_Control_Agent_Sessions_macOS.md)**  
  Terminal.app AppleScript injection, conversation memory, relay correction, model/effort switching, and manual Codex resume after usage limits.
* **[How to Control Agent Sessions (WSL / Linux)](general/guides/agent-control-wsl/How_to_Control_Agent_Sessions_WSL.md)**  
  Windows Terminal console input injection, `tmux send-keys`, the dialog guard, session titles and model switching. Host fixes (clipboard paste, keyboard, Codex `app-server` socket) are in `fix/`.
* **[Muse CLI Local WSL2 Connection Guide](general/guides/muse-cli-wsl/MUSE_CLI_WSL_GUIDE.md)**  
  WSL2 installation (`muse-cli`), zero-interruption background Windows Chrome `NetworkService` memory cookie sync (`sync_muse_cookies_wsl.sh`), token lifecycle, and agent-safe commands.
* **[Google Cloud HPC CPU Onboarding & Co-Execution Guide](general/guides/gcp-hpc-cpu-onboarding/GCP_HPC_CPU_ONBOARDING_GUIDE.md)**  
  Colab CPU vs. Zen 5 desktop vs. GCP `H4D`/`C4D`, `$0`-upfront Ultra Developer Program credit onboarding (avoiding the `$5` Prepay trap), SKU exclusions, WSL2 multi-profile CDP human–agent break-down workflow, and cross-brand `gcp-cpu-compute` skill installer ([`install-gcp-cpu-skill.sh`](general/guides/gcp-hpc-cpu-onboarding/install-gcp-cpu-skill.sh)).

---

## 2. Claude Code Only — `claude/`

* **Rules (`claude/rules/`)**:
  * **[The 10 Years Rule](claude/rules/ten-years-retention/The_10_Years_Rule.md)**: Keep Claude Code session transcripts for 10 years (`"cleanupPeriodDays": 3650`).
  * **[The Ultracode Rule](claude/rules/ultracode-workflow/The_Ultracode_Rule.md)**: Self-started dynamic workflows with lower-effort subagents (`CLAUDE_md_section5.md`, `install-ultracode-rule.sh`).
  * **[The Claude Thought-Chain & Guardrail Rule](claude/rules/thought-chain-rigor/The_Claude_Thought_Chain_Rule.md)**: Plain-text approvals with provenance audits, consumer-first/binary-first checks, concrete CLI contracts, float64/bounds numerical hygiene, and Supervisor seat boundaries (`CLAUDE_md_section6.md`).
* **Hooks (`claude/hooks/`)**:
  * [`agent-bridge/`](claude/hooks/agent-bridge/install-claude-bridge-hook.sh): Injects agent-bridge instructions into Claude Code sessions/subagents (`CLAUDE_md_section4.md`).
  * [`rules-gate/`](claude/hooks/rules-gate/install-claude-rules-gate-hook.sh): Enforces the mandatory `~/AI-management` repo read (rewritten 2026-11-25): `PostToolUse` records which files of [`reading-list.txt`](general/rules/mandatory-repo-read/reading-list.txt) a session read whole, by content; `PreToolUse` refuses its other tools until all are read; after a commit only the changed files are asked for.
  * [`claude-guardrails/`](claude/hooks/claude-guardrails/install-claude-guardrails-hook.sh): Blocks `AskUserQuestion` pickers, refuses an edit of a `.py` file that adds a `1 - cdf` upper tail or a hardcoded `python3.X` path (comments, docstrings, `1 - cdf` strings, and hunks/lines that already had it are left alone), and injects the T1–T5 thought-chain summary.
* **Skills (`claude/skills/`)**:
  * [`agent-bridge/SKILL.md`](claude/skills/agent-bridge/SKILL.md): Claude Code skill for cross-agent terminal messaging.

---

## 3. Antigravity CLI (`agy`) Only — `agy/`

* **Tools (`agy/tools/`)**:
  * **[Statusline & Tab Animation](agy/tools/statusline/README.md)**: `statusline.py`, `color.py`, and `/color` skill for Claude-style `[WORKING]` / `[STOPPED]` pills, colored session badges, and live terminal tab braille spinners.
* **Hooks (`agy/hooks/`)**:
  * [`rules-gate/`](agy/hooks/rules-gate/install-agy-rules-gate-hook.sh): Enforces the mandatory `~/AI-management` repo-read gate in `~/.gemini/config/hooks.json` (`SessionStart` + `PreInvocation`). Since 2026-11-27 it lists the files a session has still to read and records the acknowledgment by itself when the session's own log holds them all.
* **Skills (`agy/skills/`)**:
  * [`cross-agent-bridge/`](agy/skills/cross-agent-bridge/SKILL.md): `agy` skill + [`install-cross-agent-bridge.sh`](agy/skills/cross-agent-bridge/install-cross-agent-bridge.sh).

---

## 4. Codex Only — `codex/`

* **Style (`codex/style/codex-focus/`)**:
  * **[Codex Focus Style Bundle](codex/style/codex-focus/README.md)**: Portable `[tui]` appearance (`tui-settings.toml`, `themes/codex-focus.tmTheme`, `install-codex-style.sh`).
* **Custom Build (`codex/custom-build/`)**:
  * **[Full Codex Custom Build](codex/custom-build/README.md)**: Pinned 0.154.0 source patch (`source/`), reproducible build/package/rollback scripts (`tooling/`), portable launcher (`launcher/`), session helpers (`session-helpers/`), and [`PLAN.md`](codex/custom-build/PLAN.md).
* **Skills (`codex/skills/`)**:
  * [`agent-bridge/`](codex/skills/agent-bridge/SKILL.md): Codex skill + [`install-agent-bridge.sh`](codex/skills/agent-bridge/install-agent-bridge.sh).

---

## 5. Host & Hardware Fixes — `fix/`

* **[WSL Screenshot Clipboard Bridge (`wsl-clipboard`)](fix/wsl-clipboard/README.md)**: Native Win32/GDI+ `wl-paste` drop-in for WSL2 (~80–115 ms).
* **[NuPhy Air96 Keyboard Remap (`nuphy-air96`)](fix/nuphy-air96/README.md)**: PowerToys Keyboard Manager remap & registry setup for volume and Snipping Tool.
* **[ASUS Aura Sync Box Fan LEDs (`asus-aura-fans`)](fix/asus-aura-fans/README.md)**: CLI tool (`set-fan-leds.sh` / `set-fan-leds.ps1`) for chassis ARGB dimming.
* **[Samsung Odyssey G8 (`samsung-odyssey-g8`)](fix/samsung-odyssey-g8/README.md)**: Display configuration, VSS auditing, and Night Light / Iris triage.
* **[Codex `app-server` Socket Starvation (`codex-app-server-socket`)](fix/codex-app-server-socket/README.md)**: "workspace routing discovery timed out" when a supervisor floods the Codex socket; diagnosis and fix.

---

## Quick Start

### Install All Portable Tools, Skills & Hooks

```bash
./install-all.sh
./general/regulations/executor-regulations/install-executor-rules.sh
```

### Agent Bridge (`general/tools/agent-bridge/send_to_tty.sh`)

```bash
# List all running agent sessions across tabs
general/tools/agent-bridge/send_to_tty.sh --list

# Register a human-readable name for your current session
general/tools/agent-bridge/send_to_tty.sh --register reviewer

# Send a prompt to another agent session by name or kind:pid
general/tools/agent-bridge/send_to_tty.sh reviewer "Please review report.md"
general/tools/agent-bridge/send_to_tty.sh agy:8410 "Analyze recent logs"

# Reply straight back to whoever last messaged you
general/tools/agent-bridge/send_to_tty.sh reply "[AGY-FEEDBACK] All checks passed"
```

---

## Buy me a coffee

AI-management is free and open-source. If it has been useful to you, you are warmly welcome to support its continued development with a coffee. There is no obligation at all—your interest, feedback, and use of the project already mean a great deal. Thank you.

### [☕ **Buy me a coffee**](https://buymeacoffee.com/fanxinsun)

If Buy Me a Coffee is not convenient, [Alipay](assets/alipay.jpg) is also available (打开支付宝，扫一扫). Thank you for helping this work continue.

---

## Repository Structure

```text
├── README.md
├── install-all.sh
├── assets/
│   └── alipay.jpg
├── general/
│   ├── regulations/
│   │   ├── executor-regulations/      # The_Executor_Regulations.md, EXECUTOR_RULES_BLOCK.md, PLANNER_RULES_BLOCK.md, HANDOVER_RULES.md, installer
│   │   └── others-repositories/       # The_Others_Repositories_Regulation.md
│   ├── rules/
│   │   ├── brand-neutrality/          # The_Brand_Neutrality_Rule.md, ai_content_inventory.py, CLAUDE_md_section10.md
│   │   ├── mandatory-repo-read/       # The_Mandatory_Repo_Read_Rule.md, ack-rules.sh, ack_reads.py, reading-list.txt
│   │   ├── multi-agent-dispatch/      # MULTI_AGENT_DISPATCH_RULES.md
│   │   ├── project-planning/          # The_Project_Planning_Rule.md
│   │   ├── regular-remote-push/       # The_Regular_Remote_Push_Rule.md
│   │   └── script-delivery/           # The_Script_Delivery_Rule.md, check_frame.py, frame_test_server.py, CLAUDE_md_section11.md
│   ├── templates/
│   │   ├── chunked-pipeline/          # README.md, all_in_one.sh, pipe.py, download_one.sh, run_logged.py, verify_download.py
│   │   └── download-ui/               # README.md, fetch_dst.py, download_wrapper.sh
│   ├── tools/
│   │   ├── agent-bridge/              # send_to_tty.sh, conin_inject.ps1, install-agent-bridge-tool.sh
│   │   └── handover-lint/             # check_spec.py, README.md
│   └── guides/
│       ├── agent-control-macos/       # How_to_Control_Agent_Sessions_macOS.md
│       ├── agent-control-wsl/         # How_to_Control_Agent_Sessions_WSL.md
│       ├── chunked-pipeline-workflow/ # CHUNKED_PIPELINE_GUIDE.md
│   │   ├── gcp-hpc-cpu-onboarding/    # GCP_HPC_CPU_ONBOARDING_GUIDE.md, SKILL.md, install-gcp-cpu-skill.sh
│       ├── muse-cli-wsl/              # MUSE_CLI_WSL_GUIDE.md, sync_muse_cookies_wsl.sh
│       └── planner-executor-conduct/  # PLANNER_EXECUTOR_OPERATION_GUIDE.md
├── claude/
│   ├── rules/
│   │   ├── ten-years-retention/       # The_10_Years_Rule.md
│   │   ├── thought-chain-rigor/       # The_Claude_Thought_Chain_Rule.md, CLAUDE_md_section6.md
│   │   └── ultracode-workflow/        # The_Ultracode_Rule.md, CLAUDE_md_section5.md, install-ultracode-rule.sh
│   ├── hooks/
│   │   ├── agent-bridge/              # install-claude-bridge-hook.sh, CLAUDE_md_section4.md
│   │   ├── claude-guardrails/         # install-claude-guardrails-hook.sh
│   │   └── rules-gate/                # install-claude-rules-gate-hook.sh
│   └── skills/
│       └── agent-bridge/              # SKILL.md
├── agy/
│   ├── tools/
│   │   └── statusline/                # README.md, statusline.py, color.py, skills/color/
│   ├── hooks/
│   │   └── rules-gate/                # install-agy-rules-gate-hook.sh
│   └── skills/
│       └── cross-agent-bridge/        # SKILL.md, install-cross-agent-bridge.sh
├── codex/
│   ├── style/
│   │   └── codex-focus/               # README.md, install-codex-style.sh, style-manifest.toml, tui-settings.toml, themes/
│   ├── custom-build/                  # README.md, PLAN.md, launcher/, session-helpers/, source/, tooling/
│   └── skills/
│       └── agent-bridge/              # SKILL.md, install-agent-bridge.sh
└── fix/
    ├── asus-aura-fans/                # README.md, set-fan-leds.ps1, set-fan-leds.sh
    ├── codex-app-server-socket/       # README.md
    ├── nuphy-air96/                   # README.md, apply-nuphy-air96-mappings.sh, default.json
    ├── samsung-odyssey-g8/            # README.md, check-display.ps1, check-display.sh
    └── wsl-clipboard/                 # README.md, install-wsl-clipboard.sh, wl-paste, wl-paste.cpp
```
