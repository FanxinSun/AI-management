#!/bin/bash
# PROJECT pipeline: download the files of ONE list into ONE folder, resumable, with the template's in-place dashboard.
#
# Template (general/templates/chunked-pipeline/): e7's tools/s6_download.sh of the user's project e7-upsilon-omega, with only the project's
# names changed (the settings' prefix PROJECT_DL_, e7: E7_S2_; the Python; the downloader's file name). Usage `tools/download_one.sh LIST DEST
# [status]`: there is no default folder and no set name; the list need not be under runs/. Settings, dashboard, resume, verification (size and
# adler32 per file, SHA256SUMS per record when its files are all done), the single-instance guard, the caffeinate wrapper and the exit codes
# are those of ../download-ui/download_wrapper.sh, via the same tools/fetch_dst.py:
#   0 all files done; 1 stopped (a 4xx answer, the network seems down, or files given up; a rerun resumes); 2 wrong usage or settings, or DEST holds
#   something that is not this download's own files; 3 not enough free disk space for the next file (its size plus 2 GiB), or another download is using
#   the folder; 130 interrupted with Ctrl-C (a rerun resumes, the partial files stay).
# The driver tools/pipe.py calls it once per file, with a one-file list and a folder of its own for that file.
# Settings, as environment variables (all optional): PROJECT_DL_WORKERS (default 1), PROJECT_DL_SPLIT (byte ranges per file, default 8; do not change it
#   while a folder has partial files), PROJECT_DL_MAX_ATTEMPTS (10), PROJECT_DL_REPORT_SECS (auto), PROJECT_DL_FILE_LINES (8), PROJECT_DL_DRY_RUN=1 (check
#   the list and the disk; fetch nothing, create nothing), PROJECT_DL_CAFFEINATE=0, PROJECT_DL_PYTHON (default /usr/bin/python3).
#
# Usage:   tools/download_one.sh LIST DEST [status]
#            LIST    a tab-separated list with the header recid key size adler32 url
#            DEST    the folder (a relative one is taken from the folder you run this in); the files go to DEST/<recid>/<key>
#            status  what is done, partial, bad or missing in DEST, and the free space (no network)
set -euo pipefail

workers=${PROJECT_DL_WORKERS:-1}
split=${PROJECT_DL_SPLIT:-8}
max_attempts=${PROJECT_DL_MAX_ATTEMPTS:-10}
report_secs=${PROJECT_DL_REPORT_SECS:-auto}
file_lines=${PROJECT_DL_FILE_LINES:-8}
dry_run=${PROJECT_DL_DRY_RUN:-0}
caffeinate_on=${PROJECT_DL_CAFFEINATE:-1}
py=${PROJECT_DL_PYTHON:-/usr/bin/python3}                 # PROJECT (e7: $HOME/system-env/e7/bin/python)

die() { echo "ERROR: $*" >&2; exit 2; }
usage() { echo "usage: $0 LIST DEST [status]" >&2; exit 2; }

mode=fetch
args=("$@")
if [ ${#args[@]} -gt 0 ] && [ "${args[${#args[@]}-1]}" = status ]; then
    mode=status
    unset 'args[${#args[@]}-1]'
fi
[ ${#args[@]} -eq 2 ] || usage
list=${args[0]}
dest=${args[1]}

case "$workers" in ''|*[!0-9]*|0) die "PROJECT_DL_WORKERS must be a positive integer" ;; esac
case "$split" in ''|*[!0-9]*|0) die "PROJECT_DL_SPLIT must be a positive integer" ;; esac
case "$max_attempts" in ''|*[!0-9]*|0) die "PROJECT_DL_MAX_ATTEMPTS must be a positive integer" ;; esac
case "$file_lines" in all) ;; ''|*[!0-9]*|0) die "PROJECT_DL_FILE_LINES must be a positive integer or all" ;; esac
case "$report_secs" in auto) ;; ''|*[!0-9.]*|.|*.*.*) die "PROJECT_DL_REPORT_SECS must be auto or a number of seconds" ;; esac
[ -x "$py" ] || die "Python not found or not executable: $py"

repo=$(cd "$(dirname "$0")/.." && pwd)                    # the repository, from this script's own path
case "$list" in /*) ;; *) list="$PWD/$list" ;; esac      # a relative LIST and DEST are taken from where the user is
case "$dest" in /*) ;; *) dest="$PWD/$dest" ;; esac
[ -s "$list" ] || die "file list missing: $list"
cd "$repo"

if [ "$mode" = status ]; then
    exec "$py" -I tools/fetch_dst.py status "$list" "$dest"
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
echo "list $list, folder $dest, $workers file(s) at once, $split range(s) per file"
exec ${wrap[@]+"${wrap[@]}"} "$py" -I tools/fetch_dst.py fetch "$list" "$dest" \
    --workers "$workers" --split "$split" --dashboard --report-seconds "$report_secs" --file-lines "$file_lines" \
    --max-stalls "$max_attempts" ${extra[@]+"${extra[@]}"}
