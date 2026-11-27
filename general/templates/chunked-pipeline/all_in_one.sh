#!/bin/bash
# PROJECT pipeline: the split script: one command per split, file by file: download, the project's jobs (verify, process, check), keep until the
# manager accepts the file, then delete its source; at the end of the split the end-of-split jobs, the facts, the report and the nudge.
# Template (general/templates/chunked-pipeline/): e7's tools/s6_all_in_one.sh of the user's project e7-upsilon-omega, with only the project's names
# changed. The driver is tools/pipe.py (standard library only); the downloader is tools/download_one.sh. The user starts every split by hand. No AI
# session starts a split.
#
# Usage:  cd /path/to/project && tools/all_in_one.sh g1         # run, or resume, split g1 (g1 g2, in this order)
#         cd /path/to/project && tools/all_in_one.sh status     # every split; no network; creates nothing
#         cd /path/to/project && tools/all_in_one.sh status g1  # one split, file by file
# Settings (environment, optional): PROJECT_PIPE_NUDGE ("PROJECT executor,PROJECT Committee"), PROJECT_PIPE_CAP_MIN (840), PROJECT_PIPE_RETRY=1,
#       PROJECT_PIPE_FLOOR_GIB (10); the downloader's PROJECT_DL_*.
# Exit: 0 the split is DONE (or PAUSED after the pilot file) and the nudge was delivered; 1 stopped or failed (report written, nudge sent); 2 wrong usage or a pinned
#       tool changed; 3 another copy is running (or the downloader's 3); 4 the split may not start (an earlier split is not DONE or not accepted, or runs/S1/HOLD);
#       5 a wait reached its limit (24 h): disk space before a file, or the manager's acceptance at the end of the split; 130 interrupted by Ctrl-C (no
#       nudge; the same command resumes).
set -u
cd "$(dirname "$0")/.." || exit 2
if [ "$#" -lt 1 ] || [ "$#" -gt 2 ] || { [ "$#" -eq 2 ] && [ "$1" != status ]; }; then
    echo "usage: tools/all_in_one.sh SPLIT | status [SPLIT]    (SPLIT: g1 g2)" >&2
    exit 2
fi
if [ "$1" != status ] && [ "$(uname)" = Darwin ] && command -v caffeinate >/dev/null 2>&1; then
    exec caffeinate -i /usr/bin/python3 -I tools/pipe.py "$@"
fi
exec /usr/bin/python3 -I tools/pipe.py "$@"
