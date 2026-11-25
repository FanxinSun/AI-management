#!/bin/bash
# Agent bridge: type a one-line message into another agent's terminal.
#   macOS:       Terminal.app tabs (AppleScript)
#   Linux / WSL: tmux panes (tmux send-keys) if the target runs in tmux;
#                otherwise, on WSL, the target's Windows Terminal tab: a helper
#                (conin_inject.ps1) is launched through the target session's
#                WSL interop socket and writes keystrokes into that tab's
#                console (WriteConsoleInput). TIOCSTI as a last resort if the
#                kernel allows it (dev.tty.legacy_tiocsti=1).
#
#   send_to_tty.sh <target> <message...>   send a message
#   send_to_tty.sh --raw <target> <text>   type <text> exactly, no "[from ...]"
#                                          prefix, then extra lone Returns: for
#                                          slash commands, e.g. a Codex session's
#                                          "/model gpt-6-luna --reasoning=medium"
#   send_to_tty.sh --read <target>         dump the target's screen without typing
#   send_to_tty.sh --dry-run <target>      show where a message would go
#   send_to_tty.sh --register <name> [--force]
#                                          name the calling agent session
#   send_to_tty.sh --whoami                show the calling agent session
#   send_to_tty.sh --list                  list running agents and names
#
# <target> is one of:
#   reply            the session that last messaged you (best for answers)
#   <name>           a name registered with --register (preferred)
#   "<title>"        the session's user-given title (agy, claude, codex), read
#                    live, so it follows /clear + /rename in the same tab; case
#                    and -/_/space are ignored; refused if two sessions share it
#   <kind>:<pid>     e.g. claude:7529, agy:8410 (what the [from ...] tag shows)
#   pid:<pid>        any process; its current TTY is looked up
#   claude|agy|codex|gemini
#                    any session of that kind; see "Relay correction"
#   ttysNNN|pts/N    raw TTY (TTY numbers get reused; avoid)
#
# Sessions are tracked by PID + process start time, never by TTY number.
# Every message is prefixed with "[from <sender>]", a valid reply target
# (except with --raw, which types the text as-is so slash commands work).
# Newlines are flattened to spaces (a newline would submit early).
#
# Relay correction: the bridge remembers, per session, who last messaged it and
# whom it last messaged. A target that is wrong is corrected from that record
# instead of being dropped, and the correction is printed and logged:
#   - target is your own session      -> your conversation partner
#   - bare kind matches several       -> your partner of that kind, else the
#                                        only one of that kind in your folder
#   - name's process exited/replaced  -> the one unnamed session of the same
#                                        kind in the same folder (it takes over
#                                        the name)
# When no correction is unambiguous, the send is refused (exit 2) with the
# candidates listed. BRIDGE_NO_REROUTE=1 turns correction off.

BRIDGE="${AGY_BRIDGE_HOME:-$HOME/.claude/agy-bridge}"
REG="$BRIDGE/sessions"
STATE="$BRIDGE/state"
LOG="$BRIDGE/send.log"
mkdir -p "$REG" "$STATE"
OS=$(uname -s)   # Darwin | Linux (WSL reports Linux)

die()  { echo "send_to_tty: $*" >&2; exit 1; }
die2() { echo "send_to_tty: $*" >&2; exit 2; }

# kind_of <pid> -> claude|agy|codex|gemini, or empty
kind_of() {
  local comm args
  comm=$(ps -o comm= -p "$1" 2>/dev/null) || return
  comm=${comm##*/}
  case "$comm" in
    claude|agy|codex|gemini) echo "$comm"; return ;;
    codex-cli) echo codex; return ;;
  esac
  args=$(ps -o args= -p "$1" 2>/dev/null)
  case "$args" in
    *node*/gemini*|*node*gemini-cli*) echo gemini ;;
  esac
}

# Process identity (pid + start). On Linux use the start time in clock ticks since
# boot from /proc/<pid>/stat: ps's wall-clock lstart drifts on WSL after the host
# sleeps, which made live registrations look "gone".
lstart_of() {
  if [ "$OS" = Linux ] && [ -r "/proc/$1/stat" ]; then
    sed 's/.*) //' "/proc/$1/stat" 2>/dev/null | awk '{print "t" $20}'
  else
    ps -o lstart= -p "$1" 2>/dev/null | sed 's/  */ /g;s/^ //;s/ $//'
  fi
}
tty_of()    { local t; t=$(ps -o tty= -p "$1" 2>/dev/null | tr -d ' '); [ -n "$t" ] && [ "$t" != "??" ] && [ "$t" != "?" ] && echo "$t"; }
cwd_of() {
  if [ "$OS" = Linux ]; then readlink "/proc/$1/cwd" 2>/dev/null
  else lsof -a -p "$1" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p'; fi
}

# User-given session title (/rename), read live, so it follows /clear + /rename in
# the same process. Codex stores its current thread name in session_index.jsonl;
# the active rollout or writer-lock file identifies which index entry belongs to
# each process:
#   claude: ~/.claude/sessions/<pid>.json -> "name"
#   agy:    the conversation the process has open (conversations/<id>.db) -> the
#           latest "/rename <title>" for that conversation in history.jsonl
#   codex:  the active rollout/writer-lock filename -> ~/.codex/session_index.jsonl
AGY_HOME="${AGY_HOME:-$HOME/.gemini/antigravity-cli}"
BRIDGE_CODEX_ROOT="${CODEX_HOME:-$HOME/.codex}"
agy_conv_of() {
  if [ "$OS" = Linux ]; then
    ls -l "/proc/$1/fd" 2>/dev/null | grep -o 'conversations/[0-9a-f-]*\.db$' | head -n1 | sed 's#conversations/##;s#\.db$##'
  else
    lsof -p "$1" -Fn 2>/dev/null | grep -o 'conversations/[0-9a-f-]*\.db$' | head -n1 | sed 's#conversations/##;s#\.db$##'
  fi
}
codex_thread_from_path() {
  printf '%s\n' "$1" |
    sed -n \
      -e 's#^.*/rollout-[^/]*-\([0-9A-Fa-f]\{8\}-[0-9A-Fa-f]\{4\}-[0-9A-Fa-f]\{4\}-[0-9A-Fa-f]\{4\}-[0-9A-Fa-f]\{12\}\)\.jsonl$#\1#p' \
      -e 's#^.*/thread-writer-locks/\([0-9A-Fa-f]\{8\}-[0-9A-Fa-f]\{4\}-[0-9A-Fa-f]\{4\}-[0-9A-Fa-f]\{4\}-[0-9A-Fa-f]\{12\}\)\.lock$#\1#p'
}
codex_thread_of() {
  local fd path c
  if [ "$OS" = Linux ]; then
    for fd in /proc/"$1"/fd/*; do
      path=$(readlink "$fd" 2>/dev/null) || continue
      c=$(codex_thread_from_path "$path")
      [ -n "$c" ] && { echo "$c"; return; }
    done
  else
    for path in $(lsof -p "$1" -Fn 2>/dev/null | sed -n 's/^n//p'); do
      c=$(codex_thread_from_path "$path")
      [ -n "$c" ] && { echo "$c"; return; }
    done
  fi
}
title_of() {
  local k c; k=$(kind_of "$1")
  case "$k" in
    claude)
      [ -f "$HOME/.claude/sessions/$1.json" ] || return
      python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); n=d.get("name") or ""; print(n) if str(d.get("pid"))==sys.argv[2] and n else None' \
        "$HOME/.claude/sessions/$1.json" "$1" 2>/dev/null ;;
    agy)
      c=$(agy_conv_of "$1"); [ -n "$c" ] && [ -f "$AGY_HOME/history.jsonl" ] || return
      grep -F "\"conversationId\":\"$c\"" "$AGY_HOME/history.jsonl" |
        python3 -c 'import json,sys
t=""
for l in sys.stdin:
    try: d=json.loads(l)
    except Exception: continue
    s=d.get("display","")
    if s.startswith("/rename "): t=s[8:].strip()
print(t) if t else None' 2>/dev/null ;;
    codex)
      c=$(codex_thread_of "$1")
      [ -n "$c" ] && [ -f "$BRIDGE_CODEX_ROOT/session_index.jsonl" ] || return
      python3 - "$BRIDGE_CODEX_ROOT/session_index.jsonl" "$c" <<'PY'
import json
import sys

index_path, thread_id = sys.argv[1:]
title = ""
try:
    with open(index_path, encoding="utf-8") as stream:
        for line in stream:
            try:
                row = json.loads(line)
            except Exception:
                continue
            if row.get("id") == thread_id and row.get("thread_name"):
                title = str(row["thread_name"])
except OSError:
    pass
if title:
    print(title.replace("\r", " ").replace("\n", " "))
PY
      ;;
  esac
}
# live pids whose title equals $1 (case-insensitive, spaces/-/_ treated alike)
pids_by_title() {
  local want pid k t; want=$(echo "$1" | tr 'A-Z_-' 'a-z  ' | tr -s ' ')
  all_agents | while read -r pid k t; do
    [ "$(title_of "$pid" | tr 'A-Z_-' 'a-z  ' | tr -s ' ')" = "$want" ] && echo "$pid"
  done
}

# The agent session that invoked this script: walk up the parent chain.
# Codex 0.171+ runs tool shells under a tty-less `codex app-server`; when we hit
# a tty-less codex ancestor, resolve to the live codex TUI session (matching
# thread cwd / PWD when more than one codex TUI is running).
caller_pid() {
  local p=$PPID k t codex_fallback=""
  while [ -n "$p" ] && [ "$p" -gt 1 ]; do
    k=$(kind_of "$p")
    if [ -n "$k" ]; then
      t=$(tty_of "$p")
      if [ -n "$t" ]; then echo "$p"; return; fi
      [ "$k" = codex ] && [ -z "$codex_fallback" ] && codex_fallback=$p
    fi
    p=$(ps -o ppid= -p "$p" 2>/dev/null | tr -d ' ')
  done
  if [ -n "$codex_fallback" ]; then
    local cands n mycwd="" matches
    cands=$(all_agents | awk '$2=="codex" {print $1}')
    n=$(echo "$cands" | grep -c .)
    if [ "$n" -eq 1 ]; then echo "$cands"; return; fi
    if [ "$n" -gt 1 ]; then
      if [ -n "${CODEX_THREAD_ID:-}" ] && [ -f "$BRIDGE_CODEX_ROOT/state_5.sqlite" ]; then
        mycwd=$(python3 -c 'import sqlite3,sys; r=sqlite3.connect(sys.argv[1]).execute("SELECT cwd FROM threads WHERE id=?",(sys.argv[2],)).fetchone(); print(r[0]) if r and r[0] else None' "$BRIDGE_CODEX_ROOT/state_5.sqlite" "$CODEX_THREAD_ID" 2>/dev/null)
      fi
      [ -z "$mycwd" ] && mycwd=$PWD
      matches=$(for c in $cands; do [ "$(cwd_of "$c")" = "$mycwd" ] && echo "$c"; done)
      if [ -n "$matches" ] && [ "$(echo "$matches" | grep -c .)" -eq 1 ]; then
        echo "$matches"; return
      fi
    fi
    echo "$codex_fallback"
  fi
}

# All running agent PIDs as "pid kind tty"
all_agents() {
  ps -axo pid=,tty=,args= | awk '
    { split($3, a, "/"); b = a[length(a)]; k = "" }
    b == "claude" || b == "agy" || b == "codex" || b == "codex-cli" || b == "gemini" { k = b }
    k == "codex-cli" { k = "codex" }
    k == "" && b == "node" && $0 ~ /gemini/ { k = "gemini" }
    k != "" { t = ($2 == "??" || $2 == "?") ? "" : $2; if (t != "") print $1, k, t }'
}

# ---- registry: one file per name, key=value lines ----
reg_get() { sed -n "s/^$2=//p" "$REG/$1" 2>/dev/null; }

reg_alive() {  # name -> 0 if the registered process is still the same process
  local pid st; pid=$(reg_get "$1" pid); st=$(reg_get "$1" lstart)
  [ -n "$pid" ] || return 1
  # One-time upgrade of entries written with the old drifting wall-clock lstart:
  # same pid, kind and tty still alive -> rewrite with the stable start tick.
  if [ "$OS" = Linux ] && [ "${st#t}" = "$st" ] && [ -n "$(kind_of "$pid")" ] &&
     [ "$(kind_of "$pid")" = "$(reg_get "$1" kind)" ] && [ "$(tty_of "$pid")" = "$(reg_get "$1" tty)" ]; then
    sed -i "s/^lstart=.*/lstart=$(lstart_of "$pid")/" "$REG/$1"; return 0
  fi
  [ "$(lstart_of "$pid")" = "$st" ]
}

name_of_pid() {  # live registered name for a pid, if any
  local f
  for f in "$REG"/*; do
    [ -f "$f" ] || continue
    [ "$(reg_get "${f##*/}" pid)" = "$1" ] && reg_alive "${f##*/}" && { echo "${f##*/}"; return; }
  done
}

label_of() {  # display/reply label for a pid
  local n; n=$(name_of_pid "$1")
  if [ -n "$n" ]; then echo "$n"; else echo "$(kind_of "$1"):$1"; fi
}

write_reg() {  # name pid
  {
    echo "pid=$2"; echo "kind=$(kind_of "$2")"; echo "lstart=$(lstart_of "$2")"
    echo "tty=$(tty_of "$2")"; echo "cwd=$(cwd_of "$2")"; echo "registered=$(date '+%F %T')"
  } > "$REG/$1"
}

# ---- conversation memory: $STATE/<pid>.from / .to = "own_lstart|peer_pid|peer_lstart" ----
remember() {  # owner_pid from|to peer_pid
  echo "$(lstart_of "$1")|$3|$(lstart_of "$3")" > "$STATE/$1.$2"
}
recall() {  # owner_pid from|to -> peer pid, if both are still the same processes
  local line own p ps
  line=$(cat "$STATE/$1.$2" 2>/dev/null) || return
  IFS='|' read -r own p ps <<< "$line"
  # One-time upgrade of records written with the old drifting wall-clock lstart.
  if [ "$OS" = Linux ] && [ "${own#t}" = "$own" ] && [ -n "$p" ] &&
     [ -n "$(kind_of "$1")" ] && [ -n "$(kind_of "$p")" ]; then
    remember "$1" "$2" "$p"; echo "$p"; return
  fi
  [ "$own" = "$(lstart_of "$1")" ] && [ -n "$p" ] && [ "$ps" = "$(lstart_of "$p")" ] && echo "$p"
}
partner() {  # me [kind] -> who last messaged me, else whom I last messaged
  local me=$1 k=$2 d p
  [ -n "$me" ] || return
  for d in from to; do
    p=$(recall "$me" "$d")
    [ -n "$p" ] && [ "$p" != "$me" ] || continue
    if [ -z "$k" ] || [ "$(kind_of "$p")" = "$k" ]; then echo "$p"; return; fi
  done
}

NOTE=""
reroute() {  # new_pid reason
  [ "$BRIDGE_NO_REROUTE" = 1 ] && return 1
  T_PID=$1; T_TTY=$(tty_of "$1")
  NOTE="rerouted '$TARGET' -> $(label_of "$1") ($2)"
  echo "send_to_tty: $NOTE" >&2
}

list_cands() {  # pids... -> stderr
  local pid
  for pid in "$@"; do echo "  $(label_of "$pid")  pid=$pid tty=$(tty_of "$pid") cwd=$(cwd_of "$pid" | sed "s#^$HOME#~#")" >&2; done
}

cmd_list() {
  local me; me=$(caller_pid)
  printf '%-22s %-14s %-7s %-8s %-8s %-8s %-32s %s\n' TITLE NAME KIND PID TTY VIA CWD "LAST FROM"
  all_agents | while read -r pid k t; do
    n=$(name_of_pid "$pid"); [ -z "$n" ] && n="-"
    [ "$pid" = "$me" ] && n="$n (you)"
    ti=$(title_of "$pid"); ti=${ti:--}
    lf=$(recall "$pid" from); lf=${lf:+$(label_of "$lf")}
    printf '%-22s %-14s %-7s %-8s %-8s %-8s %-32s %s\n' "$ti" "$n" "$k" "$pid" "${t:--}" "$( [ -n "$t" ] && transport_of "$t" || echo -)" "$(cwd_of "$pid" | sed "s#^$HOME#~#")" "${lf:--}"
  done
  echo "(TITLE = the session's /rename title, read live; usable as a target: send_to_tty.sh \"<title>\" \"msg\")"
  for f in "$REG"/*; do
    [ -f "$f" ] || continue
    reg_alive "${f##*/}" || echo "stale registration: ${f##*/} (pid $(reg_get "${f##*/}" pid) gone)"
  done
}

cmd_register() {
  local name=$1 force=$2 me old
  [[ "$name" =~ ^[A-Za-z][A-Za-z0-9._-]{0,31}$ ]] || die "name must be letters/digits/._- and start with a letter"
  case "$name" in claude|agy|codex|gemini|pid|reply) die "'$name' is reserved";; esac
  me=$(caller_pid); [ -n "$me" ] || die "not running inside an agent session (claude/agy/codex/gemini)"
  if [ -f "$REG/$name" ] && reg_alive "$name" && [ "$(reg_get "$name" pid)" != "$me" ] && [ "$force" != "--force" ]; then
    die "name '$name' is held by live pid $(reg_get "$name" pid); pick another name or add --force"
  fi
  old=$(name_of_pid "$me"); [ -n "$old" ] && [ "$old" != "$name" ] && rm -f "$REG/$old"
  write_reg "$name" "$me"
  echo "registered '$name' -> $(kind_of "$me") pid $me on $(tty_of "$me")${old:+ (was '$old')}"
}

# resolve: sets T_PID (may be empty for a raw tty) and T_TTY, correcting wrong targets
resolve() {
  local me=$1 pid k cands n p mycwd rk rcwd rtty
  T_PID=""; T_TTY=""
  case "$TARGET" in
    reply)
      T_PID=$(partner "$me")
      [ -n "$T_PID" ] || die "nobody has messaged you yet; use a name or kind:pid" ;;
    pid:*|claude:*|agy:*|codex:*|gemini:*)
      pid=${TARGET#*:}; [[ "$pid" =~ ^[0-9]+$ ]] || die "bad pid in '$TARGET'"
      ps -p "$pid" >/dev/null 2>&1 || die "pid $pid is not running"
      k=${TARGET%%:*}
      [ "$k" != pid ] && [ "$(kind_of "$pid")" != "$k" ] && die "pid $pid is not a $k session (it is: $(kind_of "$pid"))"
      T_PID=$pid ;;
    claude|agy|codex|gemini)
      cands=$(all_agents | awk -v k="$TARGET" -v me="$me" '$2==k && $1!=me {print $1}')
      n=$(echo "$cands" | grep -c .)
      [ "$n" -eq 0 ] && die "no other $TARGET session running"
      if [ "$n" -eq 1 ]; then T_PID=$cands
      else
        p=$(partner "$me" "$TARGET")
        if [ -n "$p" ] && reroute "$p" "$n ${TARGET} sessions running; picked your conversation partner"; then :
        else
          mycwd=$( [ -n "$me" ] && cwd_of "$me")
          p=$(for c in $cands; do [ -n "$mycwd" ] && [ "$(cwd_of "$c")" = "$mycwd" ] && echo "$c"; done)
          if [ -n "$p" ] && [ "$(echo "$p" | grep -c .)" -eq 1 ] && reroute "$p" "$n ${TARGET} sessions running; picked the only one in your folder"; then :
          else
            echo "send_to_tty: $n $TARGET sessions are running and none is your conversation partner; refusing to guess. Use a name or $TARGET:<pid>:" >&2
            list_cands $cands; exit 2
          fi
        fi
      fi ;;
    ttys*|/dev/ttys*|pts/*|/dev/pts/*)
      T_TTY=${TARGET#/dev/}
      T_PID=$(all_agents | awk -v t="$T_TTY" '$3==t {print $1; exit}') ;;
    *)
      if [ ! -f "$REG/$TARGET" ]; then
        # Not a registered name: match the sessions' live /rename titles.
        cands=$(pids_by_title "$TARGET")
        n=$(echo "$cands" | grep -c .)
        [ "$n" -eq 0 ] && die "unknown target '$TARGET': no registered name and no live session with that title (see --list)"
        if [ "$n" -gt 1 ]; then
          echo "send_to_tty: $n live sessions are titled '$TARGET'; refusing to guess. Use <kind>:<pid>:" >&2
          list_cands $cands; exit 2
        fi
        T_PID=$cands
      elif reg_alive "$TARGET"; then T_PID=$(reg_get "$TARGET" pid)
      else
        # The named session is gone. Hand the name to its unambiguous successor:
        # same kind, same folder, not already named (same tab preferred).
        rk=$(reg_get "$TARGET" kind); rcwd=$(reg_get "$TARGET" cwd); rtty=$(reg_get "$TARGET" tty)
        cands=$(all_agents | while read -r c ck ct; do
          [ "$ck" = "$rk" ] && [ "$c" != "$me" ] && [ -z "$(name_of_pid "$c")" ] && [ "$(cwd_of "$c")" = "$rcwd" ] && echo "$c $ct"
        done)
        [ "$(echo "$cands" | grep -c .)" -gt 1 ] && cands=$(echo "$cands" | awk -v t="$rtty" '$2==t')
        p=$(echo "$cands" | awk 'NF{print $1}')
        if [ -n "$p" ] && [ "$(echo "$p" | grep -c .)" -eq 1 ] && [ "$BRIDGE_NO_REROUTE" != 1 ]; then
          local oldpid; oldpid=$(reg_get "$TARGET" pid)
          [ -z "$DRY" ] && write_reg "$TARGET" "$p"
          reroute "$p" "'$TARGET' (pid $oldpid) exited; its successor in ${rcwd/#$HOME/~} took over the name"
        else
          die2 "'$TARGET' is registered to pid $(reg_get "$TARGET" pid), which has exited or been replaced, and no single successor was found; re-register it in its new session"
        fi
      fi ;;
  esac
  [ -n "$T_PID" ] && [ -z "$T_TTY" ] && T_TTY=$(tty_of "$T_PID")
  [ -n "$T_TTY" ] || die "target '$TARGET' has no terminal"

  # Addressed yourself: almost always a reply meant for your conversation partner.
  if [ -n "$me" ] && [ "$T_PID" = "$me" ] && [ "$BRIDGE_ALLOW_SELF" != 1 ]; then
    p=$(partner "$me")
    if [ -n "$p" ] && reroute "$p" "target was your own session; sent to your conversation partner"; then :
    else
      die2 "target '$TARGET' is your own session (pid $me on $T_TTY) and nobody has messaged you, so there is no one to reroute to"
    fi
  fi
}

# ---- agy dispatch gate (hard rule: both manager and executor must be STOPPED before dispatching to claude) ----
agy_state_of() {  # pid [tty] -> WORKING | STOPPED
  local pid=$1 t=${2:-$(tty_of "$1")} apid line plstart
  if [ -n "$t" ] && [ -f "/tmp/agy_anim_${t}.pid" ]; then
    apid=$(cat "/tmp/agy_anim_${t}.pid" 2>/dev/null)
    [ -n "$apid" ] && kill -0 "$apid" 2>/dev/null && { echo WORKING; return; }
  fi
  if [ -f "$STATE/${pid}.pending_exec" ]; then
    line=$(cat "$STATE/${pid}.pending_exec" 2>/dev/null)
    IFS='|' read -r plstart _ <<< "$line"
    if [ "$plstart" = "$(lstart_of "$pid")" ]; then
      echo WORKING; return
    else
      rm -f "$STATE/${pid}.pending_exec"
    fi
  fi
  echo STOPPED
}

enforce_agy_dispatch_gate() {  # me target_pid
  local me=$1 tgt=$2 mycwd peer_pid peer_k peer_tty line clstart
  [ "$BRIDGE_FORCE_DISPATCH" = 1 ] && return 0
  [ -n "$me" ] && [ -n "$tgt" ] || return 0
  [ "$(kind_of "$me")" = agy ] || return 0
  mycwd=$(cwd_of "$me")
  [ -n "$mycwd" ] || return 0

  if [ "$(kind_of "$tgt")" = claude ]; then
    while read -r peer_pid peer_k peer_tty; do
      [ "$peer_k" = agy ] && [ "$peer_pid" != "$me" ] || continue
      [ "$(cwd_of "$peer_pid")" = "$mycwd" ] || continue
      if [ "$(agy_state_of "$peer_pid" "$peer_tty")" = WORKING ]; then
        die2 "refused dispatch to $(label_of "$tgt"): peer agy session $(label_of "$peer_pid") (pid $peer_pid on $peer_tty) is still WORKING (not STOPPED). Hard rule: only when both manager and executor have finished working (both STOPPED) is dispatch to claude allowed."
      fi
    done < <(all_agents)
  elif [ "$(kind_of "$tgt")" = agy ] && [ "$tgt" != "$me" ] && [ "$(cwd_of "$tgt")" = "$mycwd" ]; then
    if [ -f "$STATE/${me}.claude_dispatched" ]; then
      line=$(cat "$STATE/${me}.claude_dispatched" 2>/dev/null)
      IFS='|' read -r clstart _ <<< "$line"
      if [ "$clstart" = "$(lstart_of "$me")" ]; then
        die2 "refused dispatch to $(label_of "$tgt"): you already dispatched to claude and are awaiting claude's reply. Hard rule: finish manager + executor work (both STOPPED) BEFORE dispatching to claude."
      else
        rm -f "$STATE/${me}.claude_dispatched"
      fi
    fi
  fi
}

# ---- delivery ----
# tmux pane id whose tty is /dev/$1 (searches the default server and $BRIDGE_TMUX_SOCKETS)
tmux_pane_of() {
  command -v tmux >/dev/null || return
  local sock
  for sock in "" $BRIDGE_TMUX_SOCKETS; do
    tmux ${sock:+-S "$sock"} list-panes -a -F '#{pane_tty} #{pane_id}' 2>/dev/null |
      awk -v t="/dev/$1" -v s="$sock" '$1==t {print s "|" $2; exit}'
  done | head -n1
}
# WSL: interop socket of the session owning tty $1 (/run/WSL/<Relay pid>_interop)
wsl_sock_of() {
  [ -d /run/WSL ] || return
  local p c
  p=$(ps -t "$1" -o pid= 2>/dev/null | head -n1 | tr -d ' ')
  while [ -n "$p" ] && [ "$p" -gt 1 ]; do
    c=$(ps -o comm= -p "$p" 2>/dev/null)
    case "$c" in Relay\(*) [ -S "/run/WSL/${p}_interop" ] && echo "/run/WSL/${p}_interop"; return ;; esac
    p=$(ps -o ppid= -p "$p" 2>/dev/null | tr -d ' ')
  done
}

# JSONL dialog guard for Claude Code targets: prints pending interactive tool name
# (AskUserQuestion / ExitPlanMode / Artifact) if the target session's transcript ends
# with an unanswered dialog prompt; empty if clear. Works on WSL, Linux, and macOS.
claude_open_dialog_of() {  # pid -> dialog tool name or empty
  local pid=$1 sfile sid
  [ -n "$pid" ] || return 0
  sfile="$HOME/.claude/sessions/$pid.json"
  [ -f "$sfile" ] || return 0
  sid=$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("sessionId",""))' "$sfile" 2>/dev/null)
  [ -n "$sid" ] || return 0
  python3 - "$HOME/.claude/projects" "$sid" <<'PY' 2>/dev/null || true
import glob, json, os, sys

proj_root, sid = sys.argv[1], sys.argv[2]
matches = glob.glob(os.path.join(proj_root, "*", f"{sid}.jsonl"))
if not matches:
    sys.exit(0)
path = matches[0]
try:
    size = os.path.getsize(path)
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        if size > 262144:
            fh.seek(size - 262144)
            fh.readline()
        pending = {}
        active_msg = None
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            rtype = rec.get("type")
            msg = rec.get("message")
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if rtype == "assistant":
                mid = msg.get("id")
                if mid and active_msg and mid != active_msg and pending:
                    pending.clear()
                if mid:
                    active_msg = mid
                if isinstance(content, list):
                    for blk in content:
                        if isinstance(blk, dict) and blk.get("type") == "tool_use":
                            tname = blk.get("name", "")
                            tid = blk.get("id", "")
                            if tname in ("AskUserQuestion", "ExitPlanMode", "Artifact") and tid:
                                pending[tid] = tname
            elif rtype == "user":
                if isinstance(content, list):
                    for blk in content:
                        if isinstance(blk, dict) and blk.get("type") == "tool_result":
                            pending.pop(blk.get("tool_use_id", ""), None)
                        elif isinstance(blk, dict) and blk.get("type") == "text":
                            pending.clear()
                elif isinstance(content, str) and content.strip():
                    pending.clear()
        if pending:
            print(list(pending.values())[-1])
except OSError:
    pass
PY
}

wait_claude_json_dialog() {  # pid tty -> 0 if clear, 1 if still open (sets dlg)
  local pid=$1 tty=$2 dlg elapsed=0
  local poll=${BRIDGE_PROMPT_POLL_SECS:-5} wait_max=${BRIDGE_PROMPT_WAIT_SECS:-60}
  [ "${BRIDGE_FORCE_SEND:-0}" = 1 ] && return 0
  dlg=$(claude_open_dialog_of "$pid")
  while [ -n "$dlg" ] && [ "$elapsed" -lt "$wait_max" ]; do
    sleep "$poll"
    elapsed=$((elapsed + poll))
    dlg=$(claude_open_dialog_of "$pid")
  done
  if [ -n "$dlg" ]; then
    echo "not sent: target has open interactive dialog ($dlg) on /dev/$tty"
    return 1
  fi
  return 0
}

WIN_PS=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
wt_ok() { [ -x "$WIN_PS" ] && [ -n "$(wsl_sock_of "$1")" ]; }
wt_send() {  # tty text submit is_claude
  local sock; sock=$(wsl_sock_of "$1")
  [ -S "$sock" ] || { echo "BRIDGE_STATUS:socket_missing"; return 1; }
  WSL_INTEROP=$sock \
    BRIDGE_B64=$(printf '%s' "$2" | base64 -w0) \
    BRIDGE_SUBMIT=$3 \
    BRIDGE_IS_CLAUDE=${4:-0} \
    BRIDGE_FORCE_SEND=${BRIDGE_FORCE_SEND:-0} \
    BRIDGE_READ_ONLY=${BRIDGE_READ_ONLY:-0} \
    BRIDGE_NO_AUTO_ESC=${BRIDGE_NO_AUTO_ESC:-0} \
    BRIDGE_PROMPT_POLL_SECS=${BRIDGE_PROMPT_POLL_SECS:-5} \
    BRIDGE_PROMPT_WAIT_SECS=${BRIDGE_PROMPT_WAIT_SECS:-60} \
    WSLENV='BRIDGE_B64:BRIDGE_SUBMIT:BRIDGE_IS_CLAUDE:BRIDGE_FORCE_SEND:BRIDGE_READ_ONLY:BRIDGE_NO_AUTO_ESC:BRIDGE_PROMPT_POLL_SECS:BRIDGE_PROMPT_WAIT_SECS' \
    "$WIN_PS" -NoProfile -NonInteractive -ExecutionPolicy Bypass \
    -File "$(wslpath -w "$(dirname "$(readlink -f "$0")")/conin_inject.ps1")" </dev/null 2>&1 | tr -d '\r'
}
read_screen() {  # tty
  local tty=$1 tp sock pane
  tp=$(tmux_pane_of "$tty")
  if [ -n "$tp" ]; then
    sock=${tp%%|*}; pane=${tp#*|}
    tmux ${sock:+-S "$sock"} capture-pane -p -t "$pane" 2>/dev/null
  elif wt_ok "$tty"; then
    BRIDGE_READ_ONLY=1 wt_send "$tty" "" 0 0
  elif [ "$OS" = Darwin ]; then
    local hist; hist=$(macos_tab_history "$tty")
    if [ "$hist" != "__TTY_NOT_FOUND__" ]; then
      printf '%s\n' "$hist"
    else
      echo "tty not found: /dev/$tty" >&2
      return 1
    fi
  else
    echo "screen read not supported for transport on /dev/$tty" >&2
    return 1
  fi
}
tiocsti_ok() { [ "$(cat /proc/sys/dev/tty/legacy_tiocsti 2>/dev/null)" = 1 ] && [ -w "/dev/$1" ]; }
transport_of() {  # tty -> tmux|wt|tiocsti|terminal.app|none
  if [ "$OS" = Darwin ]; then echo terminal.app; return; fi
  [ -n "$(tmux_pane_of "$1")" ] && { echo tmux; return; }
  wt_ok "$1" && { echo wt; return; }
  tiocsti_ok "$1" && { echo tiocsti; return; }
  echo none
}
tiocsti() {  # tty text
  python3 - "/dev/$1" "$2" <<'PY'
import fcntl, sys, termios
with open(sys.argv[1], 'wb', buffering=0) as f:
    for b in sys.argv[2].encode():
        fcntl.ioctl(f, termios.TIOCSTI, bytes([b]))
PY
}
deliver_linux() {  # tty msg submit is_claude tgt_pid
  local tty=$1 msg=$2 sub=$3 claude_tgt=${4:-0} tgt_pid=${5:-} tp sock pane
  if [ "$claude_tgt" = 1 ] && [ -n "$tgt_pid" ]; then
    local jmsg
    jmsg=$(wait_claude_json_dialog "$tgt_pid" "$tty") || { echo "$jmsg"; return; }
  fi
  tp=$(tmux_pane_of "$tty")
  if [ -n "$tp" ]; then
    sock=${tp%%|*}; pane=${tp#*|}
    tm() { tmux ${sock:+-S "$sock"} "$@"; }
    local poll=${BRIDGE_PROMPT_POLL_SECS:-5} wait_max=${BRIDGE_PROMPT_WAIT_SECS:-60} elapsed=0 st hist panel_note="" attempt
    if [ "$claude_tgt" = 1 ] && [ "${BRIDGE_FORCE_SEND:-0}" != 1 ]; then
      hist=$(tm capture-pane -p -t "$pane" 2>/dev/null)
      st=$(printf '%s\n' "$hist" | claude_prompt_state)
      if [ "$st" = unknown ]; then
        if [ "${BRIDGE_NO_AUTO_ESC:-0}" != 1 ] && printf '%s\n' "$hist" | claude_is_settings_panel; then
          hist=$(tm capture-pane -p -t "$pane" 2>/dev/null)
          st=$(printf '%s\n' "$hist" | claude_prompt_state)
          if [ "$st" = unknown ] && printf '%s\n' "$hist" | claude_is_settings_panel; then
            tm send-keys -t "$pane" Escape Escape
            sleep 1.5
            hist=$(tm capture-pane -p -t "$pane" 2>/dev/null)
            st=$(printf '%s\n' "$hist" | claude_prompt_state)
            [ "$st" != unknown ] && panel_note=" (closed /usage panel)"
          fi
        fi
        while [ "$st" = unknown ] && [ "$elapsed" -lt "$wait_max" ]; do
          sleep "$poll"
          elapsed=$((elapsed + poll))
          hist=$(tm capture-pane -p -t "$pane" 2>/dev/null)
          st=$(printf '%s\n' "$hist" | claude_prompt_state)
        done
        if [ "$st" = unknown ]; then
          echo "not sent: target not at its prompt (/dev/$tty)"
          return
        fi
      fi
    fi
    if [ "$sub" = 1 ]; then
      tm send-keys -t "$pane" -l -- "$msg" || { echo "tmux send failed: $pane"; return; }
      if [ "$claude_tgt" = 1 ] && [ "${BRIDGE_FORCE_SEND:-0}" != 1 ]; then
        sleep 1.5
        for attempt in 1 2 3 4; do
          tm send-keys -t "$pane" Enter
          sleep 0.6
          st=$(tm capture-pane -p -t "$pane" 2>/dev/null | claude_prompt_state)
          case "$st" in
            empty)
              echo "sent+enter to /dev/$tty (tmux $pane)${panel_note}"
              return ;;
            unknown)
              if [ "$attempt" -eq 1 ]; then
                sleep 1.4
                tm send-keys -t "$pane" Enter
              fi
              echo "sent+enter (unverified) to /dev/$tty (tmux $pane)${panel_note}"
              return ;;
            text)
              [ "$attempt" -lt 4 ] && sleep 1.4 ;;
          esac
        done
        echo "sent (unsubmitted: prompt still holds text) to /dev/$tty (tmux $pane)${panel_note}"
        return
      fi
      sleep 1.5; tm send-keys -t "$pane" Enter; sleep 2; tm send-keys -t "$pane" Enter
      echo "sent+enter to /dev/$tty (tmux $pane)${panel_note}"
    else
      # text + CR in one chunk, like Terminal.app's do script
      tm send-keys -t "$pane" -l -- "$msg"$'\r' || { echo "tmux send failed: $pane"; return; }
      echo "sent to /dev/$tty (tmux $pane)"
    fi
  elif wt_ok "$tty"; then
    local out status_line payload="$msg"
    [ "$sub" = 1 ] || payload="$msg"$'\r'
    out=$(wt_send "$tty" "$payload" "$sub" "$claude_tgt")
    if [ "${BRIDGE_READ_ONLY:-0}" = 1 ]; then
      printf '%s\n' "$out"
      return
    fi
    status_line=$(printf '%s\n' "$out" | sed -n 's/^BRIDGE_STATUS://p' | tail -n1)
    case "$status_line" in
      ok)
        [ "$sub" = 1 ] && echo "sent+enter to /dev/$tty (windows terminal)" || echo "sent to /dev/$tty (windows terminal)" ;;
      ok_closed_panel)
        [ "$sub" = 1 ] && echo "sent+enter to /dev/$tty (windows terminal, closed /usage panel)" || echo "sent to /dev/$tty (windows terminal, closed /usage panel)" ;;
      ok_unverified)
        echo "sent+enter (unverified) to /dev/$tty (windows terminal)" ;;
      ok_unverified_closed_panel)
        echo "sent+enter (unverified) to /dev/$tty (windows terminal, closed /usage panel)" ;;
      unsubmitted)
        echo "sent (unsubmitted: prompt still holds text) to /dev/$tty (windows terminal)" ;;
      unsubmitted_closed_panel)
        echo "sent (unsubmitted: prompt still holds text) to /dev/$tty (windows terminal, closed /usage panel)" ;;
      not_at_prompt:*)
        echo "not sent: target not at its prompt (${status_line#not_at_prompt:}) on /dev/$tty (windows terminal)" ;;
      *)
        echo "windows terminal send failed: /dev/$tty: $(printf '%s\n' "$out" | tail -n 3 | tr '\n' ' ')" ;;
    esac
  elif tiocsti_ok "$tty"; then
    local payload="$msg"
    [ "$sub" = 1 ] || payload="$msg"$'\r'
    tiocsti "$tty" "$payload" || { echo "tiocsti failed: /dev/$tty"; return; }
    if [ "$sub" = 1 ]; then sleep 1.5; tiocsti "$tty" $'\r'; sleep 2; tiocsti "$tty" $'\r'; echo "sent+enter to /dev/$tty (tiocsti)"
    else echo "sent to /dev/$tty (tiocsti)"; fi
  else
    echo "no transport for /dev/$tty: not a tmux pane, no WSL interop socket, and TIOCSTI is disabled"
  fi
}

[ "${BRIDGE_READ_ONLY:-0}" = 1 ] && READ=1

case "$1" in
  --list|-l)  cmd_list; exit ;;
  --whoami)   me=$(caller_pid); [ -n "$me" ] || die "not inside an agent session"
              p=$(partner "$me")
              echo "$(label_of "$me") ($(kind_of "$me") pid $me on $(tty_of "$me"))${p:+; reply goes to $(label_of "$p")}"; exit ;;
  --register) [ -n "$2" ] || die "usage: --register <name> [--force]"; cmd_register "$2" "$3"; exit ;;
  --read)     READ=1; shift ;;
  --dry-run)  DRY=1; shift ;;
  --raw)      RAW=1; shift ;;
  ""|-h|--help) sed -n '2,39p' "$0" | sed 's/^# \{0,1\}//'; exit ;;
esac

TARGET=$1; shift
me=$(caller_pid)
if [ -n "$DRY" ]; then
  resolve "$me"
  enforce_agy_dispatch_gate "$me" "$T_PID"
  echo "would send to $( [ -n "$T_PID" ] && label_of "$T_PID" || echo "?") (pid ${T_PID:--}, $T_TTY, via $(transport_of "$T_TTY"))"
  exit 0
fi

resolve "$me"

if [ -n "$READ" ]; then
  read_out=$(read_screen "$T_TTY")
  rc=$?
  if [ $rc -eq 0 ]; then
    printf '%s\n' "$read_out"
    lines=$(printf '%s\n' "$read_out" | grep -c '^')
    sender=$( [ -n "$me" ] && label_of "$me" || echo "user@$(tty 2>/dev/null | sed 's#/dev/##')" )
    echo "$(date '+%F %T') from=$sender(pid ${me:--}) target=$TARGET -> pid=${T_PID:--} tty=$T_TTY result=read $lines lines from /dev/$T_TTY (via $(transport_of "$T_TTY"))" >> "$LOG"
    exit 0
  else
    echo "read failed for /dev/$T_TTY (via $(transport_of "$T_TTY")): $read_out" >&2
    exit 1
  fi
fi

[ -n "$*" ] || die "empty message"
enforce_agy_dispatch_gate "$me" "$T_PID"

sender=$( [ -n "$me" ] && label_of "$me" || echo "user@$(tty 2>/dev/null | sed 's#/dev/##')" )
if [ -n "$RAW" ]; then msg="$*"; else msg="[from $sender] $*"; fi
msg=$(printf '%s' "$msg" | tr '\n\r' '  ')

# Claude Code and Codex treat a typed burst ("text\r" in one chunk) as a paste
# and swallow its Return; send lone Returns afterwards.
submit=0
is_claude=0
[ -n "$T_PID" ] && [ "$(kind_of "$T_PID")" = claude ] && { submit=1; is_claude=1; }
ps -t "$T_TTY" -o comm= 2>/dev/null | grep -qE '(^|/)claude$' && { submit=1; is_claude=1; }
[ -n "$T_PID" ] && [ "$(kind_of "$T_PID")" = codex ] && submit=1
ps -t "$T_TTY" -o comm= 2>/dev/null | grep -qE '(^|/)(codex|codex-cli)$' && submit=1
# --raw: a slash command opens the target's command menu, which takes the first
# Return; the lone Returns afterwards run it (tested on Codex 0.167.2, macOS).
[ -n "$RAW" ] && submit=1

macos_do_script() {  # tty text -> "ok" | "tty not found: /dev/..."
  osascript - "/dev/$1" "$2" <<'OSA'
on run argv
  set tgt to item 1 of argv
  set msg to item 2 of argv
  tell application "Terminal"
    repeat with w in windows
      repeat with t in tabs of w
        if tty of t is tgt then
          do script msg in t
          return "ok"
        end if
      end repeat
    end repeat
  end tell
  return "tty not found: " & tgt
end run
OSA
}

macos_tab_history() {  # tty -> terminal history text, or "__TTY_NOT_FOUND__"
  osascript - "/dev/$1" <<'OSA'
on run argv
  set tgt to item 1 of argv
  tell application "Terminal"
    repeat with w in windows
      repeat with t in tabs of w
        if tty of t is tgt then
          return history of t
        end if
      end repeat
    end repeat
  end tell
  return "__TTY_NOT_FOUND__"
end run
OSA
}

# Prints "text", "empty", or "unknown" for Claude Code's input box (between the last two horizontal rules).
claude_prompt_state() {
  python3 -c '
import re, sys
try:
    lines = sys.stdin.read().split("\n")
    non_empty = [ln for ln in lines if ln.strip()]
    footer = "\n".join(non_empty[-4:])
    if re.search(r"Enter to select|Enter to confirm|Esc to cancel|to navigate|Tab to amend|Do you trust the contents of this", footer):
        print("unknown")
        sys.exit(0)
    rule_idx = [i for i, ln in enumerate(lines) if ln.count("─") >= 20]
    if len(rule_idx) < 2:
        print("unknown")
        sys.exit(0)
    box = "\n".join(lines[rule_idx[-2] + 1 : rule_idx[-1]]).replace("\xa0", " ").lstrip()
    if box.startswith("❯"):
        box = box[1:]
    print("text" if box.strip() else "empty")
except Exception:
    print("unknown")
' 2>/dev/null || echo unknown
}

# Returns 0 if stdin shows the Claude Code settings/usage panel (20+ "▔" line immediately followed by Settings/Status/Config/Usage/Stats header).
claude_is_settings_panel() {
  python3 -c '
import sys
lines = sys.stdin.read().split("\n")
tabs = ("Settings", "Status", "Config", "Usage", "Stats")
ok = any(
    lines[i].count("▔") >= 20 and all(w in lines[i + 1] for w in tabs)
    for i in range(len(lines) - 1)
)
sys.exit(0 if ok else 1)
' 2>/dev/null
}

deliver_macos() {  # tty msg submit is_claude tgt_pid
  local tty=$1 msg=$2 sub=$3 claude_tgt=$4 tgt_pid=${5:-} res attempt st hist panel_note=""
  local poll=${BRIDGE_PROMPT_POLL_SECS:-5} wait_max=${BRIDGE_PROMPT_WAIT_SECS:-60} elapsed=0
  if [ "$claude_tgt" = 1 ]; then
    if [ -n "$tgt_pid" ]; then
      local jmsg
      jmsg=$(wait_claude_json_dialog "$tgt_pid" "$tty") || { echo "$jmsg"; return; }
    fi
    hist=$(macos_tab_history "$tty")
    [ "$hist" = "__TTY_NOT_FOUND__" ] && { echo "tty not found: /dev/$tty"; return; }
    st=$(printf '%s\n' "$hist" | claude_prompt_state)
    if [ "$st" = unknown ] && [ "${BRIDGE_FORCE_SEND:-0}" != 1 ]; then
      if [ "${BRIDGE_NO_AUTO_ESC:-0}" != 1 ] && printf '%s\n' "$hist" | claude_is_settings_panel; then
        hist=$(macos_tab_history "$tty")
        [ "$hist" = "__TTY_NOT_FOUND__" ] && { echo "tty not found: /dev/$tty"; return; }
        st=$(printf '%s\n' "$hist" | claude_prompt_state)
        if [ "$st" = unknown ] && printf '%s\n' "$hist" | claude_is_settings_panel; then
          macos_do_script "$tty" $'\e\e' >/dev/null
          sleep 1.5
          hist=$(macos_tab_history "$tty")
          [ "$hist" = "__TTY_NOT_FOUND__" ] && { echo "tty not found: /dev/$tty"; return; }
          st=$(printf '%s\n' "$hist" | claude_prompt_state)
          [ "$st" != unknown ] && panel_note=" (closed /usage panel)"
        fi
      fi
      while [ "$st" = unknown ] && [ "$elapsed" -lt "$wait_max" ]; do
        sleep "$poll"
        elapsed=$((elapsed + poll))
        hist=$(macos_tab_history "$tty")
        [ "$hist" = "__TTY_NOT_FOUND__" ] && { echo "tty not found: /dev/$tty"; return; }
        st=$(printf '%s\n' "$hist" | claude_prompt_state)
      done
      if [ "$st" = unknown ]; then
        echo "not sent: target not at its prompt (/dev/$tty)"
        return
      fi
    fi
  fi
  res=$(macos_do_script "$tty" "$msg")
  [ "$res" = ok ] || { echo "$res"; return; }
  if [ "$sub" != 1 ]; then
    echo "sent to /dev/$tty"
    return
  fi
  if [ "$claude_tgt" = 1 ]; then
    sleep 1.5
    for attempt in 1 2 3 4; do
      macos_do_script "$tty" "" >/dev/null
      sleep 0.6
      st=$(macos_tab_history "$tty" | claude_prompt_state)
      case "$st" in
        empty)
          echo "sent+enter to /dev/$tty${panel_note}"
          return ;;
        unknown)
          if [ "$attempt" -eq 1 ]; then
            sleep 1.4
            macos_do_script "$tty" "" >/dev/null
          fi
          echo "sent+enter (unverified) to /dev/$tty${panel_note}"
          return ;;
        text)
          [ "$attempt" -lt 4 ] && sleep 1.4 ;;
      esac
    done
    echo "sent (unsubmitted: prompt still holds text) to /dev/$tty${panel_note}"
    return
  fi
  sleep 1.5; macos_do_script "$tty" "" >/dev/null
  sleep 2;   macos_do_script "$tty" "" >/dev/null
  echo "sent+enter to /dev/$tty"
}

if [ "$OS" = Linux ]; then
  result=$(deliver_linux "$T_TTY" "$msg" "$submit" "$is_claude" "$T_PID")
else
  result=$(deliver_macos "$T_TTY" "$msg" "$submit" "$is_claude" "$T_PID")
fi
case "$result" in
  sent*)
    if [ -n "$me" ] && [ -n "$T_PID" ]; then
      remember "$T_PID" from "$me"
      remember "$me" to "$T_PID"
      if [ "$(kind_of "$me")" = agy ] && [ "$(kind_of "$T_PID")" = agy ] && [ "$T_PID" != "$me" ] && [ "$(cwd_of "$T_PID")" = "$(cwd_of "$me")" ]; then
        if [ -f "$STATE/${me}.pending_exec" ]; then
          rm -f "$STATE/${me}.pending_exec"
        else
          echo "$(lstart_of "$T_PID")|$me|$(date +%s)" > "$STATE/${T_PID}.pending_exec"
        fi
      elif [ "$(kind_of "$me")" = agy ] && [ "$(kind_of "$T_PID")" = claude ]; then
        echo "$(lstart_of "$me")|$T_PID|$(date +%s)" > "$STATE/${me}.claude_dispatched"
      elif [ "$(kind_of "$me")" = claude ] && [ "$(kind_of "$T_PID")" = agy ]; then
        rm -f "$STATE/${T_PID}.claude_dispatched"
      fi
    fi ;;
esac
echo "$(date '+%F %T') from=$sender(pid ${me:--}) target=$TARGET -> pid=${T_PID:--} tty=$T_TTY submit=$submit${NOTE:+ [$NOTE]} result=$result msg=${msg:0:80}" >> "$LOG"
echo "$result${NOTE:+ ($NOTE)}"
case "$result" in
  "sent (unsubmitted"*) exit 3 ;;
  sent*) exit 0 ;;
  *) exit 1 ;;
esac
