#!/usr/bin/env python3
import sys
import json
import time
import os
import re
import subprocess
import signal

COLOR_FILE = os.path.expanduser("~/.gemini/antigravity-cli/session_color")

COLOR_MAP = {
    "yellow": "\033[1;30;43m",         # Claude Code yellow
    "cyan": "\033[1;30;46m",           # Bright cyan
    "blue": "\033[1;97;44m",           # Blue
    "magenta": "\033[1;97;45m",        # Magenta
    "purple": "\033[1;97;45m",         # Purple
    "green": "\033[1;30;42m",          # Green
    "red": "\033[1;97;41m",            # Red
    "orange": "\033[1;30;48;5;208m",   # Orange
    "gray": "\033[1;97;100m",          # Gray
    "white": "\033[1;30;47m",          # White
}
RESET = "\033[0m"

SPINNERS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

def get_color_code():
    try:
        if os.path.exists(COLOR_FILE):
            with open(COLOR_FILE, "r") as f:
                c = f.read().strip().lower()
                if c in COLOR_MAP:
                    return COLOR_MAP[c]
    except Exception:
        pass
    return COLOR_MAP["yellow"]

def strip_ansi(s):
    return re.sub(r"\033\[[0-9;]*m", "", s)

def get_controlling_tty():
    try:
        ppid = os.getppid()
        tty = subprocess.check_output(
            ["ps", "-p", str(ppid), "-o", "tty="],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        if tty and tty != "?" and not tty.startswith("??"):
            dev = f"/dev/{tty}"
            if os.path.exists(dev):
                return dev
    except Exception:
        pass
    for fd in (2, 1, 0):
        try:
            name = os.ttyname(fd)
            if name and os.path.exists(name):
                return name
        except Exception:
            pass
    return None

def stop_animator(tty_dev):
    if not tty_dev:
        return
    safe_name = os.path.basename(tty_dev)
    pid_file = f"/tmp/agy_anim_{safe_name}.pid"
    title_file = f"/tmp/agy_anim_{safe_name}.title"
    if os.path.exists(pid_file):
        try:
            with open(pid_file, "r") as f:
                pid = int(f.read().strip())
            os.kill(pid, signal.SIGTERM)
        except Exception:
            pass
        try:
            os.remove(pid_file)
        except Exception:
            pass
    try:
        if os.path.exists(title_file):
            os.remove(title_file)
    except Exception:
        pass

def start_animator(tty_dev, title):
    if not tty_dev:
        return
    safe_name = os.path.basename(tty_dev)
    pid_file = f"/tmp/agy_anim_{safe_name}.pid"
    title_file = f"/tmp/agy_anim_{safe_name}.title"

    # Check if already running with same title
    if os.path.exists(pid_file) and os.path.exists(title_file):
        try:
            with open(pid_file, "r") as f:
                old_pid = int(f.read().strip())
            with open(title_file, "r") as f:
                old_title = f.read().strip()
            if old_title == title:
                os.kill(old_pid, 0)
                return  # Still running properly
        except Exception:
            pass
        stop_animator(tty_dev)

    # Spawn daemon animator
    try:
        with open(title_file, "w") as f:
            f.write(title)
        cmd = [sys.executable, os.path.abspath(__file__), "__daemon__", tty_dev, title, pid_file]
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass

def daemon_loop(tty_dev, title, pid_file):
    try:
        with open(pid_file, "w") as f:
            f.write(str(os.getpid()))
    except Exception:
        return

    i = 0
    start_time = time.time()
    try:
        with open(tty_dev, "w") as tty:
            # Animate up to 30 mins (safety timeout)
            while time.time() - start_time < 1800:
                frame = SPINNERS[i % len(SPINNERS)]
                # Put frame at both ends so it is visible even if left-truncated by Terminal tab
                disp = f"{frame} {title} {frame}" if title else f"{frame} agy {frame}"
                tty.write(f"\033]0;{disp}\007\033]1;{disp}\007\033]2;{disp}\007")
                tty.flush()
                time.sleep(0.12)
                i += 1
    except Exception:
        pass
    finally:
        try:
            if os.path.exists(pid_file):
                os.remove(pid_file)
        except Exception:
            pass

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "__daemon__":
        tty_dev = sys.argv[2]
        title = sys.argv[3] if len(sys.argv) > 3 else ""
        pid_file = sys.argv[4] if len(sys.argv) > 4 else f"/tmp/agy_anim_{os.path.basename(tty_dev)}.pid"
        daemon_loop(tty_dev, title, pid_file)
        return

    mode = sys.argv[1] if len(sys.argv) > 1 else "statusline"
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        data = json.loads(raw)
    except Exception:
        return

    title = data.get("conversation_title", "").strip()
    state = data.get("agent_state", "idle")
    is_working = state in ("working", "running", "thinking")
    frame = SPINNERS[int(time.time() * 4) % len(SPINNERS)]

    # --- Mode: title (Terminal Tab / Window title) ---
    if mode == "title":
        tty_dev = get_controlling_tty()
        if is_working:
            start_animator(tty_dev, title)
            text = f"{frame} {title} {frame}" if title else f"{frame} agy {frame}"
            print(text)
        else:
            stop_animator(tty_dev)
            text = f"⏹️  {title}" if title else "⏹️  agy"
            print(text)
            if tty_dev:
                try:
                    with open(tty_dev, "w") as tty:
                        tty.write(f"\033]0;{text}\007\033]1;{text}\007\033]2;{text}\007")
                        tty.flush()
                except Exception:
                    pass
        return

    # --- Mode: statusline (Single line with right-aligned badges matching Claude Code) ---
    term_width = data.get("terminal_width") or 80
    
    # Left side: shortcuts hint
    left_str = "\033[90m? for shortcuts\033[0m"

    # Right side elements: model info + [status_pill] [title_pill]
    model_info = data.get("model", {})
    model_name = ""
    effort = ""
    if isinstance(model_info, dict):
        model_name = model_info.get("display_name") or model_info.get("id") or ""
        effort = model_info.get("effort") or ""
    elif isinstance(model_info, str):
        model_name = model_info

    cycle_mode = data.get("cycle_mode") or "auto"
    model_items = [f"\033[33m{cycle_mode}\033[0m"]
    if model_name:
        model_items.append(f"\033[90m·\033[0m {model_name}")
    if effort:
        model_items.append(f"\033[90m·\033[0m {effort}")

    right_sections = [" ".join(model_items)]

    # Status pill (WORKING / STOPPED)
    if is_working:
        status_pill = f"\033[1;30;43m {frame} WORKING {RESET}"
        right_sections.append(status_pill)
    elif title:
        status_pill = f"\033[1;30;42m ⏹️ STOPPED {RESET}"
        right_sections.append(status_pill)

    # Session title badge (Claude Code style pill at far right)
    if title:
        badge_color = get_color_code()
        title_pill = f"{badge_color} {title} {RESET}"
        right_sections.append(title_pill)

    right_str = "   ".join([s for s in right_sections if s])

    # Pad between left and right to make a clean single row
    left_len = len(strip_ansi(left_str))
    right_len = len(strip_ansi(right_str))
    spaces_count = max(2, term_width - left_len - right_len)
    
    print(f"{left_str}{' ' * spaces_count}{right_str}")

if __name__ == "__main__":
    main()
