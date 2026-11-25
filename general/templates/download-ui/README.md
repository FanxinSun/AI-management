# Template: parallel threaded download with an in-place dashboard

> [!CAUTION]
> ## MANDATORY RULE (non-negotiable — user directive, 2026-11-24)
> Whenever a task requires delivering a download script for the user to run:
> 1. **You MUST deliver a runnable script** built by copying and adapting `fetch_dst.py` and `download_wrapper.sh` from this folder.
> 2. **NEVER** invent an ad-hoc `curl`/`wget`/`tqdm`/line-by-line `print` downloader, and **NEVER** drop the in-place `\033[<n>A\033[J` dashboard, the `<100`-column narrow layout, the `status` subcommand, the automatic default folder, HTTP Range resume, size/checksum verification, the `caffeinate`-safe single-instance guard, or exit codes `0`/`1`/`2`/`3`.
> 3. **Always test** through the exact launch wrapper (including `status` and `<100` col width) and place the **complete, exact, copy-paste-ready runnable command at the very end** of your closing message (Rule 14).

Recorded 2026-11-19 at the user's request. Origin: the user's `~/Downloads/download_step3.sh` (parallel
threaded downloading, a dashboard redrawn in place at a sensible refresh rate); rebuilt and tested in
topic E11 (`e11-delphi-sidereal-lineshape`, 2026-11-18) for 472 files, 43.0 GB. The E11 run finished with
all 472 files verified (exit 0).

Files here are reference copies of the E11 files exactly as tested (not generalised):
- `fetch_dst.py` = `tools/s3b_fetch_dst.py` (Python stdlib only). The project-specific parts are `RECORDS`,
  `API`, `URL`, `EOS`, `eos_url()`, and the `list` and `probe` subcommands; the rest is generic.
- `download_wrapper.sh` = `tools/pieceB_download.sh` (the user-facing command).

## The interface (what the user sees and types)
- `wrapper.sh` runs with no argument (default folder), `wrapper.sh status` (what is done/partial/bad/missing, no
  network), `wrapper.sh DEST [status]` (relative DEST is taken from where the user stands).
- Settings by environment variables, all optional: WORKERS (32), MAX_ATTEMPTS (10), REPORT_SECS (auto),
  FILE_LINES (8 or all), DRY_RUN, CAFFEINATE, PYTHON, DOWNLOAD_ROOT.
- Dashboard redrawn in place (`\033[<n>A\033[J`): every 5 s on a terminal, 30 s when piped. Overall progress and
  ETA, windowed speeds, one bar per record/group, the files being fetched. A narrow layout below 100 columns.
  All detail goes to `<folder>/download.log`.
- Ctrl-C is safe (partials kept, exit 130); rerun resumes.
- Exit codes: 0 done or asked stop; 1 failure/block/give-ups/network down; 2 usage or foreign folder or CA pin
  mismatch; 3 disk space or another download on the folder.

## The mechanics worth keeping
- N worker threads over a shared claim queue; one connection each; HTTP Range resume (206 append, 200 restart).
- Verify size + adler32 (+ sha256) while streaming; a row goes to `fetch-log.tsv` only after verification;
  failures are renamed `*.bad`, never deleted; `SHA256SUMS` written when a group is complete.
- Stall detection (bytes/s under a limit for a window: drop and resume); a file is given up only after several
  attempts in a row with no new bytes; if every connection fails the run stops ("network seems down").
- Soft budgets (`--max-files`, `--max-seconds`) drain: they stop new claims but let running files finish.
- Disk check reserves the in-flight files' sizes; lock dir `.download.lock`.
- Certificate pinning (`--cafile` + `--cafile-sha256`); never an unverified SSL context.

## Pitfalls found (keep these tests)
1. Single-guard bug: the "another fetch is running" check read `ps` and counted its own `caffeinate` helper.
   `caffeinate -i CMD` execs CMD in the same PID and forks a helper CHILD that keeps the whole command line. The
   guard must skip this process, every ancestor (job logger, `zsh -c "..."`) and every descendant, from one
   `ps -axo pid=,ppid=,command=` read. Always test through the exact launch form of the wrapper, not only the
   bare Python.
2. A status command must create nothing (it once created DEST); use the nearest existing parent for free space.
3. A soft stop must not abort in-flight downloads (separate stop and drain events).
4. Terminals of 80 columns need the narrow layout, or the speeds get cut.
5. Make the first-run default folder automatic: the user ran the wrapper with no argument and got usage.
6. Multi-record height overflow (2026-11-22): when a run has many records (e.g. 29 in E1 vs 3 in E11), `len(head)` alone can exceed `term_rows`, causing `\033[<n>A` to clamp at row 1 and strand top lines in scrollback every 5 s. Fix: query `os.get_terminal_size(sys.stdout.fileno())`, cap TTY frames strictly to `term_rows - 1` lines, switch `RECORDS` adaptively between 1-col, 2-col (`cols >= 108`), and grouped summary views, wrap every line with `cut()`, and redraw with `\033[%dA\r\033[J`.

## To reuse
Copy both files, change the project parts (list format, URLs, record table, default folder, the CA pin if any),
keep the dashboard, guard, resume, verification and exit codes, and re-run the tests above before real use.
