# Template: the chunked all-in-one pipeline (the split script)

> [!IMPORTANT]
> Whenever a download feeds processing (skim, filter, check), the Mandatory Repo-Read rule (§2, item 4) and
> [`CHUNKED_PIPELINE_GUIDE.md`](../../guides/chunked-pipeline-workflow/CHUNKED_PIPELINE_GUIDE.md) ask for one
> unattended, resumable script. Build it from these files together with [`../download-ui/`](../download-ui/README.md):
> copy, change the project's parts named below, keep the rest, and run the tests at the end before real use.

Recorded 2026-11-27. On that day the user asked to "align the UI/format in the repo WITH WHAT e6/e7 ARE USING STRICTLY".
The user then chose, row by row, one merged format from e6's and e7's; the guide's §7 holds that table.

Changed the same evening, after the user ran a split built from these files: "the format is not good as expected. It
keeps jumping. I need a stable UI refresh itself, not keep on outputing", and "the GROUPS always show 0B, RECORDS only
show one file, while I always see the file is under processing, cannot see many files are being downloaded
simultaneously". The split now draws one dashboard of its own, for the whole split, and works on several files at once
(["The screen"](#the-screen); the guide's §7, Addendum).

These files are built from e7's split script, as e7 runs it: the user's project `e7-upsilon-omega`, step 6, the versions
pinned in e7's `tools/s6_all_in_one.pins` on 2026-11-27. e7's own work is taken out. The format is the merged one:
- **From e7:** the start, download and job lines, `report.md`, `status.tsv`, `files.tsv`, `nudges.tsv` and
  `deletions.tsv`, the lock, the pins, the gates and the test modes.
- **From e6** (`tools/e6_fetch_kplus.py` of `e6-emu-below-z`):
  - the `[<utc>]` stamp on the per-file lines;
  - the `WAITING` row and the stamped `WAITING` line;
  - the `SUMMARY` line;
  - one bridge line per wait;
  - exit code 5 when a wait reaches its limit;
  - in the download's dashboard, the title with the read time-out and the `STEP`, `THIS STEP`, `TO DOWNLOAD
    (estimate)`, `HEALTH` and `GROUPS` rows.
- **Merged:** the bridge lines (e7's, with e6's step and group), the end nudge to every target, and the `status`
  command.

The downloader inside it is [`../download-ui/fetch_dst.py`](../download-ui/fetch_dst.py), built from e7's
`tools/s2_fetch.py`. Each download gets the run as `--context` (the split, the file's step and group, and the run's
totals) and, since the evening of 2026-11-27, `--status-file`: it then draws no frame of its own and writes its state
once a second for the split's dashboard.

## Files

| File | Built from e7's (sha256, first 16) | What differs from e7's |
|---|---|---|
| `all_in_one.sh` | `tools/s6_all_in_one.sh` (`e2995a77b3b24443`) | the names of the driver and the splits in the usage line, and exit 5 in the header; the code is e7's |
| `pipe.py` | `tools/s6_pipe.py` (`027c887a06a0a57d`) | e7's names are constants; e7's jobs are tables (`JOBS`, `TEMP_OUTPUTS`, `KEPT_OUTPUTS`, `END_JOBS`, `FACTS_JOB`); the merged lines (see "Differences from e7"); the split's dashboard and the workers (2026-11-27, evening) |
| `download_one.sh` | `tools/s6_download.sh` (`a45e5b97a00a2b84`) | the settings' prefix `PROJECT_DL_` (e7: `E7_S2_`), the Python, the downloader's file name, `PROJECT_DL_CONTEXT` (passed on as `--context`) and `PROJECT_DL_STATUS_FILE` (passed on as `--status-file`) |
| `run_logged.py` | `tools/run_logged.py` (`b75a503480805fee`) | the docstring only |
| `verify_download.py` | `tools/s2_verify.py` (`1b00e42096f72c6a`) | e7's ROOT-file check (`b"root"`) is the constant `MAGIC` (`None`: no check) |

In a project they all go into `<project>/tools/`, next to `fetch_dst.py` from `../download-ui/`.

## The screen

A frame from the middle of a real run, piped: the template's test copy (records named `DatasetA` and `DatasetB` in
`GROUP_NAMES`), a split of 10 files from the rule's test server (`--files 10 --kib 150`), 4 workers, and a 20-second
job after each file's check (`PROJECT_PIPE_SANDBOX_JOB_S=20`). The whole capture is
[`fixtures/pipeline-piped.txt`](../../rules/script-delivery/fixtures/pipeline-piped.txt):

```text
PROJECT pipeline tst1  |  23:32:23  |  elapsed 00:00:30  |  4 workers  |  time-out 300 s
STEP     5 of 10  group DatasetA  |  downloading 2, processing 2, finished 1 of 10 files
THIS STEP ██████████████░░░░░░  68.2%  moved 9.54 MB of 14.00 MB
TO DOWNLOAD (estimate)  24.00 MB in all   moved 10.54 MB
TOTAL    █░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   4.2%   1.00 MB / 24.00 MB
FILES    1/10 complete   2 downloading   4 workers alive
SPEED    now 300 KB/s   average 360 KB/s   ETA 00:11:30
LINKS    2 connections open   150 KB/s each   0 stalled right now
HEALTH   failed attempts 0   stalls dropped 0   certificate events 0

GROUPS (done / total)
  DatasetA ██░░░░░░░░░░░░░░░░░░   7.7%    1/5   files  1.00 MB / 13.00 MB
  DatasetB ░░░░░░░░░░░░░░░░░░░░   0.0%    0/5   files  0 B / 11.00 MB

RECORDS
  81001 DatasetA    ██░░░░░░░░░░░░░░░░░░   7.7%     1/5   files   1.00 MB / 13.00 MB
  81002 DatasetB    ░░░░░░░░░░░░░░░░░░░░   0.0%     0/5   files   0 B / 11.00 MB

DOWNLOADING NOW (showing 2 of 2, nearest to done first)
  81001 AAAA1111-a.bin       ███████████░░░░░  71%    4.25 MB / 6.00 MB    150 KB/s  ETA 00:00:11
  81001 C0000003-c.bin       ██░░░░░░░░░░░░░░  10%  300.00 KB / 3.00 MB    150 KB/s  ETA 00:00:18

PROCESSING NOW (showing 2 of 2, longest running first)
  81002 C0000002-c.bin       ████████░░░░░░░░  50%  job 2 of 2  wait running 15 s
  81002 BBBB2222-b.bin       ████████░░░░░░░░  50%  job 2 of 2  wait running 9 s

Ctrl-C stops cleanly; rerun resumes   |   log: runs/S1/pipeline-test/tst1/pipeline.log
```

- **On a terminal** this frame is the only thing on the screen while the split runs. It is redrawn in place
  (`\033[<n>A\033[J`) every 5 s, and whenever a file changes state (at most twice a second). It never gets taller
  than the window: first the `RECENT` rows go, then the file rows shrink, then the records and the groups, each to
  `… and N more`. At the end the last frame stays, and the end lines are printed below it: `SUMMARY`, `nudge:`,
  `status:` and `report:`. [`fixtures/pipeline-terminal-80.txt`](../../rules/script-delivery/fixtures/pipeline-terminal-80.txt)
  is a capture in a terminal of 80 columns, with the files already on disk.
- **Piped,** every line is printed as it comes, and a frame every 30 s. The lines are e7's (below), and each
  download's start and end lines, printed when that download ends.
- **Every line of the run** goes to `<run folder>/pipeline.log` with its UTC time, on a terminal too. Each download
  writes its own lines to `<run folder>/<id>/download-screen.log`. Once a second it also writes its state, for the
  dashboard, to `<run folder>/<id>/download-status.json`.

Where the numbers come from:
- **The title:** the split, the time of day, the time since the start, the workers and the downloader's read time-out.
- **`STEP`:** the file started last (its place in the list and its group), and how many files are downloading, how
  many are processing and how many are finished.
- **`THIS STEP`:** the files in flight: their bytes on disk out of their size. A file in its jobs counts as whole.
- **`TO DOWNLOAD (estimate)`:** the bytes this run has to download, and the bytes moved so far. The first number is
  the size of the split's files that are not DONE, less what is already on disk. When the data is already on disk it
  is 0 B, and the progress shows in `TOTAL`, `GROUPS` and `RECORDS`.
- **`TOTAL`, `FILES`, `GROUPS` and `RECORDS`:** the whole split. They count the files finished (DONE, in this run or
  an earlier one) out of all the files, with their bytes.
- **`SPEED`:**
  - `now` is the sum of the downloads' rates;
  - `average` is the bytes moved per second since the start;
  - `ETA` is the bytes not yet finished, divided by the rate at which files have finished in this run. It reads
    `unknown` until the first file finishes.
- **`LINKS` and `HEALTH`:** summed over the downloads. `HEALTH` counts every download of the run.
- **`DOWNLOADING NOW`:** each file that is downloading, nearest to done first, as the downloader's own row.
- **`PROCESSING NOW`:** each file in its jobs, longest running first: the job's number, its step and how long it has
  run. A job of the end of the split shows as `<job id> running N s   (the end of the split)`.
- **`RECENT`** (on a terminal only, and only when there is something): the last three stamped lines, for example file
  reports, `FAILED`, `deleted` and `WAITING`.

The rest of the screen:
- **Several files at once:** `PROJECT_PIPE_WORKERS` (default 4) files are worked on at once, in the list's order.
  - The pilot file runs alone, and the `--test` modes use 1 worker.
  - A file starts its download only when the free space covers its size, the floor and the bytes still to come of the
    files admitted before it.
  - The compute cap counts the limits of the jobs running now.
  - One deletion pass runs at a time.
- **When a connection fails:**
  - `HEALTH` counts failed attempts, stalls dropped and certificate events, and adds `LASTERR <first 60 characters>`.
  - After 900 s with no byte while attempts fail, it adds `NETWORK DOWN? waiting, retrying`.
  - The file's row ends in `retrying` or `waiting (certificate)`.
- **When a file fails:** `[<utc>] file <id> FAILED at <step>: its source and <KEPT_WORD> stay`, then
  `[<utc>] file report FAILED: …`.
- **In a deletion pass:** `[<utc>] deleted <path> (<bytes> bytes)`.
- **A wait** (disk space before a file, or the manager's acceptance at the end of the split):
  - once, `[<utc>] WAITING <what>: <why>`;
  - then the row `WAITING  <what>  since HH:MM:SS  next check in <s> s`, which is drawn in the frame on a terminal
    and printed once per poll when piped;
  - at its limit, exit 5.
- **A running job, piped:** `<stage> <job id> running N s | compute …` every 60 s. On a terminal the job is shown in
  `PROCESSING NOW` instead.
- **Line width:** the e6 lines (`[<utc>] WAITING …`, `[<utc>] SUMMARY: …`) wrap at the terminal's width, as e6 does.
  The other lines are cut there, as e7 does.
- **Ctrl-C** reaches every running job and download. The partial files stay, the exit code is 130, and the same
  command resumes.

## The bridge lines

To `FILE_NUDGE_DEFAULT` (the Committee: the first target that takes it), after each file and at the start of each wait:

```text
[PIPELINE s1 g1 file] <id> step <i> of <n> group <G> DONE (<p> of <n> passed); kept until accepted: <k> files (<ids or none>); failed waiting: <ids or none>; now carry out runs/S1/handover-file.md
[PIPELINE s1 g1 file] <id> step <i> of <n> group <G> FAILED at <step>, its source stays; kept until accepted: <k> files (<ids or none>); failed waiting: <ids or none>; now carry out runs/S1/handover-file.md
[PIPELINE s1 g1 wait] <what>: <why>; polling every <s> s, up to <span>; kept until accepted: <ids or none>; now carry out runs/S1/handover-file.md
```

To every target of `NUDGE_DEFAULT` (executor and Committee), at the end of the split:

```text
[PIPELINE s1 g1] <status>; report runs/S1/g1/report.md; facts <path or not made>; compute <x> of 840 min; kept until accepted: <k> files; now carry out runs/S1/handover-split.md
```

Every attempt is logged in `runs/<ST>/<split>/nudges.tsv`. A send that fails never stops the run. If the end line
reached no target, the script prints it for the user to pass on, and exits 1.

## How to adapt it

1. **Copy the files.** Copy `all_in_one.sh`, `pipe.py`, `download_one.sh`, `run_logged.py` and `verify_download.py`
   from here, and `fetch_dst.py` from `../download-ui/`, into `<project>/tools/`. You may rename them like e7
   (`s6_all_in_one.sh`, `s6_pipe.py`, `s6_download.sh`). Then change `WRAPPER`, `DOWNLOADER` and `PINS` in `pipe.py`,
   the driver's name in `all_in_one.sh`, and `tools/fetch_dst.py` in `download_one.sh`.
2. **The names.** In `pipe.py`, set `PROJECT`, `STEP_WORD`, `ST`, `SPLITS`, `ENV`, `TESTENV`, `DL_DRY_RUN`,
   `DL_CONTEXT`, `NUDGE_DEFAULT`, `FILE_NUDGE_DEFAULT`, `TEST_PREFIX`, `KEPT_WORD`, `OUTPUT_WORD`, `KEEP_STEP`, `PY`,
   `PREFLIGHT_IMPORTS`, `LONG_OK`, `JOB_MEM_MB`, `GROUP_NAMES` (each record's dataset), `TITLE` (the dashboard's
   title), `WORKERS` (files at once) and `DL_STATUS` (the downloader's status-file setting). The comments give e7's
   values. In `fetch_dst.py`, set `TITLE`, `WORKERS_SETTING` and `RECNAME`. In `download_one.sh`, set the prefix
   `PROJECT_DL_` and the Python.
3. **The work.**
   - `JOBS`: the jobs of one file after its download, in order. Each runs through `run_logged.py` and must exit 0.
     The first is the independent `verify_download.py`.
   - `TEMP_OUTPUTS`: what is deleted with the source after acceptance.
   - `KEPT_OUTPUTS`: what stays for good.
   - `END_JOBS` and `FACTS_JOB`: the end of the split.
   - A step name has no `-` in it, because a job id is `<split>-<file id>-<step>`. A command over 1800 s needs
     `LONG_OK`, the user's approval in the user's words.
   - Jobs of different files run at the same time (`WORKERS`). A job must not write a file that another file's job
     writes too, and `WORKERS` jobs of `JOB_MEM_MB` each must fit in memory. Where they do not, set `WORKERS = 1`.
4. **The splits.** For each split, write one list `runs/<ST>/splits/files-<split>.tsv` with the header
   `recid key size adler32 url`. A file's id is the first 8 characters of its key, and it must be unique. e7 cut
   its lists with its own `tools/s6_splits.py` (byte order, week-sized splits).
5. **The manager's standing orders.** Write `runs/<ST>/handover-file.md` and `runs/<ST>/handover-split.md`. The
   bridge lines tell the manager to carry them out.
6. **The pins.** Run `shasum -a 256 tools/<every tool the split runs> > tools/all_in_one.pins`. A run refuses
   (exit 2) when a pinned file changed, and a split whose tools changed while it ran ends `FAILED after the split
   (pins changed: …)`.

## The manager's side (as e7)

- **Accepting a file:** after its own independent check of a file, the manager appends a line to
  `runs/<ST>/<split>/accepted-files.tsv`. The first field is the 8-character id, separated by a tab. e7 writes
  `id`, `utc`, `by`, `basis`. The script then deletes that file's source, its `.part` files and its `TEMP_OUTPUTS`
  in the next deletion pass, each logged first in `runs/<ST>/<split>/deletions.tsv` (path, bytes, sha256, utc).
- **Accepting a split:** the manager adds a line `<split>` to `runs/<ST>/accepted.tsv`; until then the next split
  is refused (exit 4). Before the first split's pilot is accepted, with the line `<first split>-pilot`, that split
  pauses after its first finished file and stops at once if that file fails.
- **Holding:** `runs/<ST>/HOLD` stops the script before the next file, with nothing more deleted (`STOPPED (HOLD)`).

## Commands, settings, exit codes

```bash
cd /path/to/project && tools/all_in_one.sh g1          # run or resume split g1 (the user starts each split by hand)
cd /path/to/project && tools/all_in_one.sh status      # every split; no network; creates nothing
cd /path/to/project && tools/all_in_one.sh status g1   # one split, file by file: id, state, on disk, last job
```

Settings: `PROJECT_PIPE_NUDGE`, `PROJECT_PIPE_FILE_NUDGE`, `PROJECT_PIPE_POLL_S` (300), `PROJECT_PIPE_WAIT_H` (24),
`PROJECT_PIPE_CAP_MIN` (840), `PROJECT_PIPE_RETRY=1`, `PROJECT_PIPE_FLOOR_GIB` (10) and `PROJECT_PIPE_WORKERS` (4;
the `--test` modes use 1). The downloader adds `PROJECT_DL_WORKERS` (1, the connections of one download),
`PROJECT_DL_SPLIT` (8), `PROJECT_DL_MAX_ATTEMPTS` (10), `PROJECT_DL_REPORT_SECS` (auto), `PROJECT_DL_FILE_LINES` (8),
`PROJECT_DL_DRY_RUN=1`, `PROJECT_DL_CAFFEINATE=0` and `PROJECT_DL_PYTHON`. `pipe.py` sets `PROJECT_DL_CONTEXT` and
`PROJECT_DL_STATUS_FILE` for each download.

In the run folder `runs/<ST>/<split>/`, besides `report.md`, `files.tsv`, `nudges.tsv` and `deletions.tsv`:
`pipeline.log` (every line of the run), and for each file `<id>/download-screen.log` and `<id>/download-status.json`.

Exit codes:
- `0`: the split is DONE, or PAUSED after the pilot file, and the end line reached a target.
- `1`: stopped or failed; or the split ended `DONE, <n> file(s) failed: …`; or the end line reached no target.
- `2`: wrong usage, or a pinned tool changed.
- `3`: another copy is running, or the downloader's own 3.
- `4`: a gate refused the split.
- `5` (e6's): a wait reached its limit, either the disk space before a file or the manager's acceptance at the end of
  the split.
- `130`: Ctrl-C. No nudge is sent, and the same command resumes.

## Tests before real use

Run each in a copy of the project, with the bridge pointed away from live sessions (`PROJECT_PIPE_SANDBOX_SEND`, or
`HOME` set to a test folder whose `.claude/agy-bridge/send_to_tty.sh` only logs):

```bash
cd /path/to/project && for t in fail partial pilot cap disk error; do PROJECT_PIPE_SANDBOX_SEND=/path/to/fake-send.sh /usr/bin/python3 -I tools/pipe.py --test $t; done
cd /path/to/project && PROJECT_PIPE_SANDBOX_TEST_ROOT=/path/to/test-root PROJECT_PIPE_SANDBOX_FAKE=1 PROJECT_PIPE_SANDBOX_SEND=/path/to/fake-send.sh PROJECT_PIPE_POLL_S=1 PROJECT_PIPE_WAIT_H=0.001 /usr/bin/python3 -I tools/pipe.py tst1
cd /path/to/project && tools/all_in_one.sh status && tools/download_one.sh runs/<ST>/splits/files-g1.tsv downloads/try status
```

The second command reads the list `/path/to/test-root/files-tst1.tsv`. Its first run ends with exit 5, because the
acceptance wait runs out. Add ids to `runs/<ST>/pipeline-test/tst1/accepted-files.tsv` and run it again: the second
run deletes those files.

Then prove the screen before you say that the script has the format
([The Script Delivery Rule](../../rules/script-delivery/The_Script_Delivery_Rule.md), "How to capture"). The tests
above draw no frame worth checking: `--test` and `PROJECT_PIPE_SANDBOX_FAKE=1` download nothing. Make two captures from
the rule's test server and check both:
1. **Piped,** with the files downloading.
2. **In a terminal of 80 columns, through the wrapper the user runs, with the files already on disk.** This is the
   path of a real run whose data is there.

Both captures use 10 files (more than the workers) and jobs that take 20 s (`PROJECT_PIPE_SANDBOX_JOB_S`), so that
several files are in flight in every frame. Paste the commands and their output with the delivery:

```bash
T=$(mktemp -d /tmp/frame-test.XXXXXX)
/usr/bin/python3 -I ~/AI-management/general/rules/script-delivery/frame_test_server.py "$T/srv" --files 10 --kib 150 & SERVER=$!
until [ -s "$T/srv/files-tst1.tsv" ]; do sleep 0.2; done
printf '#!/bin/bash\necho "sent+enter to /dev/fake-$1"\n' > "$T/fake-send.sh"; chmod +x "$T/fake-send.sh"
cd /path/to/project
export PROJECT_PIPE_SANDBOX_TEST_ROOT="$T/srv" PROJECT_PIPE_SANDBOX_SEND="$T/fake-send.sh" PROJECT_PIPE_POLL_S=1 PROJECT_PIPE_WAIT_H=0.001 PROJECT_PIPE_SANDBOX_JOB_S=20
/usr/bin/python3 -I tools/pipe.py tst1 > "$T/capture-pipe.txt"
COLUMNS=80 LINES=30 script -q -c "env PROJECT_PIPE_TEST_TAG=disk tools/all_in_one.sh tst1" "$T/capture-pipe-80.txt"
~/AI-management/general/rules/script-delivery/check_frame.py --kind pipeline --complete "$T/capture-pipe.txt" "$T/capture-pipe-80.txt"
kill $SERVER
```

About these commands:
- Both runs end with exit 5, because nobody accepts the test files.
- The second run has a new run folder (`PROJECT_PIPE_TEST_TAG=disk`), so it starts the same 10 files again. The
  downloads are under the test server's folder and are already complete, so it moves 0 B.
- On macOS the `script` form is `script -q FILE COMMAND …`.
- The checker fails a terminal capture in which anything is printed between two frames, and a complete capture in
  which no frame shows a file in flight.
- A project that renamed its wrapper (as e7 did) puts its own name in place of `tools/all_in_one.sh`. The rule also
  gives the captures of the downloader alone.

### Checked on 2026-11-27

**Before the merge,** the driver matched e7 exactly:
- e7's own test modes (`--test fail|partial|pilot|cap|disk|error`), run on e7's `s6_pipe.py` and on this `pipe.py`
  with e7's names, gave identical screens, `files.tsv`, `nudges.tsv`, bridge messages and exit codes.
- `report.md` was identical except the two "Paths" lines.
- e7's fake-file flow was identical.
- The wrappers have e7's code line for line.

**After the merge,** in test projects with a local test server:
- **The standalone downloader** drew the merged frame (`STEP 1 of 1 group <set>`) within the terminal's width.
- **The pipeline:**
  - drew the frame with the run (`PROJECT download g1`, `STEP 1 of 2 group DatasetA`, both groups);
  - printed stamped report and deletion lines, `SUMMARY`, and one `nudge:` line per target;
  - ended the acceptance wait and a disk wait at their limits with exit 5;
  - finished a split as `DONE` with exit 0;
  - refused a split at the gate (exit 4);
  - printed `status g1` with the on-disk column.
- **HEALTH counted:**
  - failed attempts, against a closed port;
  - stalls dropped (1, matching the 1 stall line in `download.log`);
  - certificate events (3, against a local HTTPS server with a self-signed certificate; the row read `waiting
    (certificate)`);
  - `NETWORK DOWN? waiting, retrying` appeared with a 1-second window in a test copy.
- **e7's six test modes and the fake-file flow** ran with the expected statuses and exit codes.

**In the evening, after the user's words** (the split's dashboard and the workers), in test copies:
- **Unchanged behavior:**
  - The six test modes gave the same exit codes, statuses and `files.tsv` as the driver before the change.
  - The fake-file flow (3 files; 2 accepted, then deleted in the second run) gave the same statuses and deletions
    with 1 worker and with 3 workers, as before the change.
- **Captures,** each passed by `check_frame.py`:
  - The two captures of "Tests before real use", saved as the checker's fixtures. The piped one has 5 frames. The
    terminal one has 25 frames of 23 to 29 rows in a window of 30, redrawn in place.
  - In the second capture all 10 downloads found their file complete on disk, and the run moved 0 B. Its frames showed
    4 files processing at once, and `TOTAL`, `GROUPS` and `RECORDS` counting the finished files.
  - The same in a test copy whose `JOBS` had a 6-second job.
- **The old driver failed the new check:** run in a terminal of 80 columns, it printed 17 lines between its frames.
  The downloader alone, run in a terminal, passed.
- **Ctrl-C and resume:** Ctrl-C during two downloads at once ended with exit 130, and both partial files stayed.
  The same command then resumed both and ended as before.
- **Gates:**
  - A `HOLD` placed 1.5 s into a fake split of 6 files with 3 workers stopped it with `STOPPED (HOLD)`, after 3 files
    were DONE.
  - `--test partial` with 3 workers ran every file and ended `DONE, 1 file(s) failed: T2.root`.

## Differences from e7

The merged format, as the user chose it (guide §7):
- **The per-file lines** (`file report`, `FAILED`, `deleted`) carry e6's `[<utc>]` stamp.
- **Waits:** e7 printed `waiting for disk space …` or `end of the split: waiting …` every poll. Now a wait prints e6's
  `[<utc>] WAITING <what>: <why>` once, then the `WAITING` row, and sends one bridge line. e7 sent one only for disk.
- **At the end of the split,** e6's `SUMMARY` line comes before `nudge:`, `status:` and `report:`.
- **The bridge line per file** adds `step <i> of <n> group <G>` and the kept count. The end line adds `kept until
  accepted: <k> files` and goes to every target, where e7 stopped at the first that took it.
- **`status <split>`** adds the bytes on disk.
- **Exit 5** for a wait that reaches its limit. e7 used 1.
- **The download's dashboard** gets the run as `--context` (see `../download-ui/README.md`).
- **The screen and the workers** (the user, 2026-11-27, evening: "I need a stable UI refresh itself, not keep on
  outputing"):
  - e7 worked on one file at a time and printed every line, with the downloader's own frame drawn between them for
    each file.
  - Now the split has one dashboard of its own, for the whole split. On a terminal nothing else is printed until the
    end lines, and every line goes to `pipeline.log`.
  - `PROJECT_PIPE_WORKERS` files are worked on at once.
  - `GROUPS (done / total)` and `RECORDS` count the finished files of the whole split, where e7 showed the bytes
    moved and the one file being downloaded.

And, from before the merge, the removal of e7's own work:
- **e7's per-file jobs** (probe, the version-1 skim and its checks with e7's "rule C", re-check, menus, the lean skim
  and its checks, evaluation) are the table `JOBS`. The template has one job, `verify_download.py`.
- **e7's manifests** are not kept. A file's source sha256 for `deletions.tsv` comes from the download's `SHA256SUMS`;
  a deletion pass skips a file whose `SHA256SUMS` is missing and notes it.
- **e7's end-of-split analysis** (m1, m6, m6fit, m1cum) and facts are `END_JOBS` and `FACTS_JOB`. With `END_JOBS`
  empty there is no analysis stage, so no `FAILED at analysis` either.
- **The report's "Paths" section** names the template's folders.
- **A missing `runs/log.jsonl` or split list** reads as empty.
- **`status`** shows the configured compute cap. e7 printed `840`.
