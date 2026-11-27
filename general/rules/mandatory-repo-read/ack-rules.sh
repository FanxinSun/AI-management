#!/bin/bash
# Records or checks a session's acknowledgment of having read ~/AI-management rules.
#   Claude Code ids (claude-<session_id>): since 2026-11-25 the rules-gate hook records the files the
#   session actually read; for these ids this script reports that record and cannot set it.
#   agy and Codex ids (agy-<conversation id>, codex-<thread id>, codex-<pid of the live session>): since
#   2026-11-27 the acknowledgment is checked against the session's own log (ack_reads.py). It is recorded when
#   every listed file was read whole after it last changed, and refused while one is unread.
#   Any other id (gemini-*, manual), and an id whose log cannot be found: a declaration, recorded at the
#   current HEAD and shown as "declared".
# Usage:
#   ack-rules.sh <session_id>          Record ack for <session_id> at current HEAD (claude-*: report what is read)
#   ack-rules.sh --needs <session_id>  List the files <session_id> has still to read, one path per line
#   ack-rules.sh --auto <session_id>   Record only an ack that the session's log supports (for hooks): exit 0
#                                      recorded, 1 a file is unread, 3 this id's log cannot be checked
#   ack-rules.sh --check <session_id>  Exit 0 iff <session_id> is acked for current HEAD (claude-*: iff all is read)
#   ack-rules.sh --list                List recorded session acknowledgments
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../../.." && pwd)"
ACK_DIR="${AI_MGMT_ACK_DIR:-$HOME/.ai-management/rules-ack}"
READ_DIR="${AI_MGMT_READ_DIR:-$HOME/.ai-management/rules-read}"
GATE="${CLAUDE_HOME:-$HOME/.claude}/hooks/ai-management-rules-gate.sh"
READS="$SCRIPT_DIR/ack_reads.py"
LIST_PATH="general/rules/mandatory-repo-read/reading-list.txt"
PY="/usr/bin/python3"
[ -x "$PY" ] || PY="$(command -v python3 || true)"
mkdir -p "$ACK_DIR"

head_sha="$(git -C "$REPO" rev-parse HEAD 2>/dev/null || echo unknown)"
short_sha="$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo "$head_sha")"

sanitize() {
  printf '%s' "$1" | tr '/ ' '__' | tr -cd 'A-Za-z0-9._-'
}

# 0 when this id is a Claude session and the read-recording gate (v2) is installed here.
by_reading() {
  case "$1" in claude-*) ;; *) return 1 ;; esac
  [ -x "$GATE" ] && grep -q 'rules gate v2' "$GATE" 2>/dev/null
}

# 0 when this id's reads can be looked up in the session's own log (agy, Codex).
by_log() {
  case "$1" in agy-*|codex-*) ;; *) return 1 ;; esac
  [ -f "$READS" ] && [ -n "$PY" ]
}

# The reading list at HEAD, for this platform.
listed_files() {
  local os
  os="$(uname -s | tr 'A-Z' 'a-z')"
  git -C "$REPO" show "HEAD:$LIST_PATH" 2>/dev/null | awk -v os="$os" '
    /^[[:space:]]*#/ || NF == 0 { next }
    NF == 2 { if (index(os, $1) == 1) print $2; next }
    { print $1 }'
}

# changed_since COMMIT: the listed files that changed since that commit, or joined the list since.
changed_since() {
  local prev="$1" old f
  old="$(git -C "$REPO" show "$prev:$LIST_PATH" 2>/dev/null | awk '!/^[[:space:]]*#/ && NF { print $NF }' || true)"
  listed_files | while IFS= read -r f; do
    if ! printf '%s\n' "$old" | grep -qxF "$f" || ! git -C "$REPO" diff --quiet "$prev" HEAD -- "$f" 2>/dev/null; then
      printf '%s\n' "$f"
    fi
  done
}

# needs ID: prints the files the session has still to read.
#   From its own log where that can be checked; otherwise the files changed since its last acknowledgment
#   (all of them when it has none).
needs() {
  local safe="$1" out rc prev
  if by_log "$safe"; then
    out="$("$PY" -I "$READS" --needs "$safe" 2>/dev/null)" && rc=0 || rc=$?
    if [ "$rc" = 0 ] || [ "$rc" = 1 ]; then
      [ -z "$out" ] || printf '%s\n' "$out"
      return 0
    fi
  fi
  prev="$(cat "$ACK_DIR/$safe" 2>/dev/null || true)"
  if [ -n "$prev" ] && git -C "$REPO" cat-file -e "$prev^{commit}" 2>/dev/null; then
    [ "$prev" = "$head_sha" ] || changed_since "$prev"
  else
    listed_files
  fi
}

record() {  # record ID verified|declared
  printf '%s\n' "$head_sha" > "$ACK_DIR/$1"
  if [ "$2" = verified ]; then
    printf '%s\n' "$head_sha" > "$ACK_DIR/.verified-$1"
  else
    rm -f "$ACK_DIR/.verified-$1"
  fi
  rm -f "$ACK_DIR/.notified-$1"
}

case "${1:-}" in
  ""|-h|--help)
    sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
    ;;
  --list)
    echo "current HEAD: $short_sha ($head_sha)"
    names="$( { for f in "$ACK_DIR"/* "$READ_DIR"/claude-*; do
                  [ -f "$f" ] || continue
                  n="${f##*/}"
                  case "$n" in (.*|*.ok|*.ok.*) continue ;; esac
                  printf '%s\n' "$n"
                done; } | sort -u )"
    for name in $names; do
      if by_reading "$name"; then
        st="$("$GATE" status "$name" 2>/dev/null | head -1 || true)"
        st="${st#*: }"
        case "$st" in
          "read "*) n="${st#read }"; a="${n%% of *}"; b="${n##* of }"
                    if [ "$a" = "$b" ]; then status="READ"; else status="UNREAD"; fi
                    printf '%-48s %-8s %s\n' "$name" "$status" "$a/$b files" ;;
          *) printf '%-48s %-8s %s\n' "$name" "?" "$st" ;;
        esac
      else
        val="$(cat "$ACK_DIR/$name" 2>/dev/null || true)"
        status="STALE"
        how=""
        if [ "$val" = "$head_sha" ]; then
          status="CURRENT"
          how="declared"
          [ "$(cat "$ACK_DIR/.verified-$name" 2>/dev/null || true)" = "$val" ] && how="reads checked"
        fi
        printf '%-48s %-8s %-13s %s\n' "$name" "$status" "${val:0:12}" "$how"
      fi
    done
    exit 0
    ;;
  --check)
    sid="${2:-}"
    [ -n "$sid" ] || { echo "usage: ack-rules.sh --check <session_id>" >&2; exit 2; }
    safe="$(sanitize "$sid")"
    [ -n "$safe" ] || exit 1
    if by_reading "$safe"; then
      "$GATE" status "$safe" >/dev/null 2>&1
      exit $?
    fi
    [ -f "$ACK_DIR/$safe" ] && [ "$(cat "$ACK_DIR/$safe" 2>/dev/null)" = "$head_sha" ]
    exit $?
    ;;
  --needs)
    sid="${2:-}"
    [ -n "$sid" ] || { echo "usage: ack-rules.sh --needs <session_id>" >&2; exit 2; }
    safe="$(sanitize "$sid")"
    [ -n "$safe" ] || { echo "invalid session_id: $sid" >&2; exit 1; }
    if by_reading "$safe"; then
      { "$GATE" status "$safe" 2>/dev/null || true; } | sed -n 's/^  unread: //p'
      exit 0
    fi
    needs "$safe"
    exit 0
    ;;
  --auto)
    sid="${2:-}"
    [ -n "$sid" ] || { echo "usage: ack-rules.sh --auto <session_id>" >&2; exit 2; }
    safe="$(sanitize "$sid")"
    [ -n "$safe" ] || exit 1
    by_log "$safe" || exit 3
    "$PY" -I "$READS" "$safe" >/dev/null 2>&1 && rc=0 || rc=$?
    [ "$rc" = 0 ] || exit "$rc"
    record "$safe" verified
    exit 0
    ;;
  -*)
    echo "unknown option: $1" >&2
    exit 2
    ;;
  *)
    sid="$1"
    safe="$(sanitize "$sid")"
    [ -n "$safe" ] || { echo "invalid session_id: $sid" >&2; exit 1; }
    if by_reading "$safe"; then
      if out="$("$GATE" status "$safe" 2>/dev/null)"; then
        echo "$out"
        echo "acknowledged by reading; there is nothing to record by hand"
        exit 0
      fi
      echo "$out"
      echo "not acknowledged: a Claude Code session is acknowledged by reading the files above with the Read tool (each whole); this command cannot record it" >&2
      exit 1
    fi
    why=""
    if by_log "$safe"; then
      out="$("$PY" -I "$READS" "$safe" 2>&1)" && rc=0 || rc=$?
      case "$rc" in
        0)
          record "$safe" verified
          echo "acknowledged AI-management rules at $short_sha for session $safe (reads checked: this session's own log holds every listed file, whole)"
          exit 0
          ;;
        1)
          printf '%s\n' "$out" | grep '^unread ' >&2 || true
          echo "not acknowledged at $short_sha: this session's own log does not hold the file(s) above, whole, since they last changed. Read each of them whole with your file-reading tool (several calls may share one file), then run this again. A part of a file, or the part that a nudge named, is not an acknowledgment." >&2
          exit 1
          ;;
        *)
          why="$out"
          ;;
      esac
    fi
    record "$safe" declared
    echo "acknowledged AI-management rules at $short_sha for session $safe"
    [ -z "$why" ] || echo "note: recorded as declared, not as checked: $why"
    ;;
esac
