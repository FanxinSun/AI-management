#!/bin/bash
# Records or checks a session's acknowledgment of having read ~/AI-management rules.
#   agy, Codex, Gemini and manual ids: a declaration, recorded at the current HEAD.
#   Claude Code ids (claude-<session_id>): since 2026-11-25 the rules-gate hook records the files the
#   session actually read; for these ids this script reports that record and cannot set it.
# Usage:
#   ack-rules.sh <session_id>          Record ack for <session_id> at current HEAD (claude-*: report what is read)
#   ack-rules.sh --check <session_id>  Exit 0 iff <session_id> is acked for current HEAD (claude-*: iff all is read)
#   ack-rules.sh --list                List recorded session acknowledgments
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../../.." && pwd)"
ACK_DIR="${AI_MGMT_ACK_DIR:-$HOME/.ai-management/rules-ack}"
READ_DIR="${AI_MGMT_READ_DIR:-$HOME/.ai-management/rules-read}"
GATE="${CLAUDE_HOME:-$HOME/.claude}/hooks/ai-management-rules-gate.sh"
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

case "${1:-}" in
  ""|-h|--help)
    sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
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
        [ "$val" = "$head_sha" ] && status="CURRENT"
        printf '%-48s %-8s %s\n' "$name" "$status" "${val:0:12}"
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
    printf '%s\n' "$head_sha" > "$ACK_DIR/$safe"
    rm -f "$ACK_DIR/.notified-$safe"
    echo "acknowledged AI-management rules at $short_sha for session $safe"
    ;;
esac
