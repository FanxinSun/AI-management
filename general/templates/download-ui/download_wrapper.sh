#!/bin/bash
# PROJECT download: the files of one set, from their URLs, resumable, with the template's in-place dashboard.
#
# Template (general/templates/download-ui/): e7's tools/s2_download.sh of the user's project e7-upsilon-omega, with only the project's names
# changed (they are marked PROJECT below; e7's values are in the comments). Copy it with fetch_dst.py into <project>/tools/ and change:
# the sets, the list folder, the default folder, the settings' prefix PROJECT_DL_ (e7: E7_S2_) and the Python. Keep everything else.
#
# What it downloads: the files of one set, listed in runs/download/files-<SET>.tsv (a tab-separated list with the header
# recid key size adler32 url). Every file is checked by size and adler32 before it counts as done; a file that fails is renamed *.bad,
# never deleted. When a record is complete a SHA256SUMS file is written in its folder. A file over 64 MiB is fetched in PROJECT_DL_SPLIT
# byte ranges on as many connections (the server must honour Range), then joined and verified.
#
# Running it again resumes: finished files are skipped and a half-finished file continues where it stopped (HTTP Range).
# Ctrl-C is safe at any moment; the partial files (*.part) are kept. Do not run two copies on one folder (the script
# refuses). A stalled connection is dropped and resumed; a file is given up on only after several attempts in a row that
# added no bytes. On macOS the download runs under `caffeinate -i` (closing the lid still sleeps the Mac). The terminal
# shows a dashboard; the detail is in <DEST>/download.log.
#
# Usage:   tools/download_wrapper.sh [SET] [DEST] [status]
#            SET   set1 (default) or set2: picks runs/download/files-<SET>.tsv
#            DEST  the folder; default: downloads/download-<SET> in this repository (git-ignored); a relative DEST is
#                  taken from the folder you run this in. Another disk: /Volumes/<drive>/<project>/<folder>
#            status  what is done, partial, bad or missing in DEST, and the free space (no network)
#          Examples:  tools/download_wrapper.sh                        (set1, into downloads/download-set1)
#                     tools/download_wrapper.sh set2
#                     tools/download_wrapper.sh set2 /Volumes/MyDisk/project/download-set2
#                     tools/download_wrapper.sh set1 status
# Settings, as environment variables (all optional):
#   PROJECT_DL_WORKERS      files fetched at once, default 1
#   PROJECT_DL_SPLIT        a file over 64 MiB is fetched in this many byte ranges on this many connections, default 8.
#                           Do not change it while a set has partial files: the range files (*.part0, *.part1, ...) do not
#                           record the split, so after an increase the old ones are resumed at the wrong offsets; the
#                           checksum then fails and that file is downloaded again. PROJECT_DL_WORKERS can be changed at any time.
#   PROJECT_DL_MAX_ATTEMPTS consecutive attempts without progress before a file is given up, default 10
#   PROJECT_DL_REPORT_SECS  dashboard refresh in seconds, default auto (5 on a terminal, 30 when piped)
#   PROJECT_DL_FILE_LINES   active files listed in the dashboard, default 8 ("all" lists every one)
#   PROJECT_DL_DRY_RUN=1    check the list and the disk; fetch nothing, create nothing
#   PROJECT_DL_CAFFEINATE=0 do not run under caffeinate
#   PROJECT_DL_PYTHON       the Python to use, default /usr/bin/python3 (fetch_dst.py needs only the standard library)
#
# Exit status (passed through from the Python script):
#   0 all files done (or a stop that was asked for); 1 stopped: a 4xx answer from the server, the network seems down,
#   or some files were given up (rerun resumes); 2 wrong usage or settings, or DEST holds something that is not this
#   download's own files; 3 not enough free disk space for the next file (its size plus 2 GiB), or another download
#   is using the folder; 130 interrupted with Ctrl-C (rerun resumes).
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
usage() { echo "usage: $0 [set1|set2] [DEST] [status]   (default: set1 into <repository>/downloads/download-set1)" >&2; exit 2; }

set_name=set1                                             # PROJECT: the default set (e7: step2)
dest=
mode=fetch
args=("$@")
if [ ${#args[@]} -gt 0 ] && [ "${args[${#args[@]}-1]}" = status ]; then
    mode=status
    unset 'args[${#args[@]}-1]'
fi
if [ ${#args[@]} -gt 0 ]; then
    case "${args[0]}" in
        set1|set2) set_name=${args[0]}; args=("${args[@]:1}") ;;   # PROJECT: the sets (e7: step2|step3|step4a|step4b)
    esac
fi
case ${#args[@]} in
    0) ;;
    1) dest=${args[0]} ;;
    *) usage ;;
esac

case "$workers" in ''|*[!0-9]*|0) die "PROJECT_DL_WORKERS must be a positive integer" ;; esac
case "$split" in ''|*[!0-9]*|0) die "PROJECT_DL_SPLIT must be a positive integer" ;; esac
case "$max_attempts" in ''|*[!0-9]*|0) die "PROJECT_DL_MAX_ATTEMPTS must be a positive integer" ;; esac
case "$file_lines" in all) ;; ''|*[!0-9]*|0) die "PROJECT_DL_FILE_LINES must be a positive integer or all" ;; esac
case "$report_secs" in auto) ;; ''|*[!0-9.]*|.|*.*.*) die "PROJECT_DL_REPORT_SECS must be auto or a number of seconds" ;; esac
[ -x "$py" ] || die "Python not found or not executable: $py"

repo=$(cd "$(dirname "$0")/.." && pwd)                    # the repository, from this script's own path
case "$dest" in
    '') dest=$repo/downloads/download-$set_name ;;        # PROJECT: the default folder (e7: downloads/s2-miniaod-<SET>)
    /*) ;;
    *) dest="$PWD/$dest" ;;                              # relative to where the user is, not to the repository
esac
cd "$repo"
list=runs/download/files-$set_name.tsv                    # PROJECT: the list of a set (e7: runs/S2/files-<SET>.tsv)
[ -s "$list" ] || die "file list missing: $repo/$list"

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
echo "set $set_name: list $list, folder $dest, $workers file(s) at once, $split range(s) per file"
exec ${wrap[@]+"${wrap[@]}"} "$py" -I tools/fetch_dst.py fetch "$list" "$dest" \
    --workers "$workers" --split "$split" --dashboard --report-seconds "$report_secs" --file-lines "$file_lines" \
    --max-stalls "$max_attempts" ${extra[@]+"${extra[@]}"}
