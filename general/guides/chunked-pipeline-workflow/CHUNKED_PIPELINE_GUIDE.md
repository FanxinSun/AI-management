# Chunked Download–Process–Delete Pipeline Guide (AI-Free Execution)

Recorded on **2026-11-25** and updated on **2026-11-26** from the two production pipelines developed by **e6 Committee** (`~/e6-emu-below-z`, `claude:57721`) and **e7 Committee** (`~/e7-upsilon-omega`, `claude:90804`), reflecting **per-file manager acceptance before deletion** (E7 D21 / E6 D23). Updated on **2026-11-27**: e6's and e7's screens are recorded from their code (§3, §4), and the templates carry the merged format that the user chose from the two (§7).

> [!IMPORTANT]
> **Templates (2026-11-27).** Build a pipeline from [`general/templates/chunked-pipeline/`](../../templates/chunked-pipeline/README.md)
> (e7's split script: driver, wrapper, per-file downloader, job logger, independent verify) and
> [`general/templates/download-ui/`](../../templates/download-ui/README.md) (the downloader). They are built from e7's
> files as e7 runs them (the versions pinned in e7's `tools/s6_all_in_one.pins`), with e7's project names turned into
> constants and e7's physics jobs turned into tables.
> - **Before the merge** the templates matched e7 exactly. This was checked on 2026-11-27 by running e7's own test
>   modes on e7's driver and on the template with e7's names: the outputs were identical.
> - **The merge:** the user then chose, row by row, one format from e6's and e7's. The templates carry that merged
>   format (§7). e6 and e7 themselves were not changed.

---

## 1. Purpose & Core Pattern

When processing hundreds of gigabytes to multiple terabytes of remote datasets on bounded local disk over many hours or days, keeping an AI session in the loop burns tokens, hits context/usage limits, and risks unlogged edits.

The **Chunked All-in-One AI-Free Pipeline** moves all downloading, processing, checking, and deletion into an unattended, resumable script that the **user starts by hand**, while keeping an **independent manager acceptance gate before any irreversible deletion**:

```text
[User starts/resumes one command]
   │
   ▼  (AI-free loop, file by file)
download file ──► verify ──► process / skim ──► tool checks ──► one bridge line to Manager/Committee
                                                                         │
      ┌──────────────────────────────────────────────────────────────────┘
      ▼  (Manager runs independent filecheck tool offline/logged)
   [PASS] ──► Manager appends row to accepted-files.tsv ──► next script deletion pass logs & deletes raw files
   [FAIL] ──► Manager writes HOLD; downloads stay untouched; script stops cleanly before next file
```

**Core principles:**
1. **Bounded disk with two-stage accept-then-delete:** each file is verified, reduced to a compact kept output (skim/book/results), and kept on disk only until the Manager's independent check accepts that file (typically 1–2 files / 10–70 s or one file-cycle overlap on disk).
2. **AI-free execution:** downloading, processing, automated checks, deletion passes, analysis, and report generation run unattended under `caffeinate -i`.
3. **Human-started, resumable:** every run is launched by the user with one command (no AI session starts splits/downloads unless explicitly approved). `Ctrl-C` exits `130` cleanly; rerunning the exact same command resumes.
4. **Independent verification before removal:** per-file automated checks run inside the script, and the Manager/Committee re-derives/verifies each file using independent code before appending its ID to `accepted-files.tsv`.

---

## 2. Two Production Variants Side by Side

| Dimension | **E6 (`e6-emu-below-z`) — Continuous Multi-Step Driver** | **E7 (`e7-upsilon-omega`) — Explicit Large-Split Driver** |
|---|---|---|
| **Dataset scale** | 359 NanoAOD files (357.5 GB source; **38.65 GB** branch-read over HTTPS) | 556 remaining MINIAOD files (**2.00 TB** source; ~55 days at 0.42 MB/s) |
| **Chunking unit** | **27 consecutive steps** of ~2.0 GB estimated download each (default **8,000-entry** read steps, D22; optional soft stop `--steps N`) | **8 user-started large splits** (`g1..g4`, `h1..h4`, 60–80 files / 232–267 GB each, cut by `s6_splits.py`) |
| **Granularity of delete** | **Per file, after Committee acceptance (D23):** `deletion_pass` runs at start, pre-step, every 60 s, and at end for files in `CTL/accepted-files.tsv` | **Per file, after Manager acceptance (D21):** `deletion_pass` runs at start of each file, every 300 s wait poll, and at split end for `DONE` files in `accepted-files.tsv` |
| **Kept footprint** | 1–2 files at a time until accepted (deleted 10–70 s after acceptance); skims/books on external disk | ~2 sources + v1 skims (2.7–4.2 GB + 0.48–0.68 GB each) until prompt acceptance; lean skim (6.8% of v1) on internal Mac disk |
| **Entry point** | `tools/e6_download_kplus.sh` → `tools/e6_fetch_kplus.py` + `tools/e6_follow.py` | `tools/s6_all_in_one.sh <split>` → `tools/s6_pipe.py` + `tools/s6_download.sh` (`s2_fetch.py`) |
| **Downloader base** | Its own branch-read fetcher, built to the `general/templates/download-ui/` rules (in-place dashboard, `<100`-col layout, `status`, Range resume, lock, `caffeinate`), with its own dashboard (§3) | Calls `tools/s6_download.sh` (`tools/s2_fetch.py`) per file; since 2026-11-27 these are the templates `chunked-pipeline/download_one.sh` and `download-ui/fetch_dst.py` |
| **Governance gates** | `CTL = runs/E6-6/read-control/` (`accepted-files.tsv`, `accepted-groups.tsv`, `HOLD`); `steps-plan.tsv` matches `runs/E6-6/e6-6-8-steps.tsv`; group gate (M3 milestone required before next group) | SHA-256 pins on 25 tools (`s6_all_in_one.pins`); `g1` pilot pause; `accepted-files.tsv`, `accepted.tsv`, `HOLD` (exit 4); next split refuses while an earlier split keeps files |
| **Waking AI** | **Per-file + event bridge lines** (`[E6 READ file\|wait\|stop]`) to `"e6 Committee"` via installed bridge (failed send never stops run) | **Per-file + end-of-split bridge lines** (`[PIPELINE s6 <split> file]` to `"e7 Committee"`, end nudge to `"e7 executor,e7 Committee"`) via `~/.claude/agy-bridge/send_to_tty.sh` (`timeout=180`, caught) |

**When to choose which:**
* **E6 pattern** fits when a single continuous command should walk through many medium chunks (~2 GB each), reading selected branches with indefinite network/TLS retries and Committee checks (`C1–C7`) per file and per group milestone.
* **E7 pattern** fits when total download spans weeks across very large files (multi-GB each) on tight internal disk: cutting into week-sized user-started splits (`g1..h4`), deleting source + v1 skim per file only after `s6_mgr_filecheck.py` (`F1–F7`) acceptance, and polling up to 24 h for disk/acceptance instead of failing.

---

## 3. E6 Production Pattern (`e6-emu-below-z`)

1. **Wrapper, Read Sizing (D22), & UI (`tools/e6_download_kplus.sh` → `e6_fetch_kplus.py`):**
   * Built to `general/templates/download-ui/` rules: no-arg default run, `status` mode (no network, creates nothing), in-place `\033[<n>A\033[J` dashboard, `<100`-column narrow layout, `caffeinate -i`, single-instance `.download.lock` + `ps` guard.
   * **Smaller multi-range read requests (D22):** 50,000-entry requests (~13 MB) stalled/cut after 60–120 s, whereas **8,000-entry default steps** (`--step`; `E6_KPLUS_STEP_ENTRIES`, ~1–2 MB) finish reliably in 15–25 s. Failed network wait is **15 s**; certificate mismatch wait stays **600 s**.
   * **Estimated download vs source size:** displays only the branch-read bytes (~11.8% data, ~10.58% sim), never the raw 357.5 GB source size.
2. **Per-file accept-then-delete loop (D23):**
   * **Pipeline:** download file → process (`skim` + `book`) → tool's own checks → send one bridge line `[E6 READ file] ...; kept until accepted: <k> files; Committee: check per runs/E6-6/handover-file.md` to `e6 Committee`.
   * **Independent Committee check (`tools/e6_committee_filecheck.py`, `0.8–28 s` wall):** runs logged under `run_logged.py` and checks:
     * **C1:** all inputs found;
     * **C2:** download size and SHA-256 equal manifest's;
     * **C3:** entries equal source's;
     * **C4:** skim equals preselected download branch by branch with equal branch sets;
     * **C5:** weights and `Runs` tree agree;
     * **C6:** list K re-derived by `e6_committee_rederive_k2.py`;
     * **C7:** exact Poisson tail test of list-K yield against the group's other files (`poisson.sf(k - 1, mu)` upper tail, `poisson.cdf(k, mu)` lower tail; `FAIL` below `norm.sf(5)` = `2.8665e-7`).
   * **Control folder (`CTL = runs/E6-6/read-control/`, written only by Committee):**
     * `PASS`: appends row (`utc`, `file`, `tool_tag`) to `CTL/accepted-files.tsv`.
     * `FAIL`: writes one-line `CTL/HOLD`; download stays and read stops with exit `4` before the next file.
   * **`deletion_pass` (`tools/e6_fetch_kplus.py`):** runs at start, before each step, every 60 s, and at end (never under `HOLD` or while `e6_follow.py` runs, and with zero network needed). For each kept file listed in `accepted-files.tsv`: verifies SHA-256 equals manifest `output_sha256` (otherwise logs `"NOT DELETED"` once and keeps), appends `deleted.tsv`, and removes the file.
   * **Group gate & follow-up (`tools/e6_follow.py`):** a new group starts only once all prior groups appear in `CTL/accepted-groups.tsv` (after Milestone M3) with zero kept files. Disk, group-gate, and end waits poll every **300 s** (`--poll-seconds`) up to **24 h** (`--wait-limit 86400`, exiting `5`). `e6_follow.py` accepts each file either as `deleted` (in `deleted.tsv` and gone) or `kept` (exact recorded size).
3. **Resilience & library traps:**
   * **Hidden library network calls:** `uproot`'s `HTTPSource.num_bytes` sends an HTTP `HEAD` outside the caller's retrying wrapper; E6 moves the size request inside `Ctx.open()` so TLS/network retry logic covers it too.
   * **Retries & hard stops:** transient network/HTTP errors (15 s wait) and TLS cert hostname mismatches (refused, logged to `cert-events.tsv`, 600 s wait, cert verification **never** disabled) retry without limit. Only HTTP `403`/`429`, failed checks, `HOLD` (`4`), 24 h wait limit (`5`), and `Ctrl-C` (`130`) stop the run.
4. **Screen** (recorded 2026-11-27 from `tools/e6_fetch_kplus.py`, its `render()` and its report lines; e6's own layout, not the template's):
   * **The frame** is redrawn in place (`\033[<n>A\033[J`), every 5 s on a terminal and every 30 s when piped. Before a line is printed, the frame is erased, and it is drawn again below the line. Lines in `[...]` appear only in that state:
     ```text
     E6 K+ read in steps  |  HH:MM:SS  |  elapsed HH:MM:SS  |  <N> workers  |  time-out <S> s
     STEP     <n> of <N>  group <G>  |  downloading <a>, processing <b>, finished <c> of <d> files
     [WAITING  <what>  since HH:MM:SS  next check in <s> s]
     [PHASE    follow-up (<phase>) running HH:MM:SS]
     THIS STEP <20-character bar> <p>%  moved <X> of ~<Y>
     TO DOWNLOAD (estimate)  <X> in all   moved <Y>
     TOTAL    <30-character bar> <p>%   ETA HH:MM:SS
     SPEED    last 60 s <rate>   since start <rate>
     KEPT     <X> kept so far   <Y> held by this step (downloads not yet deleted)
     HEALTH   failed attempts <a>   stalls dropped <b>   certificate events <c>[   LASTERR <text>][   NETWORK DOWN? waiting, retrying]

     GROUPS (moved / estimate)
       <G>    <bar> <p>%  <d>/<n>   files  <moved> / <estimate>

     IN PROGRESS (showing <a> of <b>)
       <G>    <name> <bar> step <i>/<n>  <bytes>[  retrying|  waiting (certificate)]

     Ctrl-C stops cleanly; rerun resumes   |   log: <folder>/download.log
     ```
   * **Widths:** a file being processed shows `processing` in place of `step <i>/<n>`. Below 100 columns the group bars are 10 characters, the file bars 6 and the names 14 (else 20, 16 and 20), and every line is cut at the width minus one.
   * **The frame never gets taller than the window.** e6 draws the first of these that fits:
     1. the full frame;
     2. the frame with 2 file lines;
     3. compact groups (`GROUPS: G 12%  H 40%  …`, wrapped) with 2 file lines;
     4. compact groups with 1 file line and no foot line;
     5. compact groups only;
     6. the top lines only;
     7. three lines: the title, `TO DOWNLOAD (estimate) <X>, moved <Y>  <12-character bar> <p>%` and
        `STEP <n> of <N>  <done>/<all> files  |  <rate>  ETA <eta>`;
     8. one line rewritten in place: `E6 K+ step <n>/<N>  <p>%  moved <X> of ~<Y>  <rate>  ETA <eta>`.
   * **Screen lines around the frame:** `[<utc>] WAITING <what>: <why>`, and at the end `[<utc>] SUMMARY: steps finished in this run <a> of <b>, files processed <c>, failed <d>, moved <X>, kept <Y>, <h> h; …`. Then `DOWNLOAD COMPLETE`, or `NOT COMPLETE (<reason>); rerun the wrapper to continue. Details: <folder>/download.log`.
   * **Bridge lines to `e6 Committee`:**
     * after each file: `[E6 READ file] <file> step <n> group <G> PROCESSED: entries <e>, skim <s>; step <n>: <a> of <b> files processed; kept until accepted: <k> files; failed: <files or none>; Committee: check per runs/E6-6/handover-file.md`
     * a failed file: `… FAILED: <message>; its download stays; …`
     * a wait: `[E6 READ wait] <what>: <why>; polling every <s> s, up to <span>`
     * at the end: `[E6 READ stop] <reason>; kept until accepted: <k> files`

---

## 4. E7 Production Pattern (`e7-upsilon-omega`)

1. **Splitting (`tools/s6_splits.py`) & Wrapper (`tools/s6_all_in_one.sh`):**
   * Cuts remaining files in byte order into 8 week-sized splits (`g1..g4`, `h1..h4`) in `runs/S6/splits/`.
   * `tools/s6_all_in_one.sh <split>` runs `exec caffeinate -i /usr/bin/python3 -I tools/s6_pipe.py <split>` (stdlib only); `status [split]` shows `DONE kept` / progress with no network and creates nothing.
   * Every job after the download (verify to eval, the analysis, the facts) runs through `tools/run_logged.py` (`runs/log.jsonl`), enforcing the per-split compute cap (`840 min`). The download itself runs as `tools/s6_download.sh`, outside the logger.
2. **Per-file lifecycle & manager acceptance (`s6_pipe.py`, D21):**
   * Space check → download into `downloads/s6-<split>/<id>/` → verify (size, adler32, SHA-256) → probe → full v1 skim (`data/s6/v1tmp`) → 8 v1 checks → manager independent `recheck1` → trigger-menu check → lean v2 skim (`data/s6/lean`, 6.8% of v1) → lean checks (K1–K7 + bit-for-bit `mgrlean`) → `eval` (E1–E9) → **record lean manifest + `DONE` while keeping source and v1 skim on disk**.
   * **Per-file report:** sends one bridge line to `e7 Committee` (`E7_PIPE_FILE_NUDGE`, logged in `runs/S6/<split>/nudges.tsv`) using `~/.claude/agy-bridge/send_to_tty.sh` with `timeout=180` inside `try/except (OSError, subprocess.TimeoutExpired)`:
     ```text
     [PIPELINE s6 <split> file] <id> DONE (<p> of <n> passed); kept until accepted: <ids or none>; failed waiting: <ids or none>; now carry out runs/S6/handover-file.md
     ```
     Failed files report `FAILED at <step>, its source stays` and retain all `.part` files, sources, and v1 skims intact (`STOPPED, 3 failed files waiting` at 3 failures).
   * **Manager independent check (`tools/s6_mgr_filecheck.py SPLIT ID`, ~2 s wall):** shares zero code with `s6_pipe.py` and reads **no event data** (preserving blinding). Checks **F1–F7**: listed once, latest state `DONE`, latest attempt of all 10 jobs exited `0` (or documented rule-C `check1` diagnosis), verdict files agree, unique lean row matches size/SHA-256, source SHA-256 matches across `fetch-log`/`SHA256SUMS`/v1/lean, and state is cleanly `kept` or `deleted` (never `mixed`). Writes `filecheck.json` atomically and appends `runs/S6/<split>/accepted-files.tsv` (`id`, `utc`, `by`, `basis`) on `PASS`.
   * **`deletion_pass`:** runs at the start of each file (after `HOLD` check, before space check), in every 300 s wait poll, and at split end for `DONE`, kept, and accepted files: writes `deleted-after-lean` to v1 manifest, logs path/bytes/SHA-256 to `deletions.tsv` with `os.fsync`, and deletes source, `.part`, and `v1tmp` skim.
3. **Waits, gates, & end of split:**
   * **Disk & end waits instead of failure:** when free space `< size + E7_PIPE_FLOOR_GIB (10)` or any `DONE` file remains kept at split end, polls every `E7_PIPE_POLL_S` (`300 s`) for up to `E7_PIPE_WAIT_H` (`24 h`): `HOLD` check → deletion pass → re-check. Exceeding 24 h stops cleanly (`STOPPED ...`).
   * **Gates (exit `4`):** `runs/S6/HOLD` stops immediately (`STOPPED (HOLD)`) with nothing more deleted; next split refuses if any prior split still keeps files or lacks `runs/S6/accepted.tsv`; `g1` pauses after its first finished file for `g1-pilot` acceptance.
   * **End nudge & standing orders:** runs `m1`, `m6`, `m6fit`, `m1cum`, `s6_facts.py`, writes `report.md` (with `source` column `kept|deleted|-`) and `status.tsv`, and sends `[PIPELINE s6 <split>] ... now carry out runs/S6/handover-split.md`. Neither `handover-file.md` nor `handover-split.md` starts/resumes splits or deletes files manually.
   * **Atomic driver swap under pins:** edit a copy (`tools/s6_pipe_next.py`), test in offline sandbox, manager verifies diff/outputs, replace via `mv`, stage pins as `.partial` → `mv` → `shasum -a 256 -c`, then user presses `Ctrl-C` and re-runs the same command to resume mid-download `.part` files cleanly.
4. **Screen** (recorded 2026-11-27 from `tools/s6_pipe.py` and `tools/s2_fetch.py`; the templates' lines differ where §7 chose e6's form or a merge):
   * **One file:**
     ```text
     file <id> (<i> of <n>)
     download <id> (<bytes> bytes) into downloads/s6-<split>/<id>
     list <list>, folder <folder>, 1 file(s) at once, 8 range(s) per file
     DOWNLOAD START UTC: …   DOWNLOAD ROOT: …   DOWNLOAD LOG: …   TOTAL FILES: …   TOTAL BYTES: …   ON DISK AT START: …   WORKERS: … (one line each)
     E7 download <list name>  |  HH:MM:SS  |  elapsed HH:MM:SS  |  <N> workers      (the download-ui dashboard, redrawn in place)
     SHA256SUMS written for record <recid>: …   DOWNLOAD END UTC: …   done <n> of <N> files, …; exit reason: …   DOWNLOAD COMPLETE (one line each)
     S2 <split>-<id>-verify start (limit 600 s) | compute <x> of 840 min
     S2 <split>-<id>-verify exit 0 <t> s | compute <x> of 840 min
     …  (S3 probe and skim1, S4 check1, S5 recheck1, S7 menus, S6 lean, leancheck, mgrlean and eval, the same two lines each)
     file report DONE: <the send result, cut at 60 characters: delivered to 'e7 Committee': sent+enter to /dev/ttysNNN>
     deleted <path> (<bytes> bytes)                                          (in a deletion pass, one line per path)
     ```
   * **On a terminal** a running job's line `S<k> <job id> running <s> s | compute …` is rewritten every 5 s and cleared
     with spaces when the job ends, so a copied `exit` line ends in spaces.
   * **A failed file:** `file <id> FAILED at <step>: its source and version-1 skim stay`, then `file report FAILED: …`.
   * **The end:** `nudge: delivered to '<target>': …`, `status: <status>` and `report: runs/S6/<split>/report[-<n>].md`.
     After Ctrl-C: `interrupted: the job's group was ended; a rerun resumes`.
   * **`status`:** one line per split, `<split>  status: <status> files DONE <a> of <b>, kept <k>, failed <f>; compute
     <x> of 840 min`, then `accepted by the manager: …`, `hold: …`, `pins: …` and `free space: …`. `status <split>`
     prints one line per file under the header `id  state  last job`.

---

## 5. Reusable Blueprint & Non-Negotiable Invariants

When designing a new chunked all-in-one pipeline in any project:

1. **Downloader UI compliance:** follow [`general/templates/download-ui/README.md`](../../templates/download-ui/README.md) (`fetch_dst.py` + `download_wrapper.sh`: in-place `\033[<n>A\033[J` dashboard, `<100`-col layout, `status` creates nothing, automatic default folder, `caffeinate -i`, single-instance lock, HTTP Range resume, size/checksum verification). **Build the driver from [`general/templates/chunked-pipeline/`](../../templates/chunked-pipeline/README.md)** (the split script): it already has the merged screen of §7, the bridge lines, report, status, waits, gates and exit codes, and invariants 2 to 6 below.
2. **Accept-then-delete + audit log:**
   * Never delete raw downloads until automated checks pass **and** the Manager/Committee's independent check records that file in `accepted-files.tsv` (and verify manifest SHA-256 matches before `os.remove`).
   * Never delete when a `HOLD` file exists; stop cleanly (`exit 4`) with nothing more deleted.
   * Log full path, byte size, SHA-256, and UTC timestamp to `deletions.tsv` / `deleted.tsv` (`flush` + `os.fsync`) **before** calling `os.remove`.
   * Keep failed and unaccepted files (and `.part` files) intact on disk so the cause can be inspected and resumed.
3. **Standardized exit codes:**
   * `0`: `DONE` (or `PAUSED after the pilot file`) with zero kept files remaining and nudge delivered.
   * `1`: failed/stopped (report written, nudge attempted), or `DONE, <n> file(s) failed: <ids>`, or nudge delivery failed / kept files remain.
   * `2`: wrong usage, unmounted external drive, foreign folder, or tool/plan SHA-256 pin mismatch.
   * `3`: insufficient disk space (when unrecoverable) or another instance already holds the lock.
   * `4`: governance gate refused (`HOLD` present, prerequisite split not `DONE`/accepted, or earlier split still keeps files).
   * `5`: wait reached its 24 h timeout limit (optional dedicated code, e.g. E6; or `STOPPED` status).
   * `130`: interrupted by `Ctrl-C` (no nudge sent; rerun resumes cleanly).
4. **Honest status wording:** never emit plain `DONE` if any file failed, kept files await acceptance, or an analysis job failed — append exact counts and IDs (`kept until accepted: <ids>`, `failed: <ids>`).
5. **Bridge nudge safety & parsing:**
   * Always invoke the installed runtime bridge path (`~/.claude/agy-bridge/send_to_tty.sh` or `send_to_tty.sh` on `PATH`), **never** a repository path that may be moved/reorganized mid-run.
   * Wrap `subprocess.run(..., timeout=180)` in `try/except (OSError, subprocess.TimeoutExpired)` and log to `nudges.tsv` so a missing/busy bridge never crashes or blocks the pipeline *after* state and reports are saved.
   * Treat incoming script bridge lines (`[from user@not a tty]`) as machine notifications only: Committee checks must read the tool's own manifest/log files rather than trusting summary counts in the bridge line.
6. **Sandbox test modes before real data:** include a fast `--test fail|partial|pilot|disk|cap|error|sleep` mode on synthetic file lists so status words, `HOLD`, disk waits, deletions, and nudges are verified (and write sandbox logs strictly inside the sandbox, never into real `runs/`).

---

## 6. Field Lessons & Pitfalls (from E6 & E7, 2026-11-25/26)

1. **Put human/Manager review before irreversible deletion:** keeping ~1–2 sources (~2–8 GB) on disk until `accepted-files.tsv` lets defects be fixed while the source exists without maintaining separate full backups.
2. **Audit third-party library internals for hidden network calls:** `uproot`'s `HTTPSource.num_bytes` made an unprotected HTTP `HEAD` outside the retry wrapper; every network touch must sit inside the retry and TLS-refuse handler.
3. **Use exact Poisson tails (`.sf` / `.cdf`) at low expected counts:** normal approximations break at small `mu` (e.g. `mu = 0.06`, `k = 1` falsely triggering 3.9σ); use `poisson.sf(k - 1, mu)` and `poisson.cdf(k, mu)` and verify checkers fail on *missing* trees/branches, not just differing ones.
4. **Poll and wait cleanly on transient resource gaps:** when free disk or Manager acceptance lags, poll every 300 s under `HOLD` check (up to 24 h) instead of aborting a multi-day run; for slow/flaky range servers, tune request chunk size (e.g. 8,000 entries vs 50,000) to avoid mid-transfer stream cuts.
5. **Keep downstream checks and status labels accurate:** after switching to accept-then-delete, downstream follow-up checks must accept both `deleted` and `kept` states, and report strings should distinguish `"accepted, awaiting deletion pass"` from `"waiting for acceptance"`.
6. **Never make an untrusted downloads folder the interpreter's `cwd`:** always run from the repository root and pass target download paths as explicit CLI arguments.
7. **Update live pinned splits atomically & isolate sandbox logs:** test changes offline in a copy, swap binary + `.partial` pins atomically, and let `Ctrl-C` + rerun resume in-flight `.part` files; ensure `--test` runs keep their `log.jsonl` records out of production `runs/`.
8. **Avoid `git push` timeouts during heavy parallel downloads:** if concurrent multi-stream downloads cause `HTTP 408` / sideband disconnects on `git push`, `git -c http.postBuffer=52428800 push` resolves the push cleanly.

---

## 7. The merged format of the templates (the user's choices, 2026-11-27)

The user compared e6's and e7's formats row by row and chose, for each row, the form the templates use. Neither e6 nor
e7 was changed. Under "Choice", "trivial" and "same" mean that the templates keep what both already share.

| # | Item | The templates use | Choice |
|---|---|---|---|
| 1 | Command | the templates' own: `download_wrapper.sh [SET] [DEST] [status]`, `all_in_one.sh <split> \| status [split]` | trivial |
| 2 | Redraw | in place `\033[<n>A\033[J`; 5 s on a terminal, 30 s piped | same |
| 3 | Title | e6's, with e7's run name: `<TITLE> <run>  \|  HH:MM:SS  \|  elapsed …  \|  N workers  \|  time-out S s` | e6 |
| 4 | Label column | 9 characters | same |
| 5 | Step rows | e6's `STEP` and `THIS STEP`; a wait is e6's `WAITING` row, drawn by the driver; no `PHASE` row (e7's job lines show the running job) | e6 |
| 6 | Estimate row | e6's `TO DOWNLOAD (estimate)  X in all   moved Y` | e6 |
| 7 | `TOTAL` | e7's: bar, %, got / size | e7 |
| 8 | `FILES` | e7's | e7 |
| 9 | `SPEED` | e7's: now, average, ETA | e7 |
| 10 | `LINKS` | e7's | e7 |
| 11 | `KEPT` | none | e7 |
| 12 | `HEALTH` | e6's: failed attempts, stalls dropped, certificate events | e6 |
| 13 | `LASTERR` | on the `HEALTH` line (60 characters), with `NETWORK DOWN? waiting, retrying` | e6 |
| 14 | Group section | both: `GROUPS (moved / estimate)` (e6) and `RECORDS` (e7) | both |
| 15 | Files section | e7's `DOWNLOADING NOW`, with e6's `retrying` / `waiting (certificate)` notes | merged |
| 16 | Bottom line | `Ctrl-C stops cleanly; rerun resumes   \|   log: …` | same |
| 17 | Narrow layout | below 100 columns: bars 10 / 6, names 14 | same |
| 18 | Short window | e7's: only the file lines shrink | e7 |
| 19 | Start lines | e7's | e7 |
| 20 | Job lines | e7's | e7 |
| 21 | Per-file lines | e7's (`file report`, `FAILED`, `deleted`), with e6's `[<utc>]` stamp | merged |
| 22 | End lines | the downloader's (e7); at the split end e6's `[<utc>] SUMMARY: …`, then e7's `nudge:`, `status:`, `report:` | merged |
| 23 | Bridge per file | e7's line with e6's `step <i> of <n> group <G>` and the kept count | merged |
| 24 | Bridge wait / end | one line per wait (e6's), e7's end line with the kept count | merged |
| 25 | Recipients | file and wait lines: the Committee; the end line: every target (executor and Committee) | merged |
| 26 | `status` | e7's, with e6's bytes on disk per file | merged |
| 27 | Deletion | after acceptance, logged first, never under `HOLD` | same |
| 28 | Exit codes | e6's, with 5 for a wait that reached its limit | e6 |
| 29 | Settings prefix | the project's | trivial |

The user's answers on the open points (2026-11-27):
- **Step and group:** in a split, a STEP is one file and the group is the file's dataset; the split's name is in the
  title. For a plain download of one set, the step is 1 of 1 and the group is the set.
- **`processing`** in the `STEP` row reads 0 in the download frame, because the jobs run after the download.
- **Waits:** a wait is shown as e6's `WAITING` row, rewritten in place, and there is no `PHASE` row.
- **`time-out`** is the downloader's read time-out (300 s).

The templates' READMEs show the screen and list each line:
[`chunked-pipeline/README.md`](../../templates/chunked-pipeline/README.md) and
[`download-ui/README.md`](../../templates/download-ui/README.md).
