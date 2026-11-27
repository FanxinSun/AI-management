#!/bin/bash
# Installs every safe, portable tool in this repo for Claude Code, agy and Codex.
# Regulations (executor-rules, ultracode-rule) are NOT installed here; run their installers by hand if wanted.
# Also skipped on purpose: codex-custom build (Linux-only, heavy), `install-executor-rules.sh --codex-policy`
# (user-only, guarded), agy-statusline (needs a manual settings.json edit; see README).
cd "$(dirname "$0")"
ok=0; fail=0
run() { echo "--- $*"; if "$@"; then ok=$((ok+1)); else echo "FAILED: $*" >&2; fail=$((fail+1)); fi; }
CH="${CLAUDE_HOME:-$HOME/.claude}"
mkdir -p "$CH/skills/agent-bridge"
run cp claude/skills/agent-bridge/SKILL.md "$CH/skills/agent-bridge/SKILL.md"                   # Claude skill
run bash general/tools/agent-bridge/install-agent-bridge-tool.sh                                 # Bridge scripts + symlinks
run codex/skills/agent-bridge/install-agent-bridge.sh                                             # Codex skill
run agy/skills/cross-agent-bridge/install-cross-agent-bridge.sh                                  # agy skill
run bash general/guides/gcp-hpc-cpu-onboarding/install-gcp-cpu-skill.sh                          # Cross-brand GCP CPU skill
run bash general/guides/poe-cli-wsl/install-poe-cli-skill.sh                                     # Cross-brand Poe CLI skill
run bash claude/hooks/agent-bridge/install-claude-bridge-hook.sh                                 # Claude bridge hook
run bash claude/hooks/rules-gate/install-claude-rules-gate-hook.sh                               # Claude rules-gate hook
run bash claude/hooks/claude-guardrails/install-claude-guardrails-hook.sh                        # Claude thought-chain & dialog guardrails
run bash agy/hooks/rules-gate/install-agy-rules-gate-hook.sh                                     # agy rules-gate hook
run codex/style/codex-focus/install-codex-style.sh                                               # Codex TUI style
run fix/wsl-clipboard/install-wsl-clipboard.sh                                                   # WSL wl-paste screenshot bridge
echo "done: $ok ok, $fail failed"
[ "$fail" -eq 0 ]
