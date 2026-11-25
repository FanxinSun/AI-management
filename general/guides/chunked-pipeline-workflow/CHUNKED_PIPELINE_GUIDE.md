# Chunked Download–Process–Delete Pipeline Guide (AI-Free Execution)

Recorded on **2026-11-25** from the two production pipelines developed by **e6 Committee** (`~/e6-emu-below-z`, `claude:57721`) and **e7 Committee** (`~/e7-upsilon-omega`, `claude:90804`).

---

## 1. Purpose & Core Pattern

When processing hundreds of gigabytes to multiple terabytes of remote datasets on bounded local disk over many hours or days, keeping an AI session in the loop burns tokens, hits context/usage limits, and risks unlogged edits.

The **Chunked All-in-One AI-Free Pipeline** moves the entire data lifecycle into a deterministic, resumable script that the **user starts by hand** with zero AI tokens spent while it runs:

```text
[User starts/resumes one command]
   │
   ▼  (AI-free loop over chunks or files)
download chunk/file ──► verify ──► process / skim ──► check ──► delete raw download (logged) ──► analyze / follow-up
   │
   ▼  (only at end, pilot pause, or hard stop)
write report + status ──► bridge nudge (or zero-token watch loop) wakes Executor / Committee
```

**Core principles:**
1. **Bounded disk:** raw downloads are never accumulated across the whole dataset; each chunk/file is verified, reduced to a compact kept output (skim/book/results), and deleted only after every check passes.
2. **AI-free execution:** downloading, processing, checking, deletion, analysis, and report generation run unattended in standard Python/shell scripts under `caffeinate -i`.
3. **Human-started, resumable:** every run is launched by the user with one command (no AI session starts splits/downloads unless explicitly approved). `Ctrl-C` exits `130` cleanly; rerunning the exact same command resumes.
4. **Independent verification:** per-file/per-step checks run inside the pipeline, and independent re-derivation (event-by-event or cell-by-cell) runs either inside the per-file chain (E7) or by the Committee outside the script (E6).

---

## 2. Two Production Variants Side by Side

| Dimension | **E6 (`e6-emu-below-z`) — Continuous Multi-Step Driver** | **E7 (`e7-upsilon-omega`) — Explicit Large-Split Driver** |
|---|---|---|
| **Dataset scale** | 359 NanoAOD files (357.5 GB source; **38.65 GB** branch-read over HTTPS) | 556 remaining MINIAOD files (**2.00 TB** source; ~55 days at 0.42 MB/s) |
| **Chunking unit** | **27 consecutive steps** of ~2.0 GB estimated download each (from a single continuous run; optional soft stop `--steps N`) | **8 user-started large splits** (`g1..g4`, `h1..h4`, 60–80 files / 232–267 GB each, cut by `s6_splits.py`) |
| **Granularity of delete** | **Per step** (all files of a step downloaded, processed, checked, then step downloads deleted) | **Per file** inside a split (download → verify → probe → v1 skim → lean v2 skim → eval → delete source + v1 skim) |
| **Kept footprint** | ~1.7–1.9 GB/step (data/tt̄), ~0.13 GB/step (DY); stored on external disk | Lean skim is 6.8% of v1 (~27 GB total for all 2016G+H); stays on internal Mac disk |
| **Entry point** | `tools/e6_download_kplus.sh` → `tools/e6_fetch_kplus.py` + `tools/e6_follow.py` | `tools/s6_all_in_one.sh <split>` → `tools/s6_pipe.py` + `tools/s6_download.sh` (`s2_fetch.py`) |
| **Downloader base** | Adapted from `general/templates/download-ui/` (in-place dashboard, `<100`-col layout, `status`, Range resume, lock, `caffeinate`) | Calls `tools/s6_download.sh` (`s2_fetch.py`, copied from `general/templates/download-ui/`) per file |
| **Governance gates** | `steps-plan.tsv` must match frozen `runs/E6-6/e6-6-8-steps.tsv` row for row (else exit 2) | SHA-256 pins of 25 tools checked pre/post-split (`s6_all_in_one.pins`); `g1` pilot pause; sequential `accepted.tsv` + `runs/S6/HOLD` (exit 4) |
| **Waking AI** | **No script nudge** (default); Committee runs a zero-token shell watch loop on `follow/steps.tsv` / `failed.tsv` / `cert-events.tsv` | **Bridge nudge** (`send_to_tty.sh` to `"e7 executor,e7 Committee"`) with one-line summary + `runs/S6/handover-split.md` |

**When to choose which:**
* **E6 pattern** fits when a single continuous command should walk through many medium chunks (~2 GB each), running downstream follow-up after each step and retrying transient network/TLS glitches indefinitely.
* **E7 pattern** fits when total download spans weeks across very large files (multi-GB each) on tight internal disk: cutting into week-sized user-started splits (`g1..h4`), deleting **per file** immediately after evaluation, and gating each split on pilot/manager acceptance keeps peak disk to one file + floor (`10 GiB`).

---

## 3. E6 Production Pattern (`e6-emu-below-z`)

1. **Wrapper & UI (`tools/e6_download_kplus.sh` → `e6_fetch_kplus.py`):**
   * Built to `general/templates/download-ui/` rules: no-arg default run, `status` mode (no network, creates nothing), in-place `\033[<n>A\033[J` dashboard, `<100`-column narrow layout, `caffeinate -i`, single-instance `.download.lock` + `ps` guard.
   * **Estimated download vs source size:** displays only the branch-read bytes (~11.8% data, ~10.58% sim), never the raw 357.5 GB source size.
2. **Per-step 6-stage loop:**
   1. **Download** the step's files (4 workers) into `DEST/data/`.
   2. **Process** each into a loose skim (`skim/`) and full-event count book (`book/`).
   3. **Check** (entries == source, skim readback == selection, cut-flow parity, simulation weight sums == `Runs` tree).
   4. **Delete** the step's raw `.kplus.root` downloads **only if every file in the step passed**, logging each path and bytes to `deleted.tsv`.
   5. **Mark** `steps.tsv` (`finalize_step`).
   6. **Follow up (`tools/e6_follow.py` as child process):** catches up any done-but-unfollowed steps first, runs R1 checks (including verifying `.kplus.root` files are gone and deleted bytes match), updates running results in `runs/E6-6/follow/`, and writes `DEST/reports/step-NN.txt` + one screen summary line.
3. **Resilience & tool updates:**
   * **Network & TLS retries (D21 / A14 / A15):** transient HTTP/timeout/stall errors retry every 60 s without limit; TLS/certificate hostname mismatches refuse the connection, log to `cert-events.tsv`, wait 600 s, and retry without limit. Certificate verification is **never** disabled.
   * **Hard stops:** HTTP `403`/`429`, a failed check or follow-up, or `Ctrl-C` (`130`).
   * **Live swaps:** edits while a run is active go to `*_new.sh` / `*_new.py`, are diffed and tested in a separate folder by the Committee, and swapped in only between runs.

---

## 4. E7 Production Pattern (`e7-upsilon-omega`)

1. **Splitting (`tools/s6_splits.py`) & Wrapper (`tools/s6_all_in_one.sh`):**
   * Cuts remaining files in byte order into 8 week-sized splits (`g1..g4`, `h1..h4`) in `runs/S6/splits/`.
   * `tools/s6_all_in_one.sh <split>` runs `exec caffeinate -i /usr/bin/python3 -I tools/s6_pipe.py <split>` (stdlib only); `status [split]` reads state with no network and creates nothing.
   * Every subprocess runs through `tools/run_logged.py` (writes `runs/log.jsonl` with wall time, peak MB, exit code), enforcing the per-split compute cap (`840 min`).
2. **Per-file 14-step lifecycle (`s6_pipe.py`):**
   * Space check (file size + `E7_PIPE_FLOOR_GIB=10` free) → download into `downloads/s6-<split>/<id>/` → verify (size, adler32, SHA-256) → probe → full v1 skim (`data/s6/v1tmp`) → 8 v1 checks → manager independent `recheck1` → trigger-menu check → lean v2 skim (`data/s6/lean`, 6.8% of v1) → lean checks (K1–K7 + manager independent bit-for-bit `mgrlean`) → evaluation (E1–E9) → update manifests (`checked` / `deleted-after-lean`) → **delete source, `.part` files, and v1 skim**, logging full path, bytes, SHA-256, and UTC timestamp to `runs/S6/<split>/deletions.tsv` with `os.fsync` **before** `os.remove`.
   * Failed files keep their source and v1 skim; 3 failed files waiting stop the split (`STOPPED, 3 failed files waiting`).
3. **End of split, gates, & bridge nudge:**
   * Runs analysis jobs (`m1`, `m6`, `m6fit`, `m1cum`), `s6_facts.py`, copies download logs to `download-records/`, writes `runs/S6/<split>/report.md` and `runs/S6/status.tsv`, and sends a single-line bridge nudge to `E7_PIPE_NUDGE` (`"e7 executor,e7 Committee"`):
     ```text
     [PIPELINE s6 <split>] <status>; report runs/S6/<split>/report.md; facts ...; compute x of 840 min; now carry out runs/S6/handover-split.md
     ```
   * **Gates (exit 4):** `runs/S6/HOLD` stops all starts; a split starts only if every prior split is `DONE` and listed in `runs/S6/accepted.tsv` (written only by the manager); `g1` pauses after its first finished file until `g1-pilot` is accepted (and any failure before pilot acceptance stops `g1` at once).
   * **Standing check-only order (`runs/S6/handover-split.md`):** when nudged, the executor only verifies logs, pins, manifest hashes, deletions, disk, blinding (0 hidden rows with content), and facts, then replies to `e7 Committee` — it never starts/resumes a split or deletes anything.

---

## 5. Reusable Blueprint & Non-Negotiable Invariants

When designing a new chunked all-in-one pipeline in any project:

1. **Downloader UI compliance:** follow [`general/templates/download-ui/README.md`](../../templates/download-ui/README.md) (`fetch_dst.py` + `download_wrapper.sh`: in-place `\033[<n>A\033[J` dashboard, `<100`-col layout, `status` creates nothing, automatic default folder, `caffeinate -i`, single-instance lock, HTTP Range resume, size/checksum verification).
2. **Delete-only-after-verified-pass + audit log:**
   * Never delete raw downloads until every check on that chunk/file has passed.
   * Log full path, byte size, SHA-256, and UTC timestamp to `deletions.tsv` / `deleted.tsv` (`flush` + `fsync`) **before** calling `os.remove`.
   * Keep failed files intact on disk so the cause can be inspected and resumed.
3. **Standardized exit codes:**
   * `0`: `DONE` (or `PAUSED after the pilot file`) and nudge delivered (if enabled).
   * `1`: failed/stopped (report written, nudge sent if enabled), or `DONE, <n> file(s) failed: <ids>`, or nudge delivery failed.
   * `2`: wrong usage, unmounted external drive, foreign folder, or tool/plan SHA-256 pin mismatch.
   * `3`: insufficient disk space (below per-step/per-file floor) or another instance already holds the lock.
   * `4`: governance gate refused (`HOLD` present or prerequisite split not `DONE`/accepted).
   * `130`: interrupted by `Ctrl-C` (no nudge sent; rerun resumes cleanly).
4. **Honest status wording:** never emit plain `DONE` if any file or analysis job failed — always emit `DONE, <n> file(s) failed: <ids>`.
5. **Bridge nudge safety:**
   * Always invoke the installed runtime bridge path (`~/.claude/agy-bridge/send_to_tty.sh` or `send_to_tty.sh` on `PATH`), **never** a repo path that may be moved/reorganized mid-run.
   * Wrap the nudge `subprocess.run` in `try/except OSError` so a missing bridge binary prints the message for the user and exits `1` *after* the report and `status.tsv` are safely saved.
6. **Sandbox test modes before real data:** include a fast `--test fail|partial|pilot|disk|cap|error|sleep` mode on synthetic file lists so status words, pilot stops, disk guards, and nudges are verified before touching multi-day downloads.

---

## 6. Field Lessons & Pitfalls (from E6 & E7)

1. **Ask the user about chunk size & storage before designing:** don't assume tiny splits or an external SSD without asking; confirm whether the user wants to start splits by hand vs continuously.
2. **Never display full source-file totals when only reading selected branches:** show the actual estimated transfer bytes so the dashboard reflects real network work.
3. **Put independent checks inside the per-file chain (or re-derive externally per step):** unattended deletion is only safe when an independent check validates the output before the source is removed.
4. **Account for external disk consumers:** VM images or other processes can shrink free space mid-run; checking free space before *every* file/step lets the pipeline stop cleanly and resume later.
5. **Never stop long user-run transfers on transient network or TLS glitches:** wait and retry with fresh connections while refusing untrusted data and keeping certificate verification on (log the refused cert subject to diagnose server vs path issues).
6. **Pinning freezes tools for the whole split:** test edge cases (including float32 vs float64 boundary tolerances and `DONE, <n> file(s) failed` states) in sandbox mode first; for live changes during an unpinned continuous run, stage under `_new` names and swap between runs.
7. **Zero-token watch loops must track line offsets and run multi-arg commands under `bash -c`:** never re-match old `STOPPED` lines, and avoid waking the AI on transient retries that clear on attempt 1.
8. **Never hardcode retired repo paths inside long-running pinned scripts:** use `~/.claude/agy-bridge/send_to_tty.sh` (or `send_to_tty.sh` on `PATH`) and catch `OSError` around nudge delivery.
