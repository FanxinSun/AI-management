# Template: parallel threaded download with an in-place dashboard

> [!CAUTION]
> ## MANDATORY RULE (non-negotiable — user directive, 2026-11-24)
> Whenever a task requires delivering a download script for the user to run:
> 1. **You MUST deliver a runnable script** built by copying and adapting `fetch_dst.py` and `download_wrapper.sh` from this folder.
> 2. **NEVER** invent an ad-hoc `curl`/`wget`/`tqdm`/line-by-line `print` downloader, and **NEVER** drop the in-place `\033[<n>A\033[J` dashboard, the `<100`-column narrow layout, the `status` subcommand, the automatic default folder, HTTP Range resume, size/checksum verification, the `caffeinate`-safe single-instance guard, or exit codes `0`/`1`/`2`/`3`.
> 3. **Always test** through the exact launch wrapper (including `status` and `<100` col width) and place the **complete, exact, copy-paste-ready runnable command at the very end** of your closing message (Rule 14).
> 4. **Chain downstream processing when the task processes data (amended 2026-11-27):** `download-ui/` supplies the download/verify layer; whenever the dataset is to be skimmed, filtered, validated, or processed after download, follow [`CHUNKED_PIPELINE_GUIDE.md`](../../guides/chunked-pipeline-workflow/CHUNKED_PIPELINE_GUIDE.md) (`download -> verify -> process -> tool checks -> bridge line to Manager/Committee`), keeping raw files until Manager acceptance on bounded disk rather than stopping silently after `SHA256SUMS`. The script for that is built from [`../chunked-pipeline/`](../chunked-pipeline/README.md) (the split script).

Recorded 2026-11-27. On that day the user asked to "align the UI/format in the repo WITH WHAT e6/e7 ARE USING STRICTLY".
The user then chose, row by row, one merged format from e6's and e7's dashboards; the guide's §7 holds that table.
The files:
- `fetch_dst.py` is built from e7's downloader `tools/s2_fetch.py` (sha256
  `df2862667dd513eb416150cb787b3e9e0978882eb1e54676fcbbf8c39091fc18`, pinned in e7's `tools/s6_all_in_one.pins`). It
  needs only the standard library.
  - Its download code, start lines, end lines and exit codes are e7's.
  - Its dashboard is the merged one (below).
  - Its title (`TITLE`), the workers setting named in the start line (`WORKERS_SETTING`) and the record names
    (`RECNAME`) are constants.
  - `RECORDS`, `API`, `URL`, `EOS`, `eos_url()` and the `list` and `probe` subcommands are a project's too. e7 uses
    none of them: each file is taken from the `url` column of the list.
- `download_wrapper.sh` is e7's user-facing `tools/s2_download.sh`, with the project's names marked `PROJECT`. They
  are the sets, the list folder, the default folder, the settings' prefix (`PROJECT_DL_`, e7: `E7_S2_`) and the
  Python.

A pipeline calls the same downloader once per file through
[`../chunked-pipeline/download_one.sh`](../chunked-pipeline/download_one.sh) (e7's `tools/s6_download.sh`). It passes
the run as `--context`: the split, the file's step and group, and the run's totals.

## The interface (what the user sees and types)

- **Commands:**
  - `download_wrapper.sh` with no argument downloads the default set into the default folder (e7: set `step2` into
    `downloads/s2-miniaod-step2`).
  - `download_wrapper.sh SET`, `download_wrapper.sh SET DEST` and `download_wrapper.sh [SET] [DEST] status` pick
    the set and the folder. A relative DEST is taken from where the user stands. `status` shows what is done,
    partial, bad or missing, uses no network and creates nothing.
- **Settings**, as environment variables, all optional, with e7's defaults:
  - `PROJECT_DL_WORKERS` (1) and `PROJECT_DL_SPLIT` (8). A file over 64 MiB is fetched in that many byte ranges on
    as many connections.
  - `PROJECT_DL_MAX_ATTEMPTS` (10), `PROJECT_DL_REPORT_SECS` (auto), `PROJECT_DL_FILE_LINES` (8 or `all`),
    `PROJECT_DL_DRY_RUN`, `PROJECT_DL_CAFFEINATE` and `PROJECT_DL_PYTHON`.
- **The start lines** (e7) are `set <SET>: list <list>, folder <DEST>, <N> file(s) at once, <M> range(s) per file`
  (`download_one.sh`: `list <list>, folder <DEST>, …`). Then come `DOWNLOAD START UTC`, `DOWNLOAD ROOT`,
  `DOWNLOAD LOG`, `TOTAL FILES`, `TOTAL BYTES`, `ON DISK AT START` and `WORKERS: <N> (set <WORKERS_SETTING> to
  change); refresh every <s> s`.
- **The end lines** (e7) are:
  - `SHA256SUMS written for record <recid>: …`, `DOWNLOAD END UTC: …` and `done <n> of <N> files, <b> of <B> bytes;
    exit reason: …`;
  - then `DOWNLOAD COMPLETE`, or `DOWNLOAD INCOMPLETE (<reason>); rerun the script to resume. Details: …`, or, after
    Ctrl-C, `INTERRUPTED: partial files are kept. Rerun the script to resume.`
- **Ctrl-C is safe:** partial files are kept and the exit code is 130; a rerun resumes.
- **Exit codes:**
  - `0`: done, or an asked stop.
  - `1`: a failure, a block, give-ups or the network down.
  - `2`: usage, a foreign folder or a CA pin mismatch.
  - `3`: disk space, or another download on the folder.

## The dashboard (the merged e6/e7 format)

Redrawn in place (`\033[<n>A\033[J`) every 5 s on a terminal, printed every 30 s when piped. The source of each row
is in brackets:

```text
<TITLE> <run>  |  HH:MM:SS  |  elapsed HH:MM:SS  |  <N> workers  |  time-out <S> s                     [e6, plus e7's run name]
STEP     <i> of <n>  group <G>  |  downloading <a>, processing 0, finished <c> of <d> files             [e6]
THIS STEP <20-character bar> <p>%  moved <X> of <Y>                                                   [e6]
TO DOWNLOAD (estimate)  <X> in all   moved <Y>                                                        [e6]
TOTAL    <30-character bar> <p>%   <got> / <size>                                                     [e7]
FILES    <n>/<N> complete   <d> downloading   <w> workers alive                                       [e7]
SPEED    now <rate>   average <rate>   ETA HH:MM:SS                                                    [e7]
LINKS    <c> connections open   <rate> each   <s> stalled right now                                    [e7]
HEALTH   failed attempts <a>   stalls dropped <b>   certificate events <c>[   LASTERR <60 characters>][   NETWORK DOWN? waiting, retrying]   [e6]

GROUPS (moved / estimate)                                                                              [e6]
  <G>  <bar> <p>%  <d>/<n>   files  <moved> / <estimate>

RECORDS                                                                                                [e7]
  <recid> <name> <bar> <p>%   <d>/<n>   files   <got> / <size>

DOWNLOADING NOW (showing a of b, nearest to done first)                                               [e7, with e6's notes]
  <recid> <key> <bar> <p>%  <got> / <size>  <rate>  ETA HH:MM:SS[  retrying|  waiting (certificate)]

Ctrl-C stops cleanly; rerun resumes   |   log: <folder>/download.log                                  [both]
```

- **With a pipeline's `--context`:**
  - `<run>` is the split.
  - `STEP` is this file within the split; its group is the file's dataset, and `finished` counts the split's DONE
    files.
  - `TO DOWNLOAD (estimate)` and `GROUPS` cover the run: the split's files not DONE when the run started, and the
    bytes moved in this run.
- **Without `--context`:** the run is the list. The step is 1 of 1, the group is the set, and `GROUPS` lists the
  list's datasets.
- **This download only:** `THIS STEP`, `TOTAL`, `FILES`, `RECORDS` and the file rows.
- **`HEALTH`:**
  - it counts failed attempts, connections dropped for stalling, and certificate refusals (certificate checks are never
    switched off);
  - `LASTERR` is the last error's first 60 characters;
  - `NETWORK DOWN? waiting, retrying` appears after `DOWN_WINDOW` (900 s, e6's value) with no byte while attempts fail.
- **A file's row** ends in `retrying` after a failed attempt, or `waiting (certificate)` after a certificate refusal,
  until bytes flow again.
- **Widths:** every line is cut at the terminal's width minus one. Below 100 columns the record and group bars are 10
  characters, the file bars 6 and the names 14. Only the file lines shrink to fit the window's height (e7's rule; see
  pitfall 6). All detail goes to `<folder>/download.log`.

## The mechanics worth keeping

- **Workers:** N worker threads take files from a shared claim queue, one connection each. HTTP Range resume: a 206
  appends, a 200 restarts.
- **Byte ranges:** with `--split N`, a file over 64 MiB is fetched in N ranges (`<key>.part0` …), each on its own
  connection with the same resume, stall and 4xx rules. The ranges are joined into `<key>.part` and verified.
  - A server that answers a Range request with 200 is a block.
  - Do not change N while a folder holds range files: they are resumed at the wrong offsets, the checksum then
    fails, and the file is downloaded again.
- **Verification:** size, adler32 and sha256 are checked while streaming. A row goes to `fetch-log.tsv` only after
  verification. Failures are renamed `*.bad`, never deleted. `SHA256SUMS` is written when a record is complete.
- **Stalls:** a connection under a byte rate for a window is dropped and resumed. A file is given up on only after
  `--max-stalls` attempts in a row with no new bytes. If every connection fails, the run stops ("network seems down").
- **Soft budgets** (`--max-files`, `--max-seconds`) drain: they stop new claims but let running files finish.
- **Disk:** the check reserves the in-flight files' sizes, twice a split file's size while its ranges are joined.
  The lock is the folder `.download.lock`.
- **Certificates:** pinning with `--cafile` and `--cafile-sha256`; never an unverified SSL context.

## Pitfalls found (keep these tests)

1. **The single-instance guard.** The "another fetch is running" check read `ps` and counted its own `caffeinate`
   helper. `caffeinate -i CMD` execs CMD in the same PID and forks a helper CHILD that keeps the whole command line.
   - The guard must skip this process, every ancestor (job logger, `zsh -c "..."`) and every descendant, from one
     `ps -axo pid=,ppid=,command=` read.
   - It matches the script by its own file name (`os.path.basename(__file__)`), so a renamed copy keeps working.
   - Always test through the exact launch form of the wrapper, not only the bare Python.
2. **A status command must create nothing** (it once created DEST). Use the nearest existing parent for free space.
3. **A soft stop must not abort in-flight downloads** (separate stop and drain events).
4. **Terminals of 80 columns need the narrow layout,** or the speeds get cut.
5. **Make the first-run default folder automatic:** the user ran the wrapper with no argument and got usage.
6. **The frame's height.**
   - The frame limits the file lines to the terminal (`term_rows - len(head) - 6`, e7's rule, which the user kept)
     but not the other lines. A run with more records or groups than a short window holds draws a frame taller than
     the window. Then `\033[<n>A` stops at the top row and old lines stay in the scrollback.
   - e6's own dashboard shrinks in steps instead (guide §3).
   - This folder carried an adaptive RECORDS layout from 2026-11-22 (two columns or per group) that neither e6 nor e7
     runs. It was removed on 2026-11-27.
7. **e6's rows are long.** The `HEALTH` line with `LASTERR` is wider than 99 characters, so on a terminal of 100
   columns or fewer its end, `NETWORK DOWN?` included, is cut off. In 80 columns the ends of the title (`time-out …`)
   and of the `STEP` row are cut too. e6 cuts the same rows the same way.

## To reuse

1. Copy both files into `<project>/tools/`.
2. Change the project's parts: `TITLE`, `WORKERS_SETTING`, `RECNAME`, the sets, the list folder, the default folder,
   the settings' prefix and the Python. Change `RECORDS`, `API`, `URL`, `EOS`, `eos_url()` and `list`/`probe` only if
   you use them.
3. Keep the dashboard, the guard, resume, verification and the exit codes.
4. Re-run the tests above through the wrapper before real use.

When processing follows the download, take the driver from [`../chunked-pipeline/`](../chunked-pipeline/README.md).

### Checked on 2026-11-27

**Before the merge:**
- With e7's three names put back, the code of `fetch_dst.py` (docstrings and comments aside) was e7's `tools/s2_fetch.py`
  line for line.
- `download_wrapper.sh` has e7's `tools/s2_download.sh` code, except e7's set names and its refusal of retired sets.
- A live run of both copies against one local server gave the same start lines and the same frame layout.

**After the merge, with the template's own names:**
- **Through the wrapper:** `status` created nothing. The frame had every row above, `STEP 1 of 1 group set1`, and lines
  within the terminal's width.
- **In an 80×30 terminal** every frame line was at most 79 characters and the tallest frame 22 lines, with the narrow
  bars. Ctrl-C exited 130 with the `.part` files kept. The rerun resumed (`ON DISK AT START: 1 files complete,
  83886080 bytes of 167772160`) and finished with exit 0.
- **With a pipeline's `--context`:** `STEP 1 of 2 group DatasetA`, and both groups of the split.
- **`HEALTH`** counted:
  - failed attempts, against a closed port;
  - stalls dropped (1, matching the 1 stall line in `download.log`);
  - certificate events (3, against a local HTTPS server with a self-signed certificate; the file's row read `waiting
    (certificate)`).
- **`NETWORK DOWN? waiting, retrying`** appeared with a 1-second window in a test copy.
- **The row for a file waiting to retry** read `retry in 1 s  retrying`.
