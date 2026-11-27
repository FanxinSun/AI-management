# Template: the chunked all-in-one pipeline (the e7 split script)

> [!IMPORTANT]
> Whenever a download feeds processing (skim, filter, check), the Mandatory Repo-Read rule (§2, item 4) and
> [`CHUNKED_PIPELINE_GUIDE.md`](../../guides/chunked-pipeline-workflow/CHUNKED_PIPELINE_GUIDE.md) ask for one
> unattended, resumable script. Build it from these files together with [`../download-ui/`](../download-ui/README.md):
> copy, change the project's parts named below, keep the rest, and run the tests at the end before real use.

Recorded 2026-11-27 at the user's request: "align the UI/format in the repo WITH WHAT e6/e7 ARE USING STRICTLY".

These files are e7's split script (the user's project `e7-upsilon-omega`, step 6), with e7's own work taken out.
They are the versions pinned in e7's `tools/s6_all_in_one.pins` on 2026-11-27, the ones e7 is running. What the user
sees and what the manager receives are e7's:
- every line on the screen;
- every bridge line and `report.md`;
- `files.tsv`, `nudges.tsv`, `deletions.tsv` and `status.tsv`;
- the `status` command, the gates, the exit codes and the test modes.

The downloader inside it is [`../download-ui/fetch_dst.py`](../download-ui/fetch_dst.py), e7's `tools/s2_fetch.py`.

e6 (`e6-emu-below-z`) uses a different form: one continuous command reading branches in steps, with its own
dashboard. Use e6's form only for branch reads in steps. The guide describes its screen (§3); it is not a template here.

## Files

| File | e7's file (sha256, first 16) | What differs from e7's |
|---|---|---|
| `all_in_one.sh` | `tools/s6_all_in_one.sh` (`e2995a77b3b24443`) | the names of the driver and the splits in the usage line; the code is e7's |
| `pipe.py` | `tools/s6_pipe.py` (`027c887a06a0a57d`) | e7's names are constants; e7's jobs are the tables `JOBS`, `TEMP_OUTPUTS`, `KEPT_OUTPUTS`, `END_JOBS`, `FACTS_JOB` (see "Differences from e7") |
| `download_one.sh` | `tools/s6_download.sh` (`a45e5b97a00a2b84`) | the settings' prefix `PROJECT_DL_` (e7: `E7_S2_`), the Python, the downloader's file name; the code is e7's |
| `run_logged.py` | `tools/run_logged.py` (`b75a503480805fee`) | the docstring only |
| `verify_download.py` | `tools/s2_verify.py` (`1b00e42096f72c6a`) | e7's ROOT-file check (`b"root"`) is the constant `MAGIC` (`None`: no check) |

In a project they all go into `<project>/tools/`, next to `fetch_dst.py` from `../download-ui/`.

## The screen

From the template's own test (the pilot file of split `g1`, served by a local test server; the folder is shortened
to `/path/to/project`, and the frame shown is the second of three). With e7's names the same lines read `E7 download
…`, `[PIPELINE s6 g1 file] …`, `E7_S2_WORKERS`, as in e7's terminal:

```text
file AAAA1111 (1 of 2)
download AAAA1111 (83886080 bytes) into downloads/s1-g1/AAAA1111
list /path/to/project/runs/S1/g1/lists/AAAA1111.tsv, folder /path/to/project/downloads/s1-g1/AAAA1111, 1 file(s) at once, 8 range(s) per file
DOWNLOAD START UTC: 2026-11-27T08:20:07Z
DOWNLOAD ROOT: /path/to/project/downloads/s1-g1/AAAA1111
DOWNLOAD LOG: /path/to/project/downloads/s1-g1/AAAA1111/download.log
TOTAL FILES: 1
TOTAL BYTES: 83886080
ON DISK AT START: 0 files complete, 0 bytes of 83886080
WORKERS: 1 (set PROJECT_DL_WORKERS to change); refresh every 3 s
PROJECT download AAAA1111.tsv  |  16:20:10  |  elapsed 00:00:03  |  1 workers
TOTAL    ██████████████████████████░░░░  86.2%   68.94 MB / 80.00 MB
FILES    0/1 complete   1 downloading   1 workers alive
SPEED    now 22.90 MB/s   average 22.90 MB/s   ETA 00:00:00
LINKS    1 connections open   22.90 MB/s each   0 stalled right now
HEALTH   retries 0   errors 0

RECORDS
  81001             █████████████████░░░  86.2%     0/1   files   68.94 MB / 80.00 MB

DOWNLOADING NOW (showing 1 of 1, nearest to done first)
  81001 AAAA1111-big.root    ██████████████░░  86%   68.94 MB / 80.00 MB   22.90 MB/s  ETA 00:00:00

Ctrl-C stops cleanly; rerun resumes   |   log: /path/to/project/downloads/s1-g1/AAAA1111/download.l

SHA256SUMS written for record 81001: /path/to/project/downloads/s1-g1/AAAA1111/81001/SHA256SUMS
DOWNLOAD END UTC: 2026-11-27T08:20:11Z
done 1 of 1 files, 83886080 of 83886080 bytes; exit reason: all files done
DOWNLOAD COMPLETE
S2 g1-AAAA1111-verify start (limit 600 s) | compute 0.0 of 840 min
S2 g1-AAAA1111-verify exit 0 0.1 s | compute 0.0 of 840 min
file report DONE: delivered to 'PROJECT Committee': sent+enter to /dev/fake-PR
nudge: delivered to 'PROJECT executor': sent+enter to /dev/fake-PRO
status: PAUSED after the pilot file
report: runs/S1/g1/report.md
```

The rest of the screen, as e7 prints it:
- **On a terminal:**
  - The dashboard is redrawn in place every 5 s; when the output is piped, a frame is printed every 30 s.
  - A running job shows `S2 <job id> running N s | compute …` on one line, rewritten every 5 s.
  - When the job ends, that line is cleared with spaces, so a copied `exit` line ends in trailing spaces.
- **When a file fails:** `file <id> FAILED at <step>: its source and <KEPT_WORD> stay`, then `file report FAILED: …`.
- **In a deletion pass:** `deleted <path> (<bytes> bytes)`.
- **While waiting:** `waiting for disk space before <id>: …` and `end of the split: waiting for the manager's
  acceptance of <ids>`.

## How to adapt it

1. **Copy the files.** Copy `all_in_one.sh`, `pipe.py`, `download_one.sh`, `run_logged.py` and `verify_download.py`
   from here, and `fetch_dst.py` from `../download-ui/`, into `<project>/tools/`. You may rename them like e7
   (`s6_all_in_one.sh`, `s6_pipe.py`, `s6_download.sh`). Then change `WRAPPER`, `DOWNLOADER` and `PINS` in `pipe.py`,
   the driver's name in `all_in_one.sh`, and `tools/fetch_dst.py` in `download_one.sh`.
2. **The names.** In `pipe.py`, set `PROJECT`, `STEP_WORD`, `ST`, `SPLITS`, `ENV`, `TESTENV`, `DL_DRY_RUN`,
   `NUDGE_DEFAULT`, `FILE_NUDGE_DEFAULT`, `TEST_PREFIX`, `KEPT_WORD`, `OUTPUT_WORD`, `KEEP_STEP`, `PY`,
   `PREFLIGHT_IMPORTS`, `LONG_OK` and `JOB_MEM_MB`. Each comment gives e7's value. In `fetch_dst.py`, set `TITLE`,
   `WORKERS_SETTING` and `RECNAME`. In `download_one.sh`, set the prefix `PROJECT_DL_` and the Python.
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
   file reports and the end nudge tell the manager to carry them out.
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
cd /path/to/project && tools/all_in_one.sh status g1   # one split, file by file
```

Settings: `PROJECT_PIPE_NUDGE`, `PROJECT_PIPE_FILE_NUDGE`, `PROJECT_PIPE_POLL_S` (300), `PROJECT_PIPE_WAIT_H` (24),
`PROJECT_PIPE_CAP_MIN` (840), `PROJECT_PIPE_RETRY=1` and `PROJECT_PIPE_FLOOR_GIB` (10). The downloader adds
`PROJECT_DL_WORKERS` (1), `PROJECT_DL_SPLIT` (8), `PROJECT_DL_MAX_ATTEMPTS` (10), `PROJECT_DL_REPORT_SECS` (auto),
`PROJECT_DL_FILE_LINES` (8), `PROJECT_DL_DRY_RUN=1`, `PROJECT_DL_CAFFEINATE=0` and `PROJECT_DL_PYTHON`.

Exit codes:
- `0`: the split is DONE, or PAUSED after the pilot file, and the nudge was delivered.
- `1`: stopped or failed; or the split ended `DONE, <n> file(s) failed: …` or with files kept until accepted; or the
  nudge failed.
- `2`: wrong usage, or a pinned tool changed.
- `3`: another copy is running, or the downloader's own 3.
- `4`: a gate refused the split.
- `130`: Ctrl-C. No nudge is sent, and the same command resumes.

## Tests before real use

Run each in a copy of the project, with the bridge pointed away from live sessions (`PROJECT_PIPE_SANDBOX_SEND`, or
`HOME` set to a test folder whose `.claude/agy-bridge/send_to_tty.sh` only logs):

```bash
cd /path/to/project && for t in fail partial pilot cap disk error; do PROJECT_PIPE_SANDBOX_SEND=/path/to/fake-send.sh /usr/bin/python3 -I tools/pipe.py --test $t; done
cd /path/to/project && PROJECT_PIPE_SANDBOX_TEST_ROOT=/path/to/test-root PROJECT_PIPE_SANDBOX_FAKE=1 PROJECT_PIPE_SANDBOX_SEND=/path/to/fake-send.sh PROJECT_PIPE_POLL_S=1 PROJECT_PIPE_WAIT_H=0.001 /usr/bin/python3 -I tools/pipe.py tst1
cd /path/to/project && tools/all_in_one.sh status && tools/download_one.sh runs/<ST>/splits/files-g1.tsv downloads/try status
```

The second command reads the list `/path/to/test-root/files-tst1.tsv`. Run it once, add ids to
`runs/<ST>/pipeline-test/tst1/accepted-files.tsv`, and run it again: the second run deletes those files.

### Checked on 2026-11-27

- **e7's own test modes:** `--test fail|partial|pilot|cap|disk|error`, run on e7's `s6_pipe.py` and on `pipe.py`
  with e7's names (`TEMP_OUTPUTS` = e7's version-1 skim path), each in a fresh copy:
  - screen, `files.tsv`, `nudges.tsv` and every bridge message: identical, with only times and durations masked;
  - `report.md`: identical except the two "Paths" lines that name e7's own analysis outputs;
  - exit codes: identical.
- **e7's sandbox flow with made-up files** (`E7_S6_TEST_ROOT`, `E7_S6_FAKE=1`, one file failing; one run, two
  acceptances, a second run): screens of 31 and 16 lines, `files.tsv`, `nudges.tsv` and all 7 bridge messages
  identical; `deletions.tsv` held the same files and sizes.
- **The wrappers:** `download_one.sh` and `all_in_one.sh`, with e7's names, have e7's code line for line.
- **The template with its own names, in a test project with real downloads from a local server:**
  - the pilot pause, then the acceptance, then the deletion pass, then the next file, then the wait for
    acceptance; `DONE` exits 0, and a split with a kept file exits 1;
  - the gate refused the next split (exit 4);
  - `status` and `status g1` printed their tables;
  - through `../download-ui/download_wrapper.sh`, in an 80-column terminal, every frame line was at most 79
    characters; Ctrl-C exited 130 and kept the `.part` files; the rerun resumed from 52428800 bytes.

## Differences from e7

Only these. Each one either removes e7's own work or puts a project value in its place:

- **e7's per-file jobs** (probe, the version-1 skim and its checks with e7's "rule C", re-check, menus, the lean skim
  and its checks, evaluation) are the table `JOBS`. The template has one job, `verify_download.py`.
- **e7's manifests** (the version-1 and lean manifests and their combined copies) are not kept. A file's source sha256
  for `deletions.tsv` comes from the download's `SHA256SUMS`. A deletion pass skips a file whose `SHA256SUMS` is
  missing and writes a note in the report, as e7 does for a missing version-1 manifest.
- **e7's end-of-split analysis** (m1, m6, m6fit, m1cum) and facts are `END_JOBS` and `FACTS_JOB`. With `END_JOBS`
  empty there is no analysis stage, so no `FAILED at analysis` either.
- **The report's "Paths" section** names the template's folders, not e7's analysis outputs.
- **A missing `runs/log.jsonl`** reads as empty; e7's helper raised `FileNotFoundError`.
- **A missing split list** counts as zero files in `status`.
- **`status`** shows the configured compute cap; e7 printed `840`, its default.
