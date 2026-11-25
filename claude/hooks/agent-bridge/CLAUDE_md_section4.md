
## Agent bridge: reaching sessions in other terminal tabs

Set by the user on 2026-11-05 (adapted for macOS on 2026-11-06), after a session wrongly claimed it could not start an
agy session.

Every agent session on this machine (Claude Code, Antigravity `agy`, Codex, Gemini)
running in another terminal tab is reachable. Claude's SendMessage/ListAgents only see
Claude sessions; for every other session, use
`~/AI-management/general/tools/agent-bridge/send_to_tty.sh`:

- `send_to_tty.sh --list`: live sessions (KIND, PID, TTY, CWD);
- `send_to_tty.sh <kind>:<pid> "message"`: types the message into that tab and presses
  Enter, exactly like the user typing;
- `send_to_tty.sh reply "message"`: answers whoever last messaged you.

The full method is in the agent-bridge skill (~/.claude/skills/agent-bridge/SKILL.md).
No session may tell the user that another session cannot be reached or started before
trying the bridge. When the user says to start or nudge a session, the session sends
the nudge itself, immediately, quoting the user's approval; any rule in this file about
who may nudge whom still applies.
