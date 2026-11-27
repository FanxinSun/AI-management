#!/usr/bin/python3 -I
"""Run one job and log it (template: general/templates/chunked-pipeline/).

This is e7's job logger, tools/run_logged.py of the user's project e7-upsilon-omega (sha256
b75a503480805fee83b37b87dd0592aa945715e1ed54c9026d65aca6b2410ddb, pinned in e7's tools/s6_all_in_one.pins on 2026-11-27);
only this docstring differs, the code is e7's. tools/pipe.py runs every job through it: the job's start, end, exit status,
command, wall and cpu time and peak memory go to one line of runs/log.jsonl, and the split's compute is summed from there.
Limits above 1800 s, up to 14400 s, need --long-ok with the user's approval, which the log line records.

usage: /usr/bin/python3 -I tools/run_logged.py --step S --id ID --limit SECONDS [--mem MB] [--bulky]
           [--by NAME] [--long-ok APPROVAL] [--env NAME=VALUE]... -- COMMAND...

The command runs from the repository root as a child in its own process group, with a clean environment
(PATH=/usr/bin:/bin:/usr/sbin:/sbin and HOME, plus the --env additions), standard input from /dev/null,
standard output to runs/S/ID.out and standard error to runs/S/ID.err (with --bulky: build/out/S/).
The whole group is killed at the time limit, or when its resident memory passes the cap (checked ten times a
second). One JSON line is appended to runs/log.jsonl. An id that already has a log line, or whose output files
exist in either output root, is refused. Exit status: 0 if the job ended with exit 0, 1 for any other outcome,
2 if refused. Standard library only.

Limits: a descendant that calls setsid() leaves the group, so it is neither killed nor counted; memory is
sampled, so a spike between two samples can pass the cap; cpu_s is the rusage of the direct child and of the
descendants it waited for. A failed or slow memory sample is counted in rss_samples_failed and never stops the time limit.
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "runs", "log.jsonl")
CLEAN_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
MAX_LIMIT = 1800
LONG_MAX = 14400
POLL = 0.1


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def group_rss_kb(pgid):
    """Sum of resident memory (KB) of the processes in process group pgid, from ps; None if ps failed."""
    try:
        res = subprocess.run(["/bin/ps", "-A", "-o", "pgid=,rss="], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, env={"PATH": CLEAN_PATH}, check=False, timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if res.returncode != 0 or not res.stdout:
        return None
    total = 0
    for line in res.stdout.decode("ascii", "replace").split("\n"):
        parts = line.split()
        if len(parts) == 2 and parts[0] == str(pgid):
            try:
                total += int(parts[1])
            except ValueError:
                return None
    return total


def logged_ids():
    ids = set()
    if os.path.exists(LOG):
        with open(LOG, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rec = json.loads(line)
                    ids.add((rec["step"], rec["id"]))
    return ids


def kill_group(pgid):
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def main():
    p = argparse.ArgumentParser(add_help=True)
    p.add_argument("--step", required=True)
    p.add_argument("--id", required=True)
    p.add_argument("--limit", required=True, type=float)
    p.add_argument("--mem", type=int, default=2048, help="memory cap in MB (default 2048)")
    p.add_argument("--bulky", action="store_true")
    p.add_argument("--by", default="unnamed", help="who ran the job")
    p.add_argument("--long-ok", default=None, metavar="APPROVAL",
                   help="the user's approval, in the user's words, for a limit above %d s" % MAX_LIMIT)
    p.add_argument("--env", action="append", default=[], metavar="NAME=VALUE")
    p.add_argument("command", nargs=argparse.REMAINDER)
    a = p.parse_args()
    cmd = a.command[1:] if a.command[:1] == ["--"] else a.command
    if not cmd:
        p.error("no command after --")
    for name, value in (("step", a.step), ("id", a.id)):
        if not value or "/" in value or value.startswith("."):
            p.error("bad %s: %r" % (name, value))
    if not a.limit > 0:
        p.error("--limit must be above 0")
    if a.limit > MAX_LIMIT and (not (a.long_ok or "").strip() or a.limit > LONG_MAX):
        p.error("--limit above %d needs --long-ok with the user's approval, and at most %d" % (MAX_LIMIT, LONG_MAX))
    added = {}
    for item in a.env:
        if "=" not in item:
            p.error("bad --env %r" % item)
        k, v = item.split("=", 1)
        added[k] = v
    env = {"PATH": CLEAN_PATH, "HOME": os.environ.get("HOME", "/var/empty")}
    env.update(added)

    roots = [os.path.join(ROOT, "runs", a.step), os.path.join(ROOT, "build", "out", a.step)]
    outdir = roots[1] if a.bulky else roots[0]
    os.makedirs(outdir, exist_ok=True)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    out_path = os.path.join(outdir, a.id + ".out")
    err_path = os.path.join(outdir, a.id + ".err")

    # Reserve the id: under the log's lock, refuse a logged id or an id with output files in either root, then
    # create both output files exclusively. Every reservation happens under this lock, so two jobs cannot both
    # pass with the same id.
    with open(LOG, "a", encoding="utf-8") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        if (a.step, a.id) in logged_ids():
            print("refused: %s/%s already has a log line" % (a.step, a.id), file=sys.stderr)
            return 2
        for r in roots:
            for ext in (".out", ".err"):
                if os.path.exists(os.path.join(r, a.id + ext)):
                    print("refused: %s exists" % os.path.join(r, a.id + ext), file=sys.stderr)
                    return 2
        try:
            out_f = open(out_path, "xb")
        except FileExistsError:
            print("refused: %s exists" % out_path, file=sys.stderr)
            return 2
        try:
            err_f = open(err_path, "xb")
        except FileExistsError:
            out_f.close()
            print("refused: %s exists (the empty %s was left in place)" % (err_path, out_path), file=sys.stderr)
            return 2
        fcntl.flock(lf, fcntl.LOCK_UN)

    start = utc()
    t0 = time.monotonic()
    outcome = None
    peak_kb = 0
    samples = 0
    samples_failed = 0
    stop_reason = []

    def on_signal(signum, frame):
        stop_reason.append("interrupted")

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    # A job whose parent shell was terminated once ended without a log line (SIGHUP is the likely cause; not verified),
    # and the job's own group kept running.
    signal.signal(signal.SIGHUP, on_signal)

    try:
        child = subprocess.Popen(cmd, cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=out_f,
                                 stderr=err_f, start_new_session=True)
    except OSError as e:
        err_f.write(("run_logged: could not start: %s\n" % e).encode())
        outcome = "not started"
        child = None
    status = None
    rusage = None
    if child is not None:
        pgid = child.pid
        while True:
            pid, st, ru = os.wait4(child.pid, os.WNOHANG)
            if pid == child.pid:
                status, rusage = st, ru
                break
            kb = None
            if stop_reason:
                outcome = stop_reason[0]
            elif time.monotonic() - t0 > a.limit:
                outcome = "timeout"
            else:
                kb = group_rss_kb(pgid)
                samples += 1
                if kb is None:
                    samples_failed += 1
                else:
                    peak_kb = max(peak_kb, kb)
                    if kb > a.mem * 1024:
                        outcome = "memory"
            if outcome is not None:
                kill_group(pgid)
                pid, st, ru = os.wait4(child.pid, 0)
                status, rusage = st, ru
                break
            time.sleep(POLL)
        child.returncode = 0  # reaped above; keep Popen from waiting again
        kill_group(pgid)  # anything the job left running in its group
        if outcome is None:
            if os.WIFEXITED(status):
                outcome = "exit %d" % os.WEXITSTATUS(status)
            elif os.WIFSIGNALED(status):
                sig = os.WTERMSIG(status)
                try:
                    outcome = "signal " + signal.Signals(sig).name
                except ValueError:
                    outcome = "signal %d" % sig
            else:
                outcome = "status %d" % status
    wall = time.monotonic() - t0
    end = utc()
    out_f.close()
    err_f.close()

    rec = {
        "step": a.step, "id": a.id, "by": a.by, "cmd": cmd, "env_added": added, "cwd": ROOT,
        "limit_s": a.limit, "mem_mb": a.mem, "start_utc": start, "end_utc": end, "wall_s": round(wall, 3),
        "cpu_s": round(rusage.ru_utime + rusage.ru_stime, 3) if rusage else None,
        "peak_rss_mb": round(peak_kb / 1024.0, 1), "rss_samples": samples, "rss_samples_failed": samples_failed,
        "outcome": outcome,
        "stdout": {"path": os.path.relpath(out_path, ROOT), "bytes": os.path.getsize(out_path),
                   "sha256": sha256(out_path)},
        "stderr": {"path": os.path.relpath(err_path, ROOT), "bytes": os.path.getsize(err_path),
                   "sha256": sha256(err_path)},
        "logger_sha256": sha256(os.path.abspath(__file__)),
    }
    if a.long_ok is not None:
        rec["long_ok"] = a.long_ok
    with open(LOG, "a", encoding="utf-8") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        lf.write(json.dumps(rec, sort_keys=False) + "\n")
        lf.flush()
        os.fsync(lf.fileno())
        fcntl.flock(lf, fcntl.LOCK_UN)
    print("%s/%s: %s, %.2f s wall, peak %.1f MB" % (a.step, a.id, outcome, wall, peak_kb / 1024.0))
    return 0 if outcome == "exit 0" else 1


if __name__ == "__main__":
    sys.exit(main())
