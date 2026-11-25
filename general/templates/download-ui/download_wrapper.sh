#!/bin/bash
# Piece B download: the DELPHI short DSTs of the off-peak years, from CERN's EOS storage.
#
# What it downloads: 472 files, 43.0 GB in all, from CERN Open Data records 81013 (short91_f1), 81166 (short93_d2)
# and 81502 (short95_d2). The list is runs/S3/pieceB-files.tsv. Many files are fetched at once (worker threads, one
# connection each; a slow link gives a slow connection, and connections add up). Every file is checked by size and
# adler32 before it counts as done; a file that fails is renamed *.bad, never deleted. When a record is complete a
# SHA256SUMS file is written in its folder.
#
# The terminal shows a dashboard redrawn in place every 5 s (every 30 s when the output is piped): overall progress
# and ETA, speeds, one bar per record, and the files being fetched. All detail goes to <folder>/download.log.
#
# Running it again resumes: finished files are skipped and a half-finished file continues from where it stopped (HTTP
# Range). Ctrl-C is safe at any moment; the partial files (*.part) are kept. Do not run two copies on one folder (the
# script refuses). A connection that stalls is dropped and resumed; a file is given up on only after several attempts
# in a row that added no bytes, and a run whose every connection fails stops at once ("the network seems down").
# On macOS the download runs under `caffeinate -i`, so the Mac does not idle-sleep while it runs (closing the lid still
# sleeps it).
#
# Usage:   tools/pieceB_download.sh                 download (or resume) into the default folder
#          tools/pieceB_download.sh status          what is done, partial, bad or missing there (no network)
#          tools/pieceB_download.sh DEST [status]   the same with the folder DEST (a relative DEST is taken from the
#                                                   folder you run this in)
# Default folder: ~/Downloads/e11-delphi-sidereal-lineshape/2026-11-18-pieceB, or E11_PIECEB_DOWNLOAD_ROOT if set.
# The project keeps bulk data outside the repository (on an external drive when one is attached:
# /Volumes/<drive>/e11-delphi-sidereal-lineshape/<one folder per download>; MIGRATION-M1-MACBOOK.md, section 3).
#
# Settings, as environment variables (all optional):
#   E11_PIECEB_DOWNLOAD_ROOT the folder, when no DEST argument is given
#   E11_PIECEB_WORKERS       parallel connections, default 32 (raise only while the overall rate keeps growing)
#   E11_PIECEB_MAX_ATTEMPTS  consecutive attempts without progress before a file is given up, default 10
#   E11_PIECEB_REPORT_SECS   dashboard refresh in seconds, default auto (5 on a terminal, 30 when piped)
#   E11_PIECEB_FILE_LINES    active files listed in the dashboard, default 8 ("all" lists every one)
#   E11_PIECEB_DRY_RUN=1     check the list, the CA file and the disk; fetch nothing, create nothing
#   E11_PIECEB_CAFFEINATE=0  do not run under caffeinate
#   E11_PIECEB_PYTHON        the Python to use, default /usr/bin/python3
#
# Exit status (passed through from the Python script):
#   0    all files done, or a stop that was asked for (nothing went wrong)
#   1    stopped: a 4xx answer from the server, the network seems down, or some files were given up (rerun resumes)
#   2    wrong usage or settings, or the folder holds something that is not this download's own files
#   3    not enough free disk space for the next file (its size plus 2 GiB), or another download is using the folder
#   130  interrupted with Ctrl-C (rerun resumes)
set -euo pipefail

CA_FP='18:7F:4F:7B:13:15:EB:D2:B7:25:47:C1:AC:CF:2E:C4:07:7D:51:C1:4A:0C:E5:74:90:4A:9F:DA:EA:8A:32:0C'
default_root=$HOME/Downloads/e11-delphi-sidereal-lineshape/2026-11-18-pieceB
workers=${E11_PIECEB_WORKERS:-32}
max_attempts=${E11_PIECEB_MAX_ATTEMPTS:-10}
report_secs=${E11_PIECEB_REPORT_SECS:-auto}
file_lines=${E11_PIECEB_FILE_LINES:-8}
dry_run=${E11_PIECEB_DRY_RUN:-0}
caffeinate_on=${E11_PIECEB_CAFFEINATE:-1}
py=${E11_PIECEB_PYTHON:-/usr/bin/python3}

die() { echo "ERROR: $*" >&2; exit 2; }
usage() { echo "usage: $0 [DEST] [status]   (default folder: \${E11_PIECEB_DOWNLOAD_ROOT:-$default_root})" >&2; exit 2; }

mode=fetch
dest=
case $# in
    0) ;;
    1) if [ "$1" = status ]; then mode=status; else dest=$1; fi ;;
    2) [ "$2" = status ] || usage; dest=$1; mode=status ;;
    *) usage ;;
esac
dest=${dest:-${E11_PIECEB_DOWNLOAD_ROOT:-$default_root}}
case "$dest" in /*) ;; *) dest="$PWD/$dest" ;; esac       # relative to where the user is, not to the repository

case "$workers" in ''|*[!0-9]*|0) die "E11_PIECEB_WORKERS must be a positive integer" ;; esac
case "$max_attempts" in ''|*[!0-9]*|0) die "E11_PIECEB_MAX_ATTEMPTS must be a positive integer" ;; esac
case "$file_lines" in all) ;; ''|*[!0-9]*|0) die "E11_PIECEB_FILE_LINES must be a positive integer or all" ;; esac
case "$report_secs" in auto) ;; ''|*[!0-9.]*|.|*.*.*) die "E11_PIECEB_REPORT_SECS must be auto or a number of seconds" ;; esac
[ -x "$py" ] || die "Python not found or not executable: $py"

repo=$(cd "$(dirname "$0")/.." && pwd)                    # the repository, from this script's own path
cd "$repo"
[ -s runs/S3/pieceB-files.tsv ] || die "file list missing: $repo/runs/S3/pieceB-files.tsv"

if [ "$mode" = status ]; then
    exec "$py" -I tools/s3b_fetch_dst.py status runs/S3/pieceB-files.tsv "$dest"
fi
case "$dest/" in
    "$repo"/downloads/*|"$repo"/data/*) ;;
    "$repo"/*) echo "NOTE: $dest is inside the repository and is not git-ignored; never 'git add' it." >&2 ;;
esac
extra=()
wrap=()
if [ "$dry_run" = 1 ]; then
    extra+=(--dry-run)
elif [ "$caffeinate_on" != 0 ] && command -v caffeinate >/dev/null 2>&1; then
    wrap=(caffeinate -i)                                  # no idle sleep while it runs; exit status passes through
fi
exec ${wrap[@]+"${wrap[@]}"} "$py" -I tools/s3b_fetch_dst.py fetch runs/S3/pieceB-files.tsv "$dest" \
    --eos --cafile tools/certs/cern-root-ca-2.pem --cafile-sha256 "$CA_FP" \
    --workers "$workers" --dashboard --report-seconds "$report_secs" --file-lines "$file_lines" \
    --max-stalls "$max_attempts" ${extra[@]+"${extra[@]}"}
