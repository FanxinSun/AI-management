# Codex Focus style bundle

This directory records the portable appearance customization of the WSL Codex
CLI on 2026-11-06 (`codex-cli 0.154.0`). It is intentionally an appearance
bundle, not a copy of the Codex home directory.

## Recorded customization

The current `~/.codex/config.toml` contains this `[tui]` configuration:

```toml
[tui]
theme = "codex-focus"
status_line = ["thread-title", "model-with-reasoning", "current-dir", "permissions", "approval-mode", "five-hour-limit", "weekly-limit"]
status_line_use_colors = true
terminal_title = ["activity", "thread-title", "project-name"]
```

The exact custom syntax theme is preserved at
[`themes/codex-focus.tmTheme`](themes/codex-focus.tmTheme). Its base palette is
black (`#000000`) with light foreground (`#E6EDF3`), white caret (`#FFFFFF`),
blue selection (`#26344D`), dark blue-gray line highlight (`#171F2A`), and
blue-gray invisibles (`#65758B`). The complete syntax palette remains in the
theme file; `style-manifest.toml` records its SHA-256.

## Install on another machine

From a checkout of this repository:

```bash
cd /path/to/AI-management/codex-style
./install-codex-style.sh
```

For a non-default Codex home:

```bash
CODEX_HOME=/path/to/.codex ./install-codex-style.sh
```

The installer creates the theme directory when needed, installs the theme, and
adds or replaces only the four recorded keys in the exact `[tui]` table. An
existing `config.toml` or theme is backed up with a dated `.bak-style-*` suffix
before a changed file is replaced. Use `--dry-run` to validate the merge without
touching the target Codex home. Restart Codex sessions after installation.

## Scope boundary

The bundle does not copy authentication, the machine-wide responsibility
policy, hooks, handover/session history, logs, databases, project trust, model
defaults, plugin state, or skills. Those are private, security-sensitive,
machine-specific, or behavioral rather than visual settings.

The shell host also enables generic `ble.sh` and `starship` behavior and has a
terminal-recovery hook for interrupted TUIs. Those settings are not Codex
configuration and were not copied because they include unrelated shell and
machine environment; the Codex-specific appearance is fully represented here.
For reference, the capture shell reported `TERM=xterm-256color`,
`NO_COLOR=1`, and an empty `COLORTERM`; those host-wide values are recorded in
`style-manifest.toml` but are intentionally not forced on another machine.
