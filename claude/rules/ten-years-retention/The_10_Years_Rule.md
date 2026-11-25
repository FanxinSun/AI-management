# The 10 Years Rule: keep Claude Code sessions for 10 years

**Rule (set 2026-11-05):** every machine that runs Claude Code has

```json
"cleanupPeriodDays": 3650
```

in `~/.claude/settings.json`, so session transcripts are kept for about 10 years
instead of 30 days. No agent lowers this value or sets it to 0.

## Why

Claude Code deletes a session transcript
(`~/.claude/projects/<project>/<session-id>.jsonl`, plus its subagent files) once
it has not been modified for `cleanupPeriodDays` days. The default is 30. The
cleanup runs at startup, gives no warning, and removes a few old sessions at a
time, so nothing looks wrong until old sessions are missing from `/resume`.

On the WSL machine this went unnoticed until 2026-11-05. By then 646 sessions from
June to early October 2026 were gone. Only 191 came back, and most of those only as
the prompts that `~/.claude/history.jsonl` had kept.

## How to apply

1. Add the key at the top level of `~/.claude/settings.json`:

   ```json
   {
     "cleanupPeriodDays": 3650,
     ...
   }
   ```

2. Start a new session; the value is read at startup.

3. Make sure nothing overrides it. Managed settings and project settings take
   precedence over user settings:
   - managed: `/etc/claude-code/managed-settings.json` (Linux/WSL),
     `/Library/Application Support/ClaudeCode/managed-settings.json` (macOS);
   - project: `<project>/.claude/settings.json` and
     `<project>/.claude/settings.local.json`.

## Check

```bash
grep -n cleanupPeriodDays ~/.claude/settings.json            # expect 3650
grep -rln cleanupPeriodDays /etc/claude-code ~/*/.claude ~/*/*/.claude 2>/dev/null
ls -l ~/.claude/.last-cleanup                                 # when cleanup last ran
```

The second command should list nothing. If it lists a file, check that file's value.

## If sessions have already disappeared

- Check `cleanupPeriodDays` first, including the project and managed settings
  above.
- Act within days. The WSL ext4 disk is mounted with `discard`, so the blocks of
  deleted files are trimmed and read back as zeros soon after deletion. Windows
  shadow copies (VSS) of C: can still hold an older `ext4.vhdx` with the files in
  it, but they rotate out within days.
- `~/.claude/history.jsonl` keeps every prompt you typed, with its session ID,
  even after the transcript is deleted. That is the last-resort source.
- The scripts used for the 2026-11-05 recovery are in `D:\claude-recovery` on the
  WSL machine: `carve.py` (free-space carver, needs root), `extract.py` (reads the
  vhdx inside a shadow copy; no admin needed) and `restore.py` (installer, never
  overwrites). `restored\MANIFEST.tsv` there lists every restored file, so the
  restore can be undone.
