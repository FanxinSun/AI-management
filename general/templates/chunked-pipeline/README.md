# Template: the chunked all-in-one pipeline (the split script)

> [!IMPORTANT]
> Whenever a download feeds processing (skim, filter, check), the Mandatory Repo-Read rule (§2, item 4) and
> [`CHUNKED_PIPELINE_GUIDE.md`](../../guides/chunked-pipeline-workflow/CHUNKED_PIPELINE_GUIDE.md) ask for one
> unattended, resumable script. Build it from these files together with [`../download-ui/`](../download-ui/README.md):
> copy, change the project's parts named below, keep the rest, and run the tests at the end before real use.

Recorded 2026-11-27. On that day the user asked to "align the UI/format in the repo WITH WHAT e6/e7 ARE USING STRICTLY".
The user then chose, row by row, one merged format from e6's and e7's; the guide's §7 holds that table.

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
`tools/s2_fetch.py`. Each download gets the run as `--context`: the split, the file's step and group, and the run's
totals.

## Files

| File | Built from e7's (sha256, first 16) | What differs from e7's |
|---|---|---|
| `all_in_one.sh` | `tools/s6_all_in_one.sh` (`e2995a77b3b24443`) | the names of the driver and the splits in the usage line, and exit 5 in the header; the code is e7's |
| `pipe.py` | `tools/s6_pipe.py` (`027c887a06a0a57d`) | e7's names are constants; e7's jobs are tables (`JOBS`, `TEMP_OUTPUTS`, `KEPT_OUTPUTS`, `END_JOBS`, `FACTS_JOB`); the merged lines (see "Differences from e7") |
| `download_one.sh` | `tools/s6_download.sh` (`a45e5b97a00a2b84`) | the settings' prefix `PROJECT_DL_` (e7: `E7_S2_`), the Python, the downloader's file name, and `PROJECT_DL_CONTEXT` (passed on as `--context`) |
| `run_logged.py` | `tools/run_logged.py` (`b75a503480805fee`) | the docstring only |
| `verify_download.py` | `tools/s2_verify.py` (`1b00e42096f72c6a`) | e7's ROOT-file check (`b"root"`) is the constant `MAGIC` (`None`: no check) |

In a project they all go into `<project>/tools/`, next to `fetch_dst.py` from `../download-ui/`.

## The screen

From the template's own test: the pilot file of split `g1`, served by a local test server, in a 100-column terminal,
with the test's two records named `DatasetA` and `DatasetB`. The folder is shortened to `/path/to/project`, and the
frame shown is one from the middle of the download:

```text
file AAAA1111 (1 of 2)
download AAAA1111 (83886080 bytes) into downloads/s1-g1/AAAA1111
list /path/to/project/runs/S1/g1/lists/AAAA1111.tsv, folder /path/to/project/downloads/s1-g1/AAAA1111, 1 file(s) at once, 8 range(s) per file
DOWNLOAD START UTC: 2026-11-27T08:58:01Z
DOWNLOAD ROOT: /path/to/project/downloads/s1-g1/AAAA1111
DOWNLOAD LOG: /path/to/project/downloads/s1-g1/AAAA1111/download.log
TOTAL FILES: 1
TOTAL BYTES: 83886080
ON DISK AT START: 0 files complete, 0 bytes of 83886080
WORKERS: 1 (set PROJECT_DL_WORKERS to change); refresh every 1 s
PROJECT download g1  |  16:58:03  |  elapsed 00:00:02  |  1 workers  |  time-out 300 s
STEP     1 of 2  group DatasetA  |  downloading 1, processing 0, finished 0 of 2 files
THIS STEP ████████████░░░░░░░░  57.5%  moved 46.00 MB of 80.00 MB
TO DOWNLOAD (estimate)  83.00 MB in all   moved 46.00 MB
TOTAL    █████████████████░░░░░░░░░░░░░  57.5%   46.00 MB / 80.00 MB
FILES    0/1 complete   1 downloading   1 workers alive
SPEED    now 22.90 MB/s   average 22.90 MB/s   ETA 00:00:01
LINKS    1 connections open   22.90 MB/s each   0 stalled right now
HEALTH   failed attempts 0   stalls dropped 0   certificate events 0

GROUPS (moved / estimate)
  DatasetA ████████████░░░░░░░░  57.5%    0/1   files  46.00 MB / 80.00 MB
  DatasetB ░░░░░░░░░░░░░░░░░░░░   0.0%    0/1   files  0 B / 3.00 MB

RECORDS
  81001 DatasetA    ████████████░░░░░░░░  57.5%     0/1   files   46.00 MB / 80.00 MB

DOWNLOADING NOW (showing 1 of 1, nearest to done first)
  81001 AAAA1111-big.root    █████████░░░░░░░  57%   46.00 MB / 80.00 MB   22.90 MB/s  ETA 00:00:01

Ctrl-C stops cleanly; rerun resumes   |   log: /path/to/project/downloads/s1-g1/AAAA1111/download.l
SHA256SUMS written for record 81001: /path/to/project/downloads/s1-g1/AAAA1111/81001/SHA256SUMS
DOWNLOAD END UTC: 2026-11-27T08:58:04Z
done 1 of 1 files, 83886080 of 83886080 bytes; exit reason: all files done
DOWNLOAD COMPLETE
S2 g1-AAAA1111-verify start (limit 600 s) | compute 0.0 of 840 min
S2 g1-AAAA1111-verify exit 0 0.1 s | compute 0.0 of 840 min
[2026-11-27T08:58:05Z] file report DONE: delivered to 'PROJECT Committee': sent+enter to /dev/fake-
[2026-11-27T08:58:05Z] SUMMARY: files finished in this run 1 of 2, failed 0, moved 80.00 MB, kept
  until accepted 1; PAUSED after the pilot file
nudge: delivered to 'PROJECT executor': sent+enter to /dev/fake-PRO
nudge: delivered to 'PROJECT Committee': sent+enter to /dev/fake-PR
status: PAUSED after the pilot file
report: runs/S1/g1/report.md
```

Where the numbers come from:
- **`STEP`:** one file of the split, with the split's DONE files counted in `finished`. The group is the file's
  dataset, from `GROUP_NAMES`.
- **`TO DOWNLOAD (estimate)` and `GROUPS`:** the run, meaning the split's files that were not DONE when this run
  started, and the bytes moved in this run.
- **`THIS STEP`, `TOTAL`, `FILES`, `RECORDS` and the file rows:** this download.

The rest of the screen:
- **On a terminal:**
  - The frame is redrawn in place every 5 s; when the output is piped, a frame is printed every 30 s.
  - A running job shows `S2 <job id> running N s | compute …` on one line, rewritten every 5 s, then cleared with
    spaces, so a copied `exit` line ends in spaces.
  - The e6 lines (`[<utc>] WAITING …`, `[<utc>] SUMMARY: …`) wrap at the terminal's width, as e6 does. The other lines
    are cut there, as e7 does.
- **When a connection fails:**
  - `HEALTH` counts failed attempts, stalls dropped and certificate events, and adds `LASTERR <first 60 characters>`.
  - After 900 s with no byte while attempts fail, it adds `NETWORK DOWN? waiting, retrying`.
  - The file's row ends in `retrying` or `waiting (certificate)`.
- **When a file fails:** `[<utc>] file <id> FAILED at <step>: its source and <KEPT_WORD> stay`, then
  `[<utc>] file report FAILED: …`.
- **In a deletion pass:** `[<utc>] deleted <path> (<bytes> bytes)`.
- **A wait** (disk space before a file, or the manager's acceptance at the end of the split):
  - once, `[<utc>] WAITING <what>: <why>`;
  - then the row `WAITING  <what>  since HH:MM:SS  next check in <s> s`, rewritten every 5 s on a terminal and
    printed once per poll when piped;
  - at its limit, exit 5.

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
   `PREFLIGHT_IMPORTS`, `LONG_OK`, `JOB_MEM_MB` and `GROUP_NAMES` (each record's dataset). The comments give e7's
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
`PROJECT_PIPE_CAP_MIN` (840), `PROJECT_PIPE_RETRY=1` and `PROJECT_PIPE_FLOOR_GIB` (10). The downloader adds
`PROJECT_DL_WORKERS` (1), `PROJECT_DL_SPLIT` (8), `PROJECT_DL_MAX_ATTEMPTS` (10), `PROJECT_DL_REPORT_SECS` (auto),
`PROJECT_DL_FILE_LINES` (8), `PROJECT_DL_DRY_RUN=1`, `PROJECT_DL_CAFFEINATE=0` and `PROJECT_DL_PYTHON`.
`PROJECT_DL_CONTEXT` is set by `pipe.py` for each download.

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
