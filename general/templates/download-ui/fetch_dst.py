"""Piece B: an all-in-one, resumable, parallel downloader of the DELPHI short DSTs (plan/subplan_3/pieceB-downloader.md).

usage: python -I tools/s3b_fetch_dst.py list OUT_TSV
       python -I tools/s3b_fetch_dst.py fetch LIST_TSV OUTDIR [--workers N] [--dashboard] [--report-seconds auto|S]
                  [--file-lines N|all] [--max-stalls N] [--max-seconds S] [--max-files N] [--only RECID]
                  [--retry-wait S] [--pause S] [--eos] [--cafile PATH] [--cafile-sha256 FP] [--dry-run]
       python -I tools/s3b_fetch_dst.py probe URL [URL ...] [--cafile PATH] [--seconds N]
       python -I tools/s3b_fetch_dst.py status LIST_TSV OUTDIR
Standard library only. Exit codes of fetch: 0 done or budget reached, 1 failure or block, 2 refused OUTDIR,
3 disk or another download running, 130 interrupted.

fetch with --workers N runs N download threads, each taking the next unfinished file of the list. With --dashboard
the terminal shows a progress dashboard redrawn in place every --report-seconds (auto: 5 s on a terminal, 30 s when
piped) and the detail goes to OUTDIR/download.log; without it, one line per file goes to standard output as before.
Every file is checked by size and adler32; a file that fails is renamed *.bad, never deleted. A stalled connection
(under --stall-limit bytes/s for --stall-seconds) is dropped and resumed from the bytes already on disk (Range).
A file is given up on only after --max-stalls CONSECUTIVE attempts that added no bytes; a 4xx answer stops the run.
--retry-wait (default 60), --pause (default 5 with one worker, else 0) and the stall options exist so the local tests
need not wait. Downloaded files are untrusted data: written and hashed, never opened or parsed.
"""
import argparse
import collections
import datetime
import hashlib
import http.client
import json
import os
import re
import shutil
import signal
import ssl
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import zlib

RECORDS = [(81013, "short91_f1", 45, 4175093760), (81166, "short93_d2", 181, 17631713280),
           (81502, "short95_d2", 246, 21187031040)]
API = "https://opendata.cern.ch/api/records/%d"
URL = "https://opendata.cern.ch/record/%d/files/%s"
CHUNK = 1 << 20
READ_TIMEOUT = 300   # seconds a read may block (--read-timeout)
LOGNAME = "fetch-log.tsv"
LOGHEAD = "recid\tkey\tbytes\tadler32\tsha256\tstart_utc\tend_utc\tattempts\tresumed\n"
GIB2 = 2 * (1 << 30)
EOS = "https://eospublic.cern.ch//eos/opendata/delphi/collision-data/%s/%s"
PROGRESS = 60.0   # seconds between progress lines in the log (--progress-seconds)
RECNAME = {r[0]: r[1] for r in RECORDS}
LOCKNAME = ".download.lock"
RUNLOG = "download.log"
SUMS = "SHA256SUMS"
RETRY_AFTER_PROGRESS = 2.0   # seconds to wait before resuming after an attempt that added bytes
CTX = None   # set by --cafile: an ssl.create_default_context(cafile=...), verification and hostname check on


def eos_url(key):
    return EOS % (key.split(".", 1)[0], key)


def utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Block(Exception):
    """A 4xx answer or a protocol surprise: stop the whole run with exit 1."""


# ---------------------------------------------------------------- list
def part_rows(path, n_tab, b_tab):
    """Rows of a record's .part file if its row count and byte sum match the table, else None."""
    if not os.path.exists(path):
        return None
    with open(path) as f:
        rows = [ln.split("\t") for ln in f.read().split("\n")[1:] if ln]
    if len(rows) == n_tab and sum(int(r[2]) for r in rows) == b_tab:
        return rows
    return None


def cmd_list(out):
    head = "recid\tkey\tsize\tadler32\turl\n"
    allrows, total_n, total_b, parts = [], 0, 0, []
    for recid, name, n_tab, b_tab in RECORDS:
        ppath = "%s.%d.part" % (out, recid)
        parts.append(ppath)
        rows = part_rows(ppath, n_tab, b_tab)
        if rows is not None:
            print("record %d %s: %d files, %d bytes (from %s)" % (recid, name, len(rows), b_tab, ppath), flush=True)
        else:
            meta = None
            for attempt in range(1, 6):
                try:
                    with urllib.request.urlopen(API % recid, timeout=300) as r:
                        meta = json.loads(r.read().decode("utf-8"))
                    break
                except (ValueError, urllib.error.URLError, OSError, http.client.HTTPException) as e:
                    print("record %d attempt %d: %r" % (recid, attempt, e), flush=True)
                    if attempt < 5:
                        time.sleep(30)
            if meta is None:
                print("record %d: no parsable answer after 5 attempts" % recid)
                return 1
            md = meta["metadata"]
            files = md["_files"]
            n, b = len(files), sum(int(x["size"]) for x in files)
            dist = md["distribution"]
            if (n, b) != (int(dist["number_files"]), int(dist["size"])) or (n, b) != (n_tab, b_tab):
                print("record %d: files %d bytes %d; distribution %s files %s bytes; table %d files %d bytes"
                      % (recid, n, b, dist["number_files"], dist["size"], n_tab, b_tab))
                return 1
            rows = []
            for x in files:
                key = x["key"]
                if "/" in key or "\t" in key:
                    print("record %d: unsupported key %r" % (recid, key))
                    return 1
                ad = x["checksum"].split(":", 1)[1]
                rows.append([str(recid), key, str(int(x["size"])), ad, URL % (recid, key)])
            with open(ppath, "w") as f:
                f.write(head + "".join("\t".join(r) + "\n" for r in rows))
            print("record %d %s: %d files, %d bytes" % (recid, name, n, b), flush=True)
        allrows += rows
        total_n += len(rows)
        total_b += b_tab
    with open(out, "w") as f:
        f.write(head + "".join("\t".join(r) + "\n" for r in allrows))
    for ppath in parts:
        os.remove(ppath)
    print("total: %d files, %d bytes" % (total_n, total_b))
    return 0


def read_list(path):
    with open(path) as f:
        lines = f.read().split("\n")
    out = []
    for ln in lines[1:]:
        if ln:
            r, k, s, a, u = ln.split("\t")
            out.append((int(r), k, int(s), a, u))
    return out


# ---------------------------------------------------------------- helpers
def read_log(outdir):
    """The fetch log: ({(recid, key): (bytes, adler32)}, {(recid, key): sha256})."""
    p = os.path.join(outdir, LOGNAME)
    done, shas = {}, {}
    if os.path.exists(p):
        with open(p) as f:
            for ln in f.read().split("\n")[1:]:
                if ln:
                    c = ln.split("\t")
                    done[(int(c[0]), c[1])] = (int(c[2]), c[3])
                    shas[(int(c[0]), c[1])] = c[4]
    return done, shas


def append_log(outdir, row):
    p = os.path.join(outdir, LOGNAME)
    new = not os.path.exists(p)
    with open(p, "a") as f:
        if new:
            f.write(LOGHEAD)
        f.write("\t".join(map(str, row)) + "\n")
        f.flush()
        os.fsync(f.fileno())


def hash_file(path, ad=1, sha=None):
    sha = sha or hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            ad = zlib.adler32(b, ad)
            sha.update(b)
    return ad, sha


def hexad(ad):
    return "%08x" % (ad & 0xffffffff)


def move_bad(src, target):
    """Rename src to <target>.bad (or .bad2, .bad3 ... if taken); never delete."""
    dst, i = target + ".bad", 1
    while os.path.exists(dst):
        i += 1
        dst = target + ".bad%d" % i
    os.rename(src, dst)
    return dst


def check_outdir(outdir, rows):
    """Refuse (return a message) if OUTDIR holds anything other than this script's own entries."""
    if not os.path.isdir(outdir):
        return None
    keys = {}
    for r, k, _, _, _ in rows:
        keys.setdefault(str(r), set()).add(k)
    for e in os.listdir(outdir):
        if e in (LOGNAME, RUNLOG, LOCKNAME):
            continue
        if e in keys and os.path.isdir(os.path.join(outdir, e)):
            for g in os.listdir(os.path.join(outdir, e)):
                if g in (SUMS, SUMS + ".tmp"):
                    continue
                base = re.sub(r"(\.part|\.bad\d*)$", "", g)
                if base not in keys[e]:
                    return "unknown file %s/%s" % (e, g)
            continue
        return "unknown entry %s" % e
    return None


# ---------------------------------------------------------------- fetch
class Stopped(Exception):
    """The run was asked to stop (Ctrl-C, a block, no disk space): leave the .part file and return."""


def psize(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def human(n):
    for unit, size in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
        if n >= size:
            return "%.2f %s" % (n / size, unit)
    return "%d B" % int(n)


def clock(seconds):
    seconds = int(seconds)
    return "%02d:%02d:%02d" % (seconds // 3600, seconds % 3600 // 60, seconds % 60)


def bar(fraction, width):
    fraction = max(0.0, min(1.0, fraction))
    filled = int(fraction * width + 0.5)
    return "█" * filled + "░" * (width - filled)


def rate_text(value):
    if value is None:
        return "measuring"
    if value >= 1 << 20:
        return "%.2f MB/s" % (value / (1 << 20))
    return "%.0f KB/s" % (value / 1024.0)


def ca_fingerprint(cafile):
    """SHA-256 fingerprint (AA:BB:...) of the single certificate in a PEM file."""
    with open(cafile) as f:
        text = f.read()
    if text.count("-----BEGIN CERTIFICATE-----") != 1:
        raise ValueError("%s must contain exactly one certificate" % cafile)
    first = text[text.index("-----BEGIN CERTIFICATE-----"):text.index("-----END CERTIFICATE-----") + 25]
    h = hashlib.sha256(ssl.PEM_cert_to_DER_cert(first)).hexdigest().upper()
    return ":".join(h[i:i + 2] for i in range(0, len(h), 2))


def other_fetchers(outdir):
    """PIDs of other `s3b_fetch_dst.py fetch ... OUTDIR` processes, best effort from ps. Only a process whose own
    script is s3b_fetch_dst.py and whose command is fetch counts, and never this process, an ancestor of it (a job
    logger, a `zsh -c "..."` shell) or a descendant of it: `caffeinate -i <utility>` execs the utility in its own PID
    and forks a helper child that keeps the whole command line."""
    try:
        ps = subprocess.run(["/bin/ps", "-axo", "pid=,ppid=,command="], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            timeout=10, check=False).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError):
        return []
    procs, children = {}, {}
    for line in ps.split("\n"):
        parts = line.split(None, 2)
        if len(parts) < 3 or not parts[0].isdigit() or not parts[1].isdigit():
            continue
        pid, ppid = int(parts[0]), int(parts[1])
        procs[pid] = (ppid, parts[2])
        children.setdefault(ppid, []).append(pid)
    own = {os.getpid()}
    up = os.getpid()
    while up in procs and procs[up][0] > 0 and procs[up][0] not in own:      # every ancestor, by ppid
        up = procs[up][0]
        own.add(up)
    todo = [os.getpid()]
    while todo:                                                               # every descendant, by the children map
        for child in children.get(todo.pop(), []):
            if child not in own:
                own.add(child)
                todo.append(child)
    mine = os.path.realpath(outdir)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    found = []
    for pid, (ppid, command) in procs.items():
        if pid in own:
            continue
        toks = command.split()
        script = next((k for k, t in enumerate(toks) if t.endswith(".py")), None)
        if script is None or os.path.basename(toks[script]) != "s3b_fetch_dst.py":
            continue
        if script + 1 >= len(toks) or toks[script + 1] != "fetch":
            continue
        if any(os.path.realpath(os.path.join(base, t)) == mine for t in toks[script + 2:] for base in (os.getcwd(), root)):
            found.append(pid)
    return found


def acquire_lock(outdir):
    """Create OUTDIR/.download.lock (a directory holding our pid). Returns (path, None), or (None, pid of the owner)."""
    lock = os.path.join(outdir, LOCKNAME)
    for _ in range(2):
        try:
            os.mkdir(lock)
        except FileExistsError:
            try:
                with open(os.path.join(lock, "pid")) as f:
                    pid = int(f.read().strip())
                os.kill(pid, 0)
                return None, pid
            except ProcessLookupError:
                pass
            except (OSError, ValueError):
                pid = None
            shutil.rmtree(lock, ignore_errors=True)       # a stale lock of a process that is gone
            continue
        with open(os.path.join(lock, "pid"), "w") as f:
            f.write("%d\n" % os.getpid())
        return lock, None
    return None, -1


def release_lock(lock):
    if lock:
        shutil.rmtree(lock, ignore_errors=True)


class Runner:
    """One fetch run: N download threads, a shared claim queue, and (with --dashboard) a progress display."""

    def __init__(self, a, rows):
        self.a, self.rows, self.n, self.outdir = a, rows, len(rows), a.outdir
        self.nthreads = max(1, min(a.workers, self.n))
        self.lock = threading.RLock()          # claims, counters, fetch-log rows, SHA256SUMS
        self.outlock = threading.Lock()        # run log and standard output lines
        self.stop = threading.Event()          # abort what is in flight (Ctrl-C, a block, no disk, network down)
        self.drain = threading.Event()         # take no new file but let those in flight finish (budgets)
        self.all_done = threading.Event()
        self.stop_reason, self.stop_code = None, 0
        self.have = [0] * self.n               # bytes of each row on disk (done file, or .part, or in flight)
        self.done = [False] * self.n
        self.cur = {}                          # row index -> dict for the rows a thread holds right now
        self.next = 0
        self.claimed_new = 0
        self.alive = self.nthreads
        self.retries = self.errors = self.give_ups = self.newly = 0
        self.fail_streak = 0                   # files given up on in a row with no byte received by anyone between
        self.last_error = ""
        self.logf = None
        self.t0 = time.monotonic()
        self.wall0 = time.time()
        self.baseline = 0
        self.hist = collections.deque()        # (time, total bytes, {row: bytes}) snapshots for the rates
        self.prev_lines = 0
        self.done_log, self.shas = {}, {}
        self.tty = sys.stdout.isatty()
        self.report = a.report if a.report else (5.0 if self.tty else 30.0)
        self.pause = a.pause if a.pause is not None else (5.0 if a.workers == 1 else 0.0)

    # ---- output
    def emit(self, tag, text, show=True):
        """A line for the run log (always) and, unless the dashboard owns the terminal, for standard output."""
        with self.outlock:
            self.logf.write("%s %s %s\n" % (utc(), tag or "[main]", text))
            self.logf.flush()
            if show and not self.a.dashboard:
                print(text, flush=True)

    def say(self, text):
        """A line for the terminal and the log (start and end of a dashboard run)."""
        with self.outlock:
            self.logf.write("%s [main] %s\n" % (utc(), text))
            self.logf.flush()
            print(text, flush=True)

    def target(self, i):
        r = self.rows[i]
        return os.path.join(self.outdir, str(r[0]), r[1])

    def request_stop(self, reason, code):
        with self.lock:
            if self.stop_reason is None or code > self.stop_code:
                self.stop_reason, self.stop_code = reason, code
        (self.stop if code else self.drain).set()

    # ---- the claim queue
    def claim(self):
        with self.lock:
            while self.next < self.n and not self.stop.is_set() and not self.drain.is_set():
                if self.a.max_seconds is not None and time.monotonic() - self.t0 >= self.a.max_seconds:
                    self.request_stop("time budget reached", 0)
                    return None
                i = self.next
                self.next += 1
                if self.done[i]:
                    self.emit("", "%d %s %d 0 0 skipped" % (self.rows[i][0], self.rows[i][1], self.rows[i][2]))
                    continue
                if self.a.max_files is not None and self.claimed_new >= self.a.max_files:
                    self.request_stop("max-files reached", 0)
                    return None
                self.claimed_new += 1
                return i
            return None

    def worker(self, wid):
        tag = "[w%d]" % wid
        try:
            first = True
            while not self.stop.is_set():
                i = self.claim()
                if i is None:
                    break
                if not first and self.pause > 0 and self.stop.wait(self.pause):
                    break
                first = False
                self.process(i, tag)
        except Exception as e:          # a bug in one thread must not leave the run hanging
            self.errors += 1
            self.last_error = "internal error: %r" % (e,)
            self.emit(tag, "INTERNAL ERROR: " + traceback.format_exc().replace("\n", " | "))
            self.request_stop("internal error", 1)
        finally:
            with self.lock:
                self.alive -= 1
                if self.alive == 0:
                    self.all_done.set()

    # ---- one file
    def process(self, i, tag):
        recid, key, size, want, url = self.rows[i]
        target = self.target(i)
        cur = {"got": self.have[i], "size": size, "live": False, "note": ""}
        self.cur[i] = cur
        try:
            if os.path.exists(target):       # present, but not in the fetch log: verify it
                ad, sha = hash_file(target)
                if os.path.getsize(target) == size and hexad(ad) == want:
                    self.emit(tag, "%d %s %d 0 0 skipped" % (recid, key, size))
                    now = utc()
                    self.finish_row(i, sha.hexdigest(), now, now, 0, "no", new=False)
                    return
                move_bad(target, target)
                self.have[i] = cur["got"] = psize(target + ".part")
            if not self.check_disk(i, tag):
                return
            self.attempts(i, tag, cur)
        finally:
            self.cur.pop(i, None)

    def check_disk(self, i, tag):
        size = self.rows[i][2]
        with self.lock:
            free = shutil.disk_usage(self.outdir).free
            coming = sum(max(0, c["size"] - c["got"]) for j, c in list(self.cur.items()) if j != i)
        if free - coming < size + GIB2:
            msg = ("free space %d bytes (less %d bytes still to arrive for files in flight) is below file size %d "
                   "plus 2 GiB" % (free, coming, size))
            self.last_error = msg
            self.emit(tag, msg)
            self.request_stop("disk space", 3)
            return False
        return True

    def attempts(self, i, tag, cur):
        a = self.a
        recid, key, size, want, url = self.rows[i]
        part = self.target(i) + ".part"
        st = {"resumed": "no"}
        start = utc()
        attempt = fails = 0
        while not self.stop.is_set():
            attempt += 1
            before = psize(part)
            try:
                outcome = self.download_once(i, tag, cur, st)
            except Stopped:
                return
            except Block as e:
                self.errors += 1
                self.last_error = "%d/%s: %s" % (recid, key, e)
                self.emit(tag, "%d %s %d 0 0 failed: %s" % (recid, key, size, e))
                self.request_stop("blocked or protocol surprise", 1)
                return
            except (OSError, ValueError, http.client.HTTPException) as e:
                after = psize(part)
                self.have[i] = cur["got"] = min(after, size)
                fails = 0 if after > before else fails + 1      # N CONSECUTIVE attempts without added bytes
                with self.lock:
                    self.retries += 1
                    self.last_error = "%d/%s: %s" % (recid, key, e)
                self.emit(tag, "%d %s attempt %d: %s (part %d -> %d bytes, attempts without progress: %d)"
                          % (recid, key, attempt, e, before, after, fails))
                if fails >= a.max_stalls:
                    with self.lock:
                        self.errors += 1
                        self.give_ups += 1
                        self.fail_streak += 1
                        streak = self.fail_streak
                    self.emit(tag, "%d %s %d 0 0 failed" % (recid, key, size))
                    if streak >= self.nthreads:
                        if self.nthreads == 1:
                            self.request_stop("%d consecutive attempts without progress on %d/%s"
                                              % (a.max_stalls, recid, key), 1)
                        else:
                            self.request_stop("%d files in a row gave up with no data from any connection in between; "
                                              "the network seems down" % streak, 1)
                    return
                wait = a.retry_wait if after <= before else min(RETRY_AFTER_PROGRESS, a.retry_wait)
                cur["note"] = "retry in %.0f s" % wait
                self.stop.wait(wait)
                continue
            secs = st["secs"]
            self.emit(tag, "%d %s %d %.1f %.1f %s" % (recid, key, size, secs, size / 1000.0 / max(secs, 1e-9), outcome))
            self.finish_row(i, st["sha"], start, utc(), attempt, st["resumed"], new=True)
            return

    def finish_row(self, i, sha, start, end, attempts, resumed, new):
        recid, key, size, want, url = self.rows[i]
        with self.lock:
            append_log(self.outdir, (recid, key, size, want, sha, start, end, attempts, resumed))
            self.done[i] = True
            self.have[i] = size
            self.shas[(recid, key)] = sha
            self.done_log[(recid, key)] = (size, want)
            if new:
                self.newly += 1
            self.write_sums(recid)

    def write_sums(self, recid):
        """SHA256SUMS of a record, in sha256sum format, once every file of the record is done."""
        idx = [i for i, r in enumerate(self.rows) if r[0] == recid]
        if not idx or not all(self.done[i] for i in idx):
            return False
        path = os.path.join(self.outdir, str(recid), SUMS)
        with open(path + ".tmp", "w") as f:
            for i in idx:
                f.write("%s  %s\n" % (self.shas[(recid, self.rows[i][1])], self.rows[i][1]))
        os.replace(path + ".tmp", path)
        return True

    def download_once(self, i, tag, cur, st):
        """One attempt. Returns the outcome word. Raises Block, Stopped, or OSError/ValueError/HTTPException (retry)."""
        a = self.a
        recid, key, size, want, url = self.rows[i]
        target = self.target(i)
        part = target + ".part"
        p = psize(part)
        if p > size:
            move_bad(part, target)
            p = 0
            self.have[i] = cur["got"] = 0
        t0 = time.monotonic()
        outcome = "fetched"
        if p < size:
            req = urllib.request.Request(url)
            if p > 0:
                req.add_header("Range", "bytes=%d-" % p)
            cur["note"] = "connecting"
            try:
                resp = urllib.request.urlopen(req, timeout=READ_TIMEOUT, context=CTX)
            except urllib.error.HTTPError as e:
                if 400 <= e.code < 500:
                    raise Block("HTTP %d for %s" % (e.code, url))
                raise OSError("HTTP %d for %s" % (e.code, url))
            with resp:
                if resp.status == 206:
                    cr = resp.headers.get("Content-Range", "")
                    m = re.match(r"bytes (\d+)-", cr)
                    if not m or int(m.group(1)) != p:
                        raise Block("206 with Content-Range %r, wanted start %d" % (cr, p))
                    mode, outcome = "ab", "resumed"
                    st["resumed"] = "yes"
                elif resp.status == 200:
                    mode, outcome = "wb", ("restarted" if p > 0 else "fetched")
                    p = 0
                    self.have[i] = cur["got"] = 0
                else:
                    raise Block("HTTP status %d" % resp.status)
                if p > 0:
                    ad, sha = hash_file(part)
                else:
                    ad, sha = 1, hashlib.sha256()
                tick = win = time.monotonic()
                tick_p = win_p = p
                cur["live"], cur["note"] = True, ""
                try:
                    with open(part, mode, buffering=0) as f:
                        while True:
                            if self.stop.is_set():
                                raise Stopped()
                            b = resp.read1(CHUNK)
                            if not b:
                                break
                            f.write(b)
                            ad = zlib.adler32(b, ad)
                            sha.update(b)
                            p += len(b)
                            self.have[i] = cur["got"] = min(p, size)
                            self.fail_streak = 0
                            now = time.monotonic()
                            if now - tick >= PROGRESS:
                                self.emit(tag, "%d %s progress: %d of %d bytes, %.1f %%, %.1f kB/s"
                                          % (recid, key, p, size, 100.0 * p / size,
                                             (p - tick_p) / 1000.0 / (now - tick)))
                                tick, tick_p = now, p
                            if now - win >= a.stall_seconds:
                                if p - win_p < a.stall_limit * (now - win):
                                    raise OSError("stalled: %d bytes in %.0f s" % (p - win_p, now - win))
                                win, win_p = now, p
                            if p > size:
                                break
                finally:
                    cur["live"] = False
        else:
            ad, sha = hash_file(part)
        st["secs"] = time.monotonic() - t0
        if p < size:
            raise OSError("stream ended short: %d of %d bytes" % (p, size))
        if p != size or hexad(ad) != want:
            move_bad(part, target)
            self.have[i] = cur["got"] = 0
            raise ValueError("verification failed: bytes %d (want %d), adler32 %s (want %s)" % (p, size, hexad(ad), want))
        st["sha"] = sha.hexdigest()
        os.rename(part, target)
        return outcome

    # ---- the dashboard
    def render(self, final=False):
        now = time.monotonic()
        if self.tty:
            try:
                cols, term_rows = os.get_terminal_size(sys.stdout.fileno())
            except OSError:
                cols, term_rows = shutil.get_terminal_size((100, 40))
        else:
            cols, term_rows = (100, 40)

        def cut(text):
            return text if len(text) < cols else text[:cols - 1]

        narrow = cols < 100          # an 80-column terminal gets shorter bars and names so the speeds stay visible
        rec_bar, file_bar, key_w = (10, 6, 14) if narrow else (20, 16, 20)

        have_total = sum(self.have)
        grand = sum(r[2] for r in self.rows)
        cur = dict(self.cur)
        snap = {i: c["got"] for i, c in cur.items()}
        window = max(10.0, self.report)
        ref, recent = None, None
        if self.hist:
            ref = self.hist[0]
            dt = now - ref[0]
            if dt > 0.5:
                recent = max(0, have_total - ref[1]) / dt
            else:
                ref = None
        gained = have_total - self.baseline
        elapsed = now - self.t0
        average = gained / elapsed if elapsed > 0 and gained > 0 else None
        eta = clock((grand - have_total) / average) if average else "unknown"
        shown_rows, stalled, live = [], 0, 0
        for i, c in cur.items():
            size = c["size"]
            rate = None
            for t_old, _total, files_old in self.hist:         # oldest snapshot that still holds this file
                if i in files_old and now - t_old > 0.5:
                    rate = max(0, c["got"] - files_old[i]) / (now - t_old)
                    break
            if c["live"]:
                live += 1
                if rate == 0:
                    stalled += 1
            shown_rows.append((c["got"] / size if size else 0.0, i, rate, c))
        self.hist.append((now, have_total, snap))
        while len(self.hist) > 1 and now - self.hist[1][0] >= window:
            self.hist.popleft()
        waiting = sum(1 for i in range(self.n) if not self.done[i] and i not in cur and self.have[i] > 0)
        files_done = sum(self.done)
        fraction = have_total / grand if grand else 0.0
        per_conn = recent / live if live and recent is not None else None
        title = "E11 piece B download  |  %s  |  elapsed %s  |  %d workers" % (
            time.strftime("%H:%M:%S"), clock(elapsed), self.nthreads)
        top = [("\033[1m" + cut(title) + "\033[0m") if self.tty else cut(title),
               cut("TOTAL    %s %5.1f%%   %s / %s" % (bar(fraction, 30), fraction * 100, human(have_total), human(grand))),
               cut("FILES    %d/%d complete   %d downloading   %d workers alive" % (files_done, self.n, len(cur), self.alive)),
               cut("SPEED    now %s   average %s   ETA %s" % (rate_text(recent), rate_text(average), eta)),
               cut("LINKS    %d connections open   %s each   %d stalled right now" % (live, rate_text(per_conn) if live else "-", stalled)),
               cut("HEALTH   retries %d   errors %d%s" % (self.retries, self.errors,
                                                          "   (+%d partial files waiting for a worker)" % waiting if waiting else ""))]
        if self.last_error:
            top.append(cut("LASTERR  " + self.last_error))
        bot = ["", cut("Ctrl-C stops cleanly; rerun resumes   |   log: %s" % os.path.join(self.outdir, RUNLOG))]

        rec_stats = []
        grp_map = {}
        grp_order = []
        present = {r[0] for r in self.rows}
        ordered_recids = [r[0] for r in RECORDS if r[0] in present] + sorted(present - set(RECNAME))
        for recid in ordered_recids:
            idx = [i for i, r in enumerate(self.rows) if r[0] == recid]
            total = sum(self.rows[i][2] for i in idx)
            have = sum(self.have[i] for i in idx)
            done_c = sum(self.done[i] for i in idx)
            name = RECNAME.get(recid, str(recid))
            rec_stats.append((recid, name, done_c, len(idx), have, total))
            gname = name.split("_", 1)[0]
            if gname not in grp_map:
                grp_map[gname] = [0, 0, 0, 0, 0]
                grp_order.append(gname)
            g = grp_map[gname]
            g[0] += 1
            g[1] += done_c
            g[2] += len(idx)
            g[3] += have
            g[4] += total

        shown_rows.sort(key=lambda t: (-t[0], t[1]))
        want_files = len(shown_rows) if self.a.file_lines == "all" else int(self.a.file_lines)
        max_total = max(6, term_rows - 1) if self.tty else 100000
        min_tail = min(4 if shown_rows else 2, max(0, max_total - len(top) - len(bot)))
        rec_budget = max(0, max_total - len(top) - len(bot) - min_tail) if self.tty else 100000

        rec_lines = []
        half = (len(rec_stats) + 1) // 2
        if not self.tty or rec_budget >= 2 + len(rec_stats):
            rec_lines = ["", cut("RECORDS")]
            for recid, name, dc, tc, have, total in rec_stats:
                frac = have / total if total else 0.0
                rec_lines.append(cut("  %d %-11s %s %5.1f%%   %3d/%-3d files   %s / %s" % (
                    recid, name, bar(frac, rec_bar), frac * 100, dc, tc, human(have), human(total))))
        elif cols >= 108 and rec_budget >= 2 + half:
            rec_lines = ["", cut("RECORDS (%d total)" % len(rec_stats))]
            col_w = (cols - 3) // 2
            left_cols = []
            for recid, name, dc, tc, have, total in rec_stats:
                frac = have / total if total else 0.0
                gname = name.split("_", 1)[0]
                cell = "  %d %-6s %s %5.1f%% %d/%d %s/%s" % (
                    recid, gname[:6], bar(frac, 6), frac * 100, dc, tc, human(have), human(total))
                left_cols.append(cell[:col_w].ljust(col_w))
            for k in range(half):
                if k + half < len(left_cols):
                    rec_lines.append(cut(left_cols[k] + " | " + left_cols[k + half].lstrip()))
                else:
                    rec_lines.append(cut(left_cols[k].rstrip()))
        elif len(grp_order) < len(rec_stats) and rec_budget >= 2 + len(grp_order):
            rec_lines = ["", cut("RECORDS (by group; %d records total)" % len(rec_stats))]
            for gname in grp_order:
                nrec, dc, tc, have, total = grp_map[gname]
                frac = have / total if total else 0.0
                label = "%s (%d)" % (gname, nrec)
                rec_lines.append(cut("  %-13s %s %5.1f%%   %3d/%-3d files   %s / %s" % (
                    label, bar(frac, rec_bar), frac * 100, dc, tc, human(have), human(total))))
        elif rec_budget >= 4:
            rec_lines = ["", cut("RECORDS")]
            items = [(gname, grp_map[gname][1], grp_map[gname][2], grp_map[gname][3], grp_map[gname][4]) for gname in grp_order] \
                if len(grp_order) < len(rec_stats) else [(str(r[0]) + " " + r[1], r[2], r[3], r[4], r[5]) for r in rec_stats]
            keep = max(1, rec_budget - 3)
            for label, dc, tc, have, total in items[:keep]:
                frac = have / total if total else 0.0
                rec_lines.append(cut("  %-13s %s %5.1f%%   %3d/%-3d files   %s / %s" % (
                    label[:13], bar(frac, rec_bar), frac * 100, dc, tc, human(have), human(total))))
            if len(items) > keep:
                rec_lines.append(cut("  … and %d more" % (len(items) - keep)))

        rem_budget = max_total - len(top) - len(rec_lines) - len(bot)
        if self.tty:
            avail_files = max(0, rem_budget - 2)
            if len(shown_rows) > min(want_files, avail_files) and avail_files > 0:
                avail_files = max(0, avail_files - 1)
            want_lines = min(want_files, avail_files)
        else:
            want_lines = max(1, want_files)
        shown = shown_rows[:want_lines]
        tail = ["", cut("DOWNLOADING NOW (showing %d of %d, nearest to done first)" % (len(shown), len(shown_rows)))]
        for frac, i, rate, c in shown:
            recid, key, size = self.rows[i][0], self.rows[i][1], c["size"]
            short = key if len(key) <= key_w else "…" + key[-(key_w - 1):]
            if c["note"] and not c["live"]:
                speed = c["note"]
            elif rate is None:
                speed = "measuring"
            elif rate > 0:
                speed = "%s  ETA %s" % (rate_text(rate), clock((size - c["got"]) / rate))
            else:
                speed = "no data right now (will resume)"
            tail.append(cut("  %d %-*s %s %3.0f%%  %s / %s  %s" % (
                recid, key_w, short, bar(frac, file_bar), frac * 100, human(c["got"]).rjust(0 if narrow else 9),
                human(size).ljust(0 if narrow else 9), speed)))
        if len(shown_rows) > len(shown) and (not self.tty or len(top) + len(rec_lines) + len(tail) + len(bot) < max_total):
            tail.append(cut("  … and %d more" % (len(shown_rows) - len(shown))))
        all_lines = top + rec_lines + tail + bot
        if self.tty and len(all_lines) > max_total:
            all_lines = all_lines[:max_total]
        block = "\n".join(all_lines)
        with self.outlock:
            if self.tty:
                if self.prev_lines:
                    sys.stdout.write("\033[%dA\r\033[J" % self.prev_lines)
                sys.stdout.write(block + "\n")
                self.prev_lines = block.count("\n") + 1
            else:
                sys.stdout.write(block + "\n\n")
            sys.stdout.flush()

    # ---- the run
    def start(self):
        a = self.a
        self.logf = open(os.path.join(self.outdir, RUNLOG), "a", encoding="utf-8", buffering=1)
        self.done_log, self.shas = read_log(self.outdir)
        for i, (recid, key, size, want, url) in enumerate(self.rows):
            d = os.path.join(self.outdir, str(recid))
            os.makedirs(d, exist_ok=True)
            t = os.path.join(d, key)
            if os.path.exists(t):
                self.have[i] = min(os.path.getsize(t), size)
                self.done[i] = self.done_log.get((recid, key)) == (size, want) and os.path.getsize(t) == size
            else:
                self.have[i] = min(psize(t + ".part"), size)
        self.baseline = sum(self.have)
        self.emit("", "RUN START workers=%d dashboard=%s max_stalls=%d retry_wait=%s stall=%s B/s over %s s"
                  % (self.nthreads, a.dashboard, a.max_stalls, a.retry_wait, a.stall_limit, a.stall_seconds), show=False)
        if a.dashboard:
            total_b = sum(r[2] for r in self.rows)
            self.say("DOWNLOAD START UTC: %s" % utc())
            self.say("DOWNLOAD ROOT: %s" % self.outdir)
            self.say("DOWNLOAD LOG: %s" % os.path.join(self.outdir, RUNLOG))
            if a.cafile_fp:
                self.say("TLS CA fingerprint (pinned, matches): %s" % a.cafile_fp)
            self.say("TOTAL FILES: %d" % self.n)
            self.say("TOTAL BYTES: %d" % total_b)
            self.say("ON DISK AT START: %d files complete, %d bytes of %d" % (sum(self.done), self.baseline, total_b))
            self.say("WORKERS: %d (set E11_PIECEB_WORKERS to change); refresh every %.0f s" % (self.nthreads, self.report))
        threads = []
        for w in range(self.nthreads):
            t = threading.Thread(target=self.worker, args=(w,), daemon=True)
            t.start()
            threads.append(t)
            if self.nthreads > 1 and w < self.nthreads - 1:
                self.stop.wait(0.3)          # spread the connection set-up
        if self.n == 0 or self.alive == 0:
            self.all_done.set()
        return threads

    def monitor(self):
        stop_seen = None
        while True:
            if self.a.dashboard:
                self.render()
            finished = self.all_done.wait(timeout=self.report if self.a.dashboard else 1.0)
            if finished:
                break
            if self.stop.is_set():
                stop_seen = stop_seen or time.monotonic()
                if time.monotonic() - stop_seen > 15:      # threads blocked in a read: they are daemons, leave them
                    break
        if self.a.dashboard:
            self.render(final=True)

    def finish(self):
        """Write the SHA256SUMS of complete records, print the end lines, return the exit code."""
        with self.lock:
            sums = [rid for rid in sorted({r[0] for r in self.rows}) if self.write_sums(rid)]
        dn = sum(self.done)
        db = sum(r[2] for i, r in enumerate(self.rows) if self.done[i])
        total_b = sum(r[2] for r in self.rows)
        if self.stop_reason is not None and self.stop_code != 0:
            reason, code = self.stop_reason, self.stop_code
        elif self.give_ups:
            reason, code = "%d file(s) gave up; rerun to resume" % self.give_ups, 1
        elif self.stop_reason is not None:
            reason, code = self.stop_reason, 0
        elif dn == self.n:
            reason, code = "all files done", 0
        else:
            reason, code = "stopped with %d files not done" % (self.n - dn), 1
        if self.a.dashboard:
            for rid in sums:
                self.say("SHA256SUMS written for record %d: %s" % (rid, os.path.join(self.outdir, str(rid), SUMS)))
            self.say("DOWNLOAD END UTC: %s" % utc())
            self.say("done %d of %d files, %d of %d bytes; exit reason: %s" % (dn, self.n, db, total_b, reason))
            if code == 0 and dn == self.n:
                self.say("DOWNLOAD COMPLETE")
            elif code == 130:
                self.say("INTERRUPTED: partial files are kept. Rerun the script to resume.")
            else:
                self.say("DOWNLOAD INCOMPLETE (%s); rerun the script to resume. Details: %s"
                         % (reason, os.path.join(self.outdir, RUNLOG)))
        else:
            self.emit("", "done %d of %d files, %d of %d bytes; exit reason: %s" % (dn, self.n, db, total_b, reason))
        return code


def dry_run(a, rows, fp):
    done, _ = read_log(a.outdir) if os.path.isdir(a.outdir) else ({}, {})
    total_b = sum(r[2] for r in rows)
    print("DRY RUN START UTC: %s" % utc())
    print("DOWNLOAD ROOT: %s%s" % (a.outdir, "" if os.path.isdir(a.outdir) else " (does not exist yet; nothing is created)"))
    if fp:
        print("TLS CA fingerprint (pinned, matches): %s" % fp)
    on_disk = n_done = n_part = 0
    for recid, key, size, want, url in rows:
        t = os.path.join(a.outdir, str(recid), key)
        if os.path.exists(t) and done.get((recid, key)) == (size, want):
            n_done += 1
            on_disk += size
        elif os.path.exists(t + ".part"):
            n_part += 1
            on_disk += min(psize(t + ".part"), size)
    for recid in sorted({r[0] for r in rows}):
        rr = [r for r in rows if r[0] == recid]
        print("record %d %s: %d files, %d bytes; first URL %s" % (recid, RECNAME.get(recid, ""), len(rr), sum(r[2] for r in rr), rr[0][4]))
    print("TOTAL FILES: %d, TOTAL BYTES: %d" % (len(rows), total_b))
    print("ON DISK: %d files complete, %d partial, %d of %d bytes" % (n_done, n_part, on_disk, total_b))
    probe = a.outdir
    while probe and not os.path.isdir(probe):
        probe = os.path.dirname(probe)
    print("FREE SPACE: %d bytes (needs about %d more, plus 2 GiB)" % (shutil.disk_usage(probe or ".").free, total_b - on_disk))
    print("WORKERS: %d, max attempts without progress per file: %d" % (a.workers, a.max_stalls))
    print("DRY RUN: list and CA checks complete; no payload files fetched")
    return 0


def cmd_fetch(a):
    global CTX, PROGRESS, READ_TIMEOUT
    sys.stdout.reconfigure(errors="replace")
    PROGRESS = a.progress_seconds
    READ_TIMEOUT = a.read_timeout
    a.report = None if a.report_seconds == "auto" else float(a.report_seconds)
    all_rows = read_list(a.list)
    msg = check_outdir(a.outdir, all_rows)
    rows = all_rows if a.only is None else [r for r in all_rows if r[0] == a.only]
    if a.eos:
        rows = [(r[0], r[1], r[2], r[3], eos_url(r[1])) for r in rows]
    a.cafile_fp = None
    if a.cafile:
        if a.cafile_sha256:
            try:
                a.cafile_fp = ca_fingerprint(a.cafile)
            except (OSError, ValueError) as e:
                print("refused: %s" % e)
                return 2
            if a.cafile_fp != a.cafile_sha256.upper():
                print("refused: CA file fingerprint %s is not the pinned %s" % (a.cafile_fp, a.cafile_sha256.upper()))
                return 2
        CTX = ssl.create_default_context(cafile=a.cafile)
    if msg:
        print("refused: %s" % msg)
        return 2
    if a.dry_run:
        return dry_run(a, rows, a.cafile_fp)
    os.makedirs(a.outdir, exist_ok=True)
    others = other_fetchers(a.outdir)
    if others:
        print("refused: another s3b_fetch_dst.py fetch (PID %s) is using this directory; stop it first (Ctrl-C in its "
              "terminal), then run again" % ", ".join(map(str, others)))
        return 3
    lock, owner = acquire_lock(a.outdir)
    if lock is None:
        print("refused: another download is already running (PID %s); two instances would corrupt the .part files" % owner)
        return 3
    runner = Runner(a, rows)

    def on_term(signum, frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, on_term)
    try:
        try:
            runner.start()
            runner.monitor()
        except KeyboardInterrupt:
            runner.request_stop("interrupted", 130)
            if a.dashboard:
                runner.say("INTERRUPTED: stopping all workers; partial files are kept")
            runner.all_done.wait(timeout=3)
        code = runner.finish()
    finally:
        release_lock(lock)
        if runner.logf:
            runner.logf.close()
    return code


# ---------------------------------------------------------------- status
def cmd_status(list_path, outdir):
    rows = read_list(list_path)
    done, _ = read_log(outdir)
    stats = {}
    for recid, key, size, want, _ in rows:
        s = stats.setdefault(recid, {k: [0, 0] for k in ("done", "present, not verified", "partial", "bad", "missing")})
        t = os.path.join(outdir, str(recid), key)
        if os.path.exists(t):
            k = "done" if done.get((recid, key)) == (size, want) else "present, not verified"
            s[k][0] += 1
            s[k][1] += size
        elif os.path.exists(t + ".part"):
            s["partial"][0] += 1
            s["partial"][1] += os.path.getsize(t + ".part")
        else:
            s["missing"][0] += 1
            s["missing"][1] += size
        d = os.path.dirname(t)
        if os.path.isdir(d):
            for g in os.listdir(d):
                if re.fullmatch(re.escape(key) + r"\.bad\d*", g):
                    s["bad"][0] += 1
                    s["bad"][1] += os.path.getsize(os.path.join(d, g))
    tot = {k: [0, 0] for k in ("done", "present, not verified", "partial", "bad", "missing")}
    for recid in sorted(stats):
        print("record %d: " % recid + "; ".join("%s %d files %d bytes" % (k, v[0], v[1]) for k, v in stats[recid].items()))
        for k, v in stats[recid].items():
            tot[k][0] += v[0]
            tot[k][1] += v[1]
    print("total: " + "; ".join("%s %d files %d bytes" % (k, v[0], v[1]) for k, v in tot.items()))
    probe = outdir
    while probe and not os.path.isdir(probe):         # status creates nothing: use the nearest existing parent
        probe = os.path.dirname(probe)
    print("free space on %s: %d bytes" % (outdir, shutil.disk_usage(probe or ".").free))
    return 0


def cmd_probe(a):
    ctx = ssl.create_default_context(cafile=a.cafile) if a.cafile else None
    for n, url in enumerate(a.urls):
        if n:
            time.sleep(5)
        t0 = time.monotonic()
        got, tick, status = 0, t0, None
        try:
            with urllib.request.urlopen(url, timeout=30, context=ctx) as r:
                status = r.status
                last = 0
                while time.monotonic() - t0 < a.seconds:
                    b = r.read1(CHUNK)
                    if not b:
                        break
                    got += len(b)
                    now = time.monotonic()
                    if now - tick >= 10:
                        print("%s status %s bytes %d, %.1f s, mean %.1f kB/s" % (url, status, got, now - t0, got / 1000.0 / (now - t0)), flush=True)
                        tick = now
        except urllib.error.HTTPError as e:
            status = e.code
        except (urllib.error.URLError, OSError, http.client.HTTPException) as e:
            print("%s error after %d bytes: %r" % (url, got, e), flush=True)
        dt = time.monotonic() - t0
        print("END %s status %s bytes %d, %.1f s, mean %.1f kB/s" % (url, status, got, dt, got / 1000.0 / max(dt, 1e-9)), flush=True)
    return 0


def main(argv):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").add_argument("out")
    f = sub.add_parser("fetch")
    f.add_argument("list")
    f.add_argument("outdir")
    f.add_argument("--workers", type=int, default=1, help="download threads (default 1)")
    f.add_argument("--dashboard", action="store_true", help="progress dashboard on the terminal, detail in OUTDIR/download.log")
    f.add_argument("--report-seconds", default="auto", help="dashboard refresh: seconds, or auto (5 on a terminal, 30 piped)")
    f.add_argument("--file-lines", default="8", help="active files listed in the dashboard (a number, or all)")
    f.add_argument("--max-stalls", type=int, default=3, help="consecutive attempts without progress before giving up on a file")
    f.add_argument("--read-timeout", type=float, default=300.0, help="seconds a read may block before the attempt fails")
    f.add_argument("--stall-seconds", type=float, default=120.0)
    f.add_argument("--stall-limit", type=float, default=1024.0, help="bytes/s under which a connection counts as stalled")
    f.add_argument("--max-seconds", type=float, default=None)
    f.add_argument("--max-files", type=int, default=None)
    f.add_argument("--only", type=int, default=None)
    f.add_argument("--retry-wait", type=float, default=60.0)
    f.add_argument("--pause", type=float, default=None, help="seconds between files per thread (default 5 with one worker, else 0)")
    f.add_argument("--progress-seconds", type=float, default=60.0, help="seconds between progress lines in the log")
    f.add_argument("--eos", action="store_true", help="take each URL from the EOS rule, not from the list")
    f.add_argument("--cafile", default=None, help="CA file for every HTTPS request (verification stays on)")
    f.add_argument("--cafile-sha256", default=None, help="refuse to run unless the CA file has this SHA-256 fingerprint")
    f.add_argument("--dry-run", action="store_true", help="check the list, CA file and disk; fetch nothing, create nothing")
    pr = sub.add_parser("probe")
    pr.add_argument("urls", nargs="+")
    pr.add_argument("--cafile", default=None)
    pr.add_argument("--seconds", type=float, default=90.0)
    s = sub.add_parser("status")
    s.add_argument("list")
    s.add_argument("outdir")
    a = p.parse_args(argv[1:])
    if a.cmd == "list":
        return cmd_list(a.out)
    if a.cmd == "fetch":
        return cmd_fetch(a)
    if a.cmd == "probe":
        return cmd_probe(a)
    return cmd_status(a.list, a.outdir)


if __name__ == "__main__":
    code = main(sys.argv)
    sys.stdout.flush()
    sys.stderr.flush()
    if threading.active_count() > 1:       # daemon download threads still blocked in a read: do not wait for them
        os._exit(code)
    sys.exit(code)
