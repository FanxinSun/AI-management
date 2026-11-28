#!/usr/bin/env python3
"""codex_auto_resume.py - Autonomous usage-limit watcher and resume utility for Codex sessions.

Monitors active OpenAI Codex CLI sessions on Linux/WSL. When a session halts due to hitting
the 5-hour quota limit (or weekly limit), this tool parses the exact reset timestamp,
waits until quota resets, and automatically injects a resume instruction via send_to_tty.sh.

Can be run:
  codex_auto_resume.py --status            # Display status of all running Codex sessions
  codex_auto_resume.py --check             # One-shot check & auto-resume eligible sessions
  codex_auto_resume.py --watch             # Run continuously in foreground
  codex_auto_resume.py --resume <target>   # Force immediate resume on target session
  codex_auto_resume.py --install           # Install systemd user service and timer
  codex_auto_resume.py --uninstall         # Remove systemd user service and timer
"""

import argparse
import datetime
import glob
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

BRIDGE_DIR = Path(os.environ.get("BRIDGE_DIR", Path.home() / ".claude" / "agy-bridge"))
CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
STATE_FILE = BRIDGE_DIR / "codex_resume_state.json"
LOG_FILE = BRIDGE_DIR / "codex_resume.log"

SEND_TO_TTY_CANDIDATES = [
    Path.home() / ".local" / "bin" / "send_to_tty",
    Path.home() / "AI-management" / "general" / "tools" / "agent-bridge" / "send_to_tty.sh",
]


def find_send_to_tty():
    which = shutil.which("send_to_tty")
    if which:
        return which
    for candidate in SEND_TO_TTY_CANDIDATES:
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return "send_to_tty"


def log_event(message: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    line = f"{timestamp} {message}\n"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
    print(line.strip())


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        tmp.replace(STATE_FILE)
    except Exception as e:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def get_registered_bridge_sessions() -> dict:
    """Returns mapping {pid: {'name': name, 'tty': tty, 'cwd': cwd, 'kind': kind}}."""
    sessions_dir = BRIDGE_DIR / "sessions"
    reg = {}
    if not sessions_dir.exists():
        return reg
    for f in sessions_dir.iterdir():
        if not f.is_file():
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
            props = {}
            for line in content.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    props[k.strip()] = v.strip()
            pid_str = props.get("pid")
            if pid_str and pid_str.isdigit():
                pid = int(pid_str)
                reg[pid] = {
                    "name": f.name,
                    "tty": props.get("tty", ""),
                    "cwd": props.get("cwd", ""),
                    "kind": props.get("kind", ""),
                }
        except Exception:
            pass
    return reg


def find_codex_processes() -> list:
    """Finds running Codex TUI processes from /proc."""
    procs = []
    reg_sessions = get_registered_bridge_sessions()

    for pid_path in glob.glob("/proc/[0-9]*"):
        try:
            pid = int(os.path.basename(pid_path))
            cmdline_file = os.path.join(pid_path, "cmdline")
            with open(cmdline_file, "rb") as f:
                raw = f.read().split(b"\x00")
            if not raw or not raw[0]:
                continue
            prog = os.path.basename(raw[0].decode("utf-8", errors="ignore"))
            args = [c.decode("utf-8", errors="ignore") for c in raw if c]
            cmd_str = " ".join(args)

            # Exclude backend daemon, app-server, grep, python wrappers
            if prog in ("codex", "codex-cli") and "app-server" not in cmd_str and "daemon" not in cmd_str:
                cwd = ""
                try:
                    cwd = os.readlink(os.path.join(pid_path, "cwd"))
                except Exception:
                    pass

                tty = ""
                try:
                    stdin_link = os.readlink(os.path.join(pid_path, "fd", "0"))
                    if stdin_link.startswith("/dev/pts/"):
                        tty = stdin_link.replace("/dev/", "")
                except Exception:
                    pass

                name = ""
                if pid in reg_sessions:
                    name = reg_sessions[pid].get("name", "")

                procs.append({
                    "pid": pid,
                    "tty": tty,
                    "cwd": cwd,
                    "name": name,
                    "cmdline": args,
                    "cmd_str": cmd_str,
                })
        except Exception:
            continue
    return procs


def get_thread_info_for_proc(proc: dict) -> dict:
    """Matches a Codex process to its thread in state_5.sqlite and rollout file."""
    db_path = CODEX_HOME / "state_5.sqlite"
    res = {
        "thread_id": "",
        "title": "",
        "rollout_path": "",
        "primary_used_percent": 0.0,
        "resets_at": 0,
        "secondary_used_percent": 0.0,
        "weekly_resets_at": 0,
        "rate_limited": False,
        "rate_limit_type": None,
    }

    cmd_str = proc["cmd_str"]
    cwd = proc["cwd"]

    # 1. Check if thread ID is in command line: codex resume <id>
    resume_match = re.search(r"resume\s+([0-9a-fA-F-]{36})", cmd_str)
    thread_id = resume_match.group(1) if resume_match else ""

    # 2. Query state_5.sqlite
    if db_path.exists():
        try:
            con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            cur = con.cursor()
            row = None
            if thread_id:
                cur.execute("SELECT id, rollout_path, title, cwd FROM threads WHERE id=?", (thread_id,))
                row = cur.fetchone()
            elif cwd:
                # Match by CWD, order by updated_at descending
                cur.execute("SELECT id, rollout_path, title, cwd FROM threads WHERE cwd=? ORDER BY updated_at DESC LIMIT 1", (cwd,))
                row = cur.fetchone()

            if row:
                res["thread_id"] = row[0]
                res["rollout_path"] = row[1]
                res["title"] = row[2] or ""
            con.close()
        except Exception:
            pass

    # 3. Read rollout file for latest rate limits
    rpath = res["rollout_path"]
    if rpath and os.path.exists(rpath):
        latest_tc = None
        try:
            with open(rpath, "r", errors="ignore") as f:
                for line in f:
                    if '"type":"token_count"' in line or '"type": "token_count"' in line:
                        try:
                            obj = json.loads(line)
                            p = obj.get("payload", {})
                            if p.get("type") == "token_count":
                                latest_tc = p
                        except Exception:
                            pass
        except Exception:
            pass

        if latest_tc:
            rl = latest_tc.get("rate_limits", {})
            pri = rl.get("primary", {})
            sec = rl.get("secondary", {})
            res["primary_used_percent"] = float(pri.get("used_percent") or 0.0)
            res["resets_at"] = int(pri.get("resets_at") or 0)
            res["secondary_used_percent"] = float(sec.get("used_percent") or 0.0)
            res["weekly_resets_at"] = int(sec.get("resets_at") or 0)
            res["rate_limit_type"] = rl.get("rate_limit_reached_type")

    return res


def inspect_screen_for_limits(target: str) -> tuple[bool, int]:
    """Inspects screen buffer via send_to_tty --read. Returns (is_rate_limited, parsed_reset_epoch)."""
    send_cmd = find_send_to_tty()
    try:
        res = subprocess.run([send_cmd, "--read", target], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        output = res.stdout
    except Exception:
        return False, 0

    is_limited = False
    parsed_reset = 0

    # Strict check: only match when 5h 0% left or explicit active limit error message.
    # Never match generic "usage limit" or "0% left" in scrollback/previous messages.
    has_zero_left = bool(re.search(r"5h\s+0%\s+left", output, re.IGNORECASE))
    has_limit_banner = bool(re.search(r"(?:You['’]ve\s+hit\s+your\s+usage\s+limit|rate\s+limit\s+reached)", output, re.IGNORECASE))
    has_try_again = bool(re.search(r"try\s+again\s+at\s+([0-9]{1,2}:[0-9]{2}(?:\s*[AP]M)?)", output, re.IGNORECASE))

    if has_zero_left or (has_limit_banner and has_try_again):
        is_limited = True

    # Look specifically for "try again at HH:MM AM/PM" or "5h limit: 0% left · resets at HH:MM"
    m = re.search(r"(?:try again at|0%\s+left\s+·\s+resets\s+at)\s+([0-9]{1,2}:[0-9]{2}(?:\s*[AP]M)?)", output, re.IGNORECASE)
    if m:
        time_str = m.group(1).strip()
        now = datetime.datetime.now()
        for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M"):
            try:
                t = datetime.datetime.strptime(time_str, fmt).time()
                reset_dt = datetime.datetime.combine(now.date(), t)
                if reset_dt < now:
                    reset_dt += datetime.timedelta(days=1)
                parsed_reset = int(reset_dt.timestamp())
                break
            except Exception:
                continue

    return is_limited, parsed_reset


def get_session_records() -> list:
    """Aggregates all running Codex sessions with their limits and statuses."""
    procs = find_codex_processes()
    records = []
    now = time.time()

    for p in procs:
        target_name = p["name"] if p["name"] else f"codex:{p['pid']}"
        info = get_thread_info_for_proc(p)
        rec = {
            "pid": p["pid"],
            "tty": p["tty"],
            "cwd": p["cwd"],
            "name": p["name"],
            "target": target_name,
            "thread_id": info["thread_id"],
            "title": info["title"],
            "rollout_path": info["rollout_path"],
            "5h_used": info["primary_used_percent"],
            "resets_at": info["resets_at"],
            "weekly_used": info["secondary_used_percent"],
            "weekly_resets_at": info["weekly_resets_at"],
            "rate_limited": False,
            "seconds_remaining": 0,
            "status": "RUNNING",
        }

        # Validate resets_at: must not be a stale timestamp hours/days in the past
        # Valid window: [now - 300, now + 6 * 3600]
        valid_resets_at = False
        if rec["resets_at"] and (now - 300 <= rec["resets_at"] <= now + 6 * 3600):
            valid_resets_at = True
            rem = rec["resets_at"] - now
            rec["seconds_remaining"] = max(0, int(rem))
        elif rec["resets_at"] and rec["resets_at"] < now - 300:
            # Stale historical reset timestamp from previous days/sessions; clear it
            rec["resets_at"] = 0
            rec["seconds_remaining"] = 0

        # Rate limit determination:
        # 1. Rollout is primary source of truth: if used_percent < 99.0 and no rate_limit_type, session is NOT rate limited.
        if info["primary_used_percent"] < 99.0 and info["rate_limit_type"] is None:
            rec["rate_limited"] = False
            rec["status"] = "OK"
        else:
            is_limited_by_rollout = (info["primary_used_percent"] >= 99.0 or info["rate_limit_type"] is not None)
            screen_limited, screen_reset = inspect_screen_for_limits(target_name)

            if is_limited_by_rollout or screen_limited:
                rec["rate_limited"] = True
                if screen_reset and not rec["resets_at"]:
                    rec["resets_at"] = screen_reset
                    rem = rec["resets_at"] - now
                    rec["seconds_remaining"] = max(0, int(rem))

                if rec["seconds_remaining"] > 0:
                    rec["status"] = "RATE_LIMITED"
                else:
                    rec["status"] = "READY_TO_RESUME"
            else:
                rec["status"] = "OK"

        records.append(rec)
    return records


def format_countdown(seconds: int) -> str:
    if seconds <= 0:
        return "00:00:00"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def cmd_status():
    records = get_session_records()
    if not records:
        print("No active Codex sessions found.")
        return 0

    print(f"{'TARGET':<16} {'PID':<8} {'TTY':<8} {'5H-USED':<10} {'RESETS IN':<12} {'WEEKLY':<10} {'STATUS':<15} {'CWD'}")
    print("-" * 105)
    for r in records:
        countdown = format_countdown(r["seconds_remaining"]) if r["resets_at"] else "-"
        used_5h = f"{r['5h_used']:.1f}%"
        used_wk = f"{r['weekly_used']:.1f}%"
        print(f"{r['target']:<16} {r['pid']:<8} {r['tty']:<8} {used_5h:<10} {countdown:<12} {used_wk:<10} {r['status']:<15} {r['cwd']}")
    return 0


def resume_session(target: str, pid: int, reason: str = "quota reset") -> bool:
    send_cmd = find_send_to_tty()
    msg = (
        "[from codex-auto-resume] Your 5-hour usage limit has reset. "
        "Resume execution from where you stopped under the active handover. "
        "Check for any half-made edits in the files you were writing when interrupted, "
        "fix or report them, and proceed with the remaining tasks."
    )
    log_event(f"Resuming session {target} (pid {pid}) via {send_cmd} - reason: {reason}")
    try:
        proc = subprocess.run([send_cmd, target, msg], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
        out = proc.stdout.strip()
        log_event(f"Resume command result for {target}: {out}")
        return proc.returncode == 0
    except Exception as e:
        log_event(f"Failed to resume {target}: {e}")
        return False


def cmd_check() -> int:
    """One-shot check: inspects sessions and resumes any whose reset timestamp has passed."""
    records = get_session_records()
    state = load_state()
    now = time.time()
    any_waiting = False

    for r in records:
        t_key = f"{r['target']}:{r['pid']}"
        s_data = state.get(t_key, {})

        if r["rate_limited"]:
            resets_at = r["resets_at"]
            if resets_at and now < resets_at:
                # Active rate limit waiting
                any_waiting = True
                if s_data.get("waiting_for_reset") != resets_at:
                    state[t_key] = {
                        "waiting_for_reset": resets_at,
                        "target": r["target"],
                        "pid": r["pid"],
                    }
                    save_state(state)
                    rem = int(resets_at - now)
                    log_event(f"Session {r['target']} (pid {r['pid']}) entered rate-limit. Resets in {format_countdown(rem)}")
            elif resets_at and now >= (resets_at + 15):
                # Eligible for resume ONLY if previously tracked waiting for this exact reset window
                if s_data.get("waiting_for_reset") == resets_at and s_data.get("resumed_for_reset") != resets_at:
                    success = resume_session(r["target"], r["pid"], reason=f"quota reset at {datetime.datetime.fromtimestamp(resets_at)}")
                    if success:
                        state[t_key] = {
                            "resumed_for_reset": resets_at,
                            "resumed_at": int(now),
                            "target": r["target"],
                            "pid": r["pid"],
                        }
                        save_state(state)
            else:
                any_waiting = True
        else:
            # Session is healthy / not rate limited; clear waiting state if any
            if t_key in state:
                state.pop(t_key, None)
                save_state(state)

    return 2 if any_waiting else 0


def cmd_watch(poll_interval: int = 30):
    log_event(f"Starting codex-auto-resume watcher (poll interval {poll_interval}s)...")
    try:
        while True:
            cmd_check()
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        log_event("Watcher stopped by user.")
        return 0


def cmd_install_systemd():
    unit_dir = Path.home() / ".config" / "systemd" / "user"
    unit_dir.mkdir(parents=True, exist_ok=True)

    script_path = Path(__file__).resolve()
    service_file = unit_dir / "codex-auto-resume.service"
    timer_file = unit_dir / "codex-auto-resume.timer"

    service_content = f"""[Unit]
Description=Codex Usage-Limit Auto-Resume Watcher
After=network.target

[Service]
Type=oneshot
ExecStart={sys.executable} {script_path} --check
StandardOutput=journal
StandardError=journal
"""

    timer_content = """[Unit]
Description=Run Codex Usage-Limit Auto-Resume Watcher every 30s

[Timer]
OnBootSec=30s
OnUnitActiveSec=30s
AccuracySec=5s

[Install]
WantedBy=timers.target
"""

    service_file.write_text(service_content, encoding="utf-8")
    timer_file.write_text(timer_content, encoding="utf-8")
    print(f"Written: {service_file}")
    print(f"Written: {timer_file}")

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", "codex-auto-resume.timer"], check=True)
    print("Enabled and started codex-auto-resume.timer.")
    subprocess.run(["systemctl", "--user", "status", "codex-auto-resume.timer", "--no-pager"])
    return 0


def cmd_uninstall_systemd():
    timer_file = Path.home() / ".config" / "systemd" / "user" / "codex-auto-resume.timer"
    service_file = Path.home() / ".config" / "systemd" / "user" / "codex-auto-resume.service"

    try:
        subprocess.run(["systemctl", "--user", "disable", "--now", "codex-auto-resume.timer"], check=False)
    except Exception:
        pass

    if timer_file.exists():
        timer_file.unlink()
        print(f"Removed {timer_file}")
    if service_file.exists():
        service_file.unlink()
        print(f"Removed {service_file}")

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    print("Uninstalled codex-auto-resume systemd user timer.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Autonomous Codex quota auto-resume tool.")
    parser.add_argument("--status", action="store_true", help="Show status of all running Codex sessions")
    parser.add_argument("--check", action="store_true", help="One-shot check and auto-resume eligible sessions")
    parser.add_argument("--watch", action="store_true", help="Watch continuously in foreground")
    parser.add_argument("--interval", type=int, default=30, help="Poll interval in seconds for --watch (default: 30)")
    parser.add_argument("--resume", metavar="TARGET", help="Force immediate resume message to target")
    parser.add_argument("--install", action="store_true", help="Install and enable systemd user service and timer")
    parser.add_argument("--uninstall", action="store_true", help="Uninstall systemd user service and timer")

    args = parser.parse_args()

    if args.install:
        return cmd_install_systemd()
    if args.uninstall:
        return cmd_uninstall_systemd()
    if args.resume:
        return 0 if resume_session(args.resume, 0, reason="manual request") else 1
    if args.watch:
        return cmd_watch(args.interval)
    if args.check:
        return cmd_check()

    # Default to status
    return cmd_status()


if __name__ == "__main__":
    sys.exit(main() or 0)
