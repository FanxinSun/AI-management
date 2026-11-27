#!/usr/bin/python3 -I
"""Template: the driver of a chunked all-in-one pipeline (a "split script"), in the form of e7's tools/s6_pipe.py
(general/templates/chunked-pipeline/; the method: general/guides/chunked-pipeline-workflow/CHUNKED_PIPELINE_GUIDE.md).

This is e7's step-6 driver, tools/s6_pipe.py of the user's project e7-upsilon-omega (sha256
027c887a06a0a57d263b765ba438966189ef60674855909d3d69f2f802234449, pinned in e7's tools/s6_all_in_one.pins on 2026-11-27), with e7's own
work taken out: e7's chain of jobs per file is the table JOBS below, its end-of-split analysis is END_JOBS and FACTS_JOB, its version-1
skim is TEMP_OUTPUTS, its lean skim is KEPT_OUTPUTS, and its names are the constants below. What it prints, the bridge lines, report.md,
status.tsv, files.tsv, nudges.tsv, deletions.tsv, the status command, the lock, the pins, the gates, the waits, the exit codes and the
test modes are e7's: with e7's values (in the comments) the lines are e7's. README.md lists what differs from e7 and how to test a copy.
Standard library only; run as /usr/bin/python3 -I tools/pipe.py, normally through tools/all_in_one.sh.

usage: pipe.py SPLIT          run, or resume, one split (SPLITS, in their order), file by file: space check, download, the JOBS (each
                              through the logger; a failed job fails the file), keep, a report line to the manager; a file's source, its
                              .part files and its TEMP_OUTPUTS are deleted only after the manager accepted the file; at the end of the
                              split: END_JOBS, the facts (FACTS_JOB), the wait for the acceptances, the report, the nudge.
       pipe.py status         every split; no network; creates nothing.
       pipe.py status SPLIT   one split, file by file.
Settings (environment, all optional; ENV is the prefix below): ENV+NUDGE (end-of-split targets in order, default NUDGE_DEFAULT),
ENV+FILE_NUDGE (the file reports' targets, default FILE_NUDGE_DEFAULT), ENV+POLL_S (seconds between polls of a wait, default 300),
ENV+WAIT_H (hours a wait lasts, default 24), ENV+CAP_MIN (the split's compute cap, default 840), ENV+RETRY=1 (retry a failed job as
<id>-r2, then -r3), ENV+FLOOR_GIB (free space kept beyond the file's size, default 10); the downloader's settings (download_one.sh).
Exit status: 0 the split is DONE (or PAUSED after the pilot file) and the nudge was delivered; 1 stopped or failed, or the split ended
with failed files ('DONE, <n> file(s) failed: <ids>') or with files kept until accepted (report written, nudge sent), or the nudge
failed; 2 wrong usage, or a pinned tool changed; 3 another copy is running, or the downloader's own 3; 4 the split may not start (the
gates); 130 Ctrl-C (no nudge; a rerun resumes). Tests only: pipe.py --test fail|partial|pilot|disk|cap|error|sleep (a made-up file
list, job ids TEST_PREFIX-...), and the setting TESTENV+TEST_ROOT=<folder> with a split named tst<anything> (list
<folder>/files-<split>.tsv, downloads under <folder>/downloads, job ids TEST_PREFIX-<split>-..., outputs under runs/<ST>/pipeline-test/;
no gates); with it TESTENV+FAKE=1 (made-up files, no download, no END_JOBS and no facts) and TESTENV+SEND=<path> (another bridge
script). The TESTENV settings are read only in a sandbox run.
Deletions: a file that passed every job is KEPT (its source, its .part files and its TEMP_OUTPUTS stay) until the manager has put its
8-character id in runs/<ST>/<split>/accepted-files.tsv. Only then, in a deletion pass (at the start of each file, in each poll of a
wait, and at the end of the split), the script deletes that file's source, its .part files and its TEMP_OUTPUTS, each by its full path,
each logged in runs/<ST>/<split>/deletions.tsv before it is removed. Never while runs/<ST>/HOLD exists. Nothing else is deleted or
moved, except a retry's partial output (the outputs of a JOBS entry), which is renamed *.failed-N, and the lock folder at the end."""
import datetime
import glob
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.environ.get("HOME", "/var/empty")

# ---- the project's names: change them when you copy the file (with e7's values, in the comments, every line is e7's)
PROJECT = "PROJECT"                   # e7: "E7"       -> "E7 step-6 split script: status (no network; nothing is created)"
STEP_WORD = "step-1"                  # e7: "step-6"
ST = "S1"                             # e7: "S6"       the logger's --step, the run folder runs/S6, the bridge tag "[PIPELINE s6 ...]"
SPLITS = ["g1", "g2"]                 # e7: ["g1", "g2", "g3", "g4", "h1", "h2", "h3", "h4"]; each: runs/<ST>/splits/files-<split>.tsv
ENV = "PROJECT_PIPE_"                 # e7: "E7_PIPE_"  (E7_PIPE_NUDGE, E7_PIPE_FILE_NUDGE, E7_PIPE_POLL_S, ...)
TESTENV = "PROJECT_PIPE_SANDBOX_"     # e7: "E7_S6_"    (E7_S6_TEST_ROOT, E7_S6_FAKE, E7_S6_SEND, E7_S6_FAKE_FAIL)
DL_DRY_RUN = "PROJECT_DL_DRY_RUN"     # e7: "E7_S2_DRY_RUN" (the downloader's dry run; with it a split only checks its list and the disk)
NUDGE_DEFAULT = "PROJECT executor,PROJECT Committee"    # e7: "e7 executor,e7 Committee"
FILE_NUDGE_DEFAULT = "PROJECT Committee"               # e7: "e7 Committee"
WRAPPER = "all_in_one.sh"             # e7: "s6_all_in_one.sh"   (named in the usage line)
DOWNLOADER = "tools/download_one.sh"  # e7: "tools/s6_download.sh"
PINS = "tools/all_in_one.pins"        # e7: "tools/s6_all_in_one.pins"
TEST_PREFIX = "pt1"                   # e7: "pt6"      the job ids of a test run: pt6-<test>-<id>-<step>
KEPT_WORD = "temporary outputs"       # e7: "version-1 skim" -> "file <id> FAILED at <step>: its source and version-1 skim stay"
OUTPUT_WORD = "output"                # e7: "lean"     -> the report's column "lean bytes"
KEEP_STEP = "the keep step"           # e7: "step 12"  -> "file <id>: all jobs passed earlier; step 12 again (keep)"
TEST_TAIL = "this is a test, nothing to do"            # e7: "this is a test of order 13, nothing to do"
SANDBOX_NUDGE_TAIL = "this is a test, nothing to do"   # e7: "this is a test of handover 12, nothing to do"
PY = ["/usr/bin/python3", "-I"]       # e7: [HOME + "/system-env/e7/bin/python", "-I"]  the Python of the jobs
PREFLIGHT_IMPORTS = ""                # e7: "import uproot, awkward, numpy, scipy" (checked with PY before a run; "" = no check)
LONG_OK = ""                          # e7: the user's approval, in the user's words, for jobs over 1800 s (run_logged.py --long-ok)
JOB_MEM_MB = 6000                     # e7: 6000       the logger's --mem

# ---- the project's work (e7's own jobs are named in the comments)
# JOBS: the jobs of one file after its download, in order; each must exit 0 (a failed job fails the file; its source stays).
#   (stage, step, limit in seconds, command, outputs). The job id is <split>-<file id>-<step> (no "-" in a step). In the command,
#   {list} {dest} {src} {rd} {fid} {key} {stem} {recid} {size} {adler32} {sfx} are filled in: {src} is the downloaded file, {rd} is
#   runs/<ST>/<split>/<file id>, {sfx} the retry suffix ('' or -r2 or -r3). outputs: files the job makes (the same fields); before a
#   retry each one that exists is renamed <name>.failed-N.
#   e7: S2 verify, S3 probe, S3 skim1 (the version-1 skim), S4 check1 (with e7's rule C and S4 diag1), S5 recheck1, S7 menus,
#   S6 lean (the lean skim), S6 leancheck, S6 mgrlean, S6 eval.
JOBS = [
    ("S2", "verify", 600, PY + ["tools/verify_download.py", "{list}", "{dest}"], []),
]
# TEMP_OUTPUTS: per-file files kept with the source until the manager accepts the file, then deleted with it
#   (the same fields as JOBS; e7: data/s6/v1tmp/{stem}.skim.root, the version-1 skim).
TEMP_OUTPUTS = []
# KEPT_OUTPUTS: per-file files that stay for good; their bytes are the report's OUTPUT_WORD column, and END_JOBS can take them
#   (e7: data/s6/lean/{stem}.lean.root, the lean skim).
KEPT_OUTPUTS = []
# END_JOBS: jobs run once at the end of the split, stage S9, each through the logger: (step, limit, command, the step it needs or None).
#   {rundir} {split} {sfx} {dep_sfx} are filled in ({dep_sfx}: the suffix of the needed step's latest attempt); an argument
#   "{done_outputs}" becomes the KEPT_OUTPUTS of the split's DONE files, "{all_done_outputs}" those of every split's DONE files.
#   e7: m1 (1800 s), m6 (3600 s), m6fit (120 s, needs m6), m1cum (3600 s).
END_JOBS = []
# FACTS_JOB: one job after END_JOBS, stage S8, (limit, command) with {rundir} {split} {sfx}, that writes {rundir}/facts.md;
#   None: no facts (e7: tools/s6_facts.py <split>, 120 s).
FACTS_JOB = None

LOGGER = ["/usr/bin/python3", "-I", "tools/run_logged.py"]
SEND = os.path.expanduser("~/.claude/agy-bridge/send_to_tty.sh")
BY = "%s all-in-one script" % ST.lower()
RUNS = "runs/%s" % ST
PILOT_NAME = "%s-pilot" % SPLITS[0]
MAXW = 99
NUDGE_TAIL = "now carry out %s/handover-split.md" % RUNS
FILE_TAIL = "now carry out %s/handover-file.md" % RUNS
SEND_TIMEOUT = 180
TEST_STEPS = ("verify", "skim1", "check1")
FAKE_STEPS = ("verify", "skim1")


class Stop(Exception):
    def __init__(self, status):
        Exception.__init__(self, status)
        self.status = status


class FileFail(Exception):
    def __init__(self, step):
        Exception.__init__(self, step)
        self.step = step


class Interrupted(Exception):
    pass


def P(x):
    return x if os.path.isabs(x) else os.path.join(ROOT, x)


def sha256(path):
    h = hashlib.sha256()
    with open(P(path), "rb") as f:
        for blk in iter(lambda: f.read(8 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_tsv(path):
    with open(P(path), encoding="utf-8") as f:
        lines = f.read().split("\n")
    lines = [l for l in lines if l.strip()]
    head = lines[0].split("\t")
    return [dict(zip(head, l.split("\t"))) for l in lines[1:]]


def read_log():
    recs = []
    if not os.path.exists(P("runs/log.jsonl")):
        return recs
    with open(P("runs/log.jsonl"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def latest_attempt(recs, step, base):
    """The latest logged attempt of job `base`: the id itself, or base-r2, base-r3. Returns (id_used, record) or (None, None)."""
    best = (None, None)
    for suffix in ("", "-r2", "-r3"):
        for r in recs:
            if r["step"] == step and r["id"] == base + suffix:
                best = (base + suffix, r)
    return best


def sfx_of(id_used, base):
    return id_used[len(base):]


def read_tsv_rows(path):
    if not os.path.exists(P(path)):
        return []
    return read_tsv(path)


def accepted_names():
    names = set()
    if os.path.exists(P(RUNS + "/accepted.tsv")):
        with open(P(RUNS + "/accepted.tsv"), encoding="utf-8") as f:
            for l in f:
                l = l.strip()
                if l and not l.startswith("#"):
                    names.add(l.split("\t")[0].split()[0])
    return names


def status_rows():
    rows = {}
    for l in (open(P(RUNS + "/status.tsv"), encoding="utf-8").read().split("\n") if os.path.exists(P(RUNS + "/status.tsv")) else []):
        c = l.split("\t")
        if len(c) >= 2 and c[0] != "split":
            rows[c[0]] = c
    return rows


def gate_problem(split):
    """None if the split may start; else the one line saying why."""
    if os.path.exists(P(RUNS + "/HOLD")):
        return "refused: %s/HOLD exists (the manager's hold)" % RUNS
    acc = accepted_names()
    st = status_rows()
    for e in SPLITS[:SPLITS.index(split)]:
        if e not in st or not st[e][1].startswith("DONE"):
            return "refused: the earlier split %s is not DONE (status: %s)" % (e, st[e][1] if e in st else "not started")
        if e not in acc:
            return "refused: the earlier split %s has no line in %s/accepted.tsv (the manager writes it)" % (e, RUNS)
        kept = Pipe(e).kept_ids()
        if kept:
            return "refused: the earlier split %s keeps %d file(s) until accepted: %s (when the manager has accepted them, run %s again: it deletes them)" % (e, len(kept), ", ".join(kept), e)
    return None


class Pipe:
    def __init__(self, split, test=None):
        self.split = split
        self.test = test
        self.test_root = os.environ.get(TESTENV + "TEST_ROOT")
        tag = os.environ.get(ENV + "TEST_TAG", "")
        self.tag = tag
        if test:
            self.jp = "%s-%s%s" % (TEST_PREFIX, test, tag)
            self.rundir = "%s/pipeline-test/%s%s" % (RUNS, test, tag)
        elif self.test_root:
            self.jp = "%s-%s%s" % (TEST_PREFIX, split, tag)
            self.rundir = "%s/pipeline-test/%s%s" % (RUNS, split, tag)
        else:
            self.jp = split
            self.rundir = "%s/%s" % (RUNS, split)
        self.sandbox = bool(test or self.test_root)
        # the pilot rules (pause after the first file, stop at once if it fails) apply to the first split before "<first split>-pilot" is accepted;
        # test mode "pilot" plays that role
        self.pilot = (split == SPLITS[0] and not self.sandbox) or test == "pilot"
        self.lockdir = "%s/pipeline-test/.lock" % RUNS if self.sandbox else "%s/.lock" % RUNS
        self.cap = float(os.environ.get(ENV + "CAP_MIN", "840"))
        self.retry = os.environ.get(ENV + "RETRY", "0") == "1"
        self.floor = float(os.environ.get(ENV + "FLOOR_GIB", "10"))
        self.nudge_targets = [t.strip() for t in os.environ.get(ENV + "NUDGE", NUDGE_DEFAULT).split(",") if t.strip()]
        self.file_targets = [t.strip() for t in os.environ.get(ENV + "FILE_NUDGE", FILE_NUDGE_DEFAULT).split(",") if t.strip()]
        self.poll_s = float(os.environ.get(ENV + "POLL_S", "300"))
        self.wait_h = float(os.environ.get(ENV + "WAIT_H", "24"))
        # test-only settings, read only in a sandbox run: made-up files without a download, and another bridge script
        self.fake = bool(self.test_root and os.environ.get(TESTENV + "FAKE") == "1")
        self.send_path = os.environ.get(TESTENV + "SEND") if (self.test_root or test) and os.environ.get(TESTENV + "SEND") else SEND
        self.hold_path = ("%s/pipeline-test/HOLD" % RUNS) if (self.test_root or test) else ("%s/HOLD" % RUNS)
        self.tty = sys.stdout.isatty()
        self.interrupted = False
        self.sigint_time = None
        self.child = None
        self.child_forward = True
        self.jobs_run = []
        self.failed_analysis = []
        self.notes = []
        self.status = None
        self.lock = None
        self.nudge_result = "not sent"
        self.traceback_text = None
        self.deleted = []
        self.file_rows = []       # (id, outcome, failed step, output bytes) of this run
        self._report = None

    # ---------- the split's list and places
    def list_rows(self):
        if self.test:
            return [{"recid": "0", "key": "T%d.root" % i, "size": "1000", "adler32": "00000000", "url": "-"} for i in range(1, 6)]
        if self.test_root:
            return read_tsv(os.path.join(self.test_root, "files-%s.tsv" % self.split))
        return read_tsv("%s/splits/files-%s.tsv" % (RUNS, self.split))

    def dl_dir(self, fid):
        base = os.path.join(self.test_root, "downloads") if self.test_root else "downloads"
        return "%s/%s-%s/%s" % (base, ST.lower(), self.split, fid)

    def jid(self, fid, step):
        return "%s-%s-%s" % (self.jp, fid, step)

    # ---------- screen
    def width(self):
        if self.tty:
            return max(20, min(MAXW, shutil.get_terminal_size((100, 24)).columns - 1))
        return MAXW

    def out(self, s):
        print(s[:self.width()], flush=True)

    def compute_min(self):
        pre = self.jp + "-"
        return sum(r.get("wall_s", 0.0) for r in read_log() if r["step"] == ST and r["id"].startswith(pre)) / 60.0

    def jline(self, stage, jid, what):
        self.out("%s %s %s | compute %.1f of %g min" % (stage, jid, what, self.compute_min(), self.cap))

    def on_sigint(self, signum, frame):
        self.interrupted = True
        self.sigint_time = time.time()
        if self.child is not None and self.child_forward and self.child.poll() is None:
            try:
                os.kill(self.child.pid, signal.SIGINT)
            except OSError:
                pass

    # ---------- lock
    def take_lock(self):
        d = P(self.lockdir)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        try:
            os.mkdir(d)
        except FileExistsError:
            pid = None
            try:
                with open(os.path.join(d, "pid")) as f:
                    pid = int(f.read().strip())
            except (OSError, ValueError):
                pass
            alive = False
            if pid:
                try:
                    os.kill(pid, 0)
                    alive = True
                except ProcessLookupError:
                    alive = False
                except PermissionError:
                    alive = True
            if alive:
                print("refused: another copy of the script is running (process %d); lock %s" % (pid, self.lockdir))
                sys.exit(3)
            print("the lock %s was left by a process (%s) that is no longer running: taken over" % (self.lockdir, pid))
        with open(os.path.join(d, "pid"), "w") as f:
            f.write("%d\n" % os.getpid())
        self.lock = d

    def release_lock(self):
        if self.lock:
            try:
                os.remove(os.path.join(self.lock, "pid"))
                os.rmdir(self.lock)
            except OSError:
                pass
            self.lock = None

    # ---------- preflight
    def pins_ok(self):
        bad = []
        if not os.path.exists(P(PINS)):
            return ["pins file %s is missing" % PINS]
        with open(P(PINS)) as f:
            for line in f:
                if not line.strip():
                    continue
                h, path = line.split(None, 1)
                path = path.strip()
                try:
                    if sha256(path) != h:
                        bad.append("%s differs from its pin" % path)
                except OSError:
                    bad.append("%s is missing" % path)
        return bad

    def preflight(self):
        probs = self.pins_ok() if (not self.test or os.path.exists(P(PINS))) else []
        if PREFLIGHT_IMPORTS:
            r = subprocess.run(PY + ["-c", PREFLIGHT_IMPORTS], capture_output=True, text=True, cwd=ROOT)
            if r.returncode != 0:
                probs.append("python imports failed: " + r.stderr.strip()[-200:])
        return probs

    # ---------- jobs
    def run_logger(self, stage, jid, limit, cmd):
        argv = LOGGER + ["--step", ST, "--by", BY, "--id", jid, "--limit", str(limit), "--mem", str(JOB_MEM_MB)]
        if limit > 1800:
            argv += ["--long-ok", LONG_OK]
        argv += ["--"] + cmd
        self.jline(stage, jid, "start (limit %d s)" % limit)
        t0 = time.time()
        self.child = subprocess.Popen(argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        step = 5.0 if self.tty else 60.0
        nxt = t0 + step
        while self.child.poll() is None:
            time.sleep(0.2)
            if time.time() >= nxt:
                nxt += step
                w = self.width()
                line = ("%s %s running %d s | compute %.1f of %g min" % (stage, jid, time.time() - t0, self.compute_min(), self.cap))[:w]
                if self.tty:
                    sys.stdout.write("\r" + line.ljust(w))
                    sys.stdout.flush()
                else:
                    print(line, flush=True)
        txt = self.child.stdout.read()
        self.child = None
        if self.tty:
            sys.stdout.write("\r" + " " * self.width() + "\r")
        rec = None
        for r in read_log():
            if r["step"] == ST and r["id"] == jid:
                rec = r
        if rec is None:
            self.jline(stage, jid, "NO LOG LINE (logger said: %s)" % txt.strip().replace("\n", " ")[:40])
            outcome, wall, peak = "no log line", time.time() - t0, 0.0
        else:
            outcome, wall, peak = rec["outcome"], rec["wall_s"], rec.get("peak_rss_mb", 0.0)
            self.jline(stage, jid, "%s %.1f s" % (outcome, wall))
        self.jobs_run.append((jid, outcome, wall, peak, stage))
        if self.interrupted:
            raise Interrupted()
        return outcome

    def attempts(self, base):
        recs = read_log()
        out = []
        for sfx in ("", "-r2", "-r3"):
            jid = base + sfx
            logged = [r for r in recs if r["step"] == ST and r["id"] == jid]
            if logged:
                out.append((jid, logged[-1]))
            elif os.path.exists(P("%s/%s.out" % (RUNS, jid))):
                out.append((jid, None))
        return out

    def execute(self, stage, base, limit, cmdf, prepare=None):
        """Returns (state, id_used, sfx); state 'ok', 'skipped', 'failed' or 'nocap'. An interrupted attempt is not a failure."""
        while True:
            if self.interrupted:
                raise Interrupted()
            att = self.attempts(base)
            id_used, rec = att[-1] if att else (None, None)
            if rec and rec["outcome"] == "exit 0":
                self.jobs_run.append((id_used, "exit 0 (skipped: done)", rec["wall_s"], rec.get("peak_rss_mb", 0.0), stage))
                self.out("%s %s already done (exit 0), skipped" % (stage, id_used))
                return "skipped", id_used, sfx_of(id_used, base)
            if att:
                was_interrupted = rec is None or rec["outcome"] == "interrupted"
                if not (was_interrupted or self.retry):
                    return "failed", id_used, sfx_of(id_used, base)
                nxt = {base: "-r2", base + "-r2": "-r3"}.get(id_used)
                if nxt is None:
                    return "failed", id_used, sfx_of(id_used, base)
                sfx = nxt
                if was_interrupted:
                    self.out("%s %s was interrupted: running again as %s%s" % (stage, id_used, base, sfx))
            else:
                sfx = ""
            jid = base + sfx
            if self.compute_min() + limit / 60.0 > self.cap:
                return "nocap", jid, sfx
            if prepare and sfx:
                prepare(sfx)
            outcome = self.run_logger(stage, jid, limit, cmdf(sfx))
            if outcome == "exit 0":
                return "ok", jid, sfx
            if not self.retry and outcome != "interrupted":
                return "failed", jid, sfx

    def need(self, stage, base, limit, cmdf, **kw):
        """A job that must exit 0. A failed job fails the file (FileFail); the cap stops the split."""
        st, jid, sfx = self.execute(stage, base, limit, cmdf, **kw)
        if st == "nocap":
            raise Stop("STOPPED at %s (compute cap)" % jid)
        if st == "failed":
            raise FileFail(base.rsplit("-", 1)[1])
        return jid, sfx

    # ---------- files.tsv
    def files_path(self):
        return "%s/files.tsv" % self.rundir

    def file_states(self):
        st = {}
        for r in read_tsv_rows(self.files_path()):
            st[r["id"]] = (r["status"], r.get("step", ""))
        return st

    def record_file(self, fid, status, step=""):
        os.makedirs(P(self.rundir), exist_ok=True)
        new = not os.path.exists(P(self.files_path()))
        with open(P(self.files_path()), "a", encoding="utf-8") as g:
            if new:
                g.write("id\tstatus\tstep\tutc\n")
            g.write("%s\t%s\t%s\t%s\n" % (fid, status, step, now()))

    # ---------- keeping, acceptance, hold, bridge
    def q(self, path):
        """A repository path; in a run with the test root the per-file outputs and the fake files live under the test folder."""
        return os.path.join(self.test_root, path) if self.test_root else path

    def fields(self, r):
        key = r["key"]
        return {"fid": key[:8], "key": key, "stem": key.rsplit(".", 1)[0], "recid": r["recid"], "size": r["size"], "adler32": r["adler32"]}

    def temp_paths(self, r):
        f = self.fields(r)
        return [self.q(t.format(**f)) for t in TEMP_OUTPUTS]

    def kept_paths(self, r):
        f = self.fields(r)
        return [self.q(t.format(**f)) for t in KEPT_OUTPUTS]

    def paths_of(self, r):
        """(source, download folder, temporary outputs) of a file of the list."""
        key = r["key"]
        dest = self.dl_dir(key[:8])
        return ("%s/%s/%s" % (dest, r["recid"], key), dest, self.temp_paths(r))

    def is_kept(self, r):
        src, _, temps = self.paths_of(r)
        return os.path.exists(P(src)) or bool(glob.glob(P(src) + ".part*")) or any(os.path.exists(P(t)) for t in temps)

    def kept_ids(self, rows=None):
        """The DONE files whose source, .part file or temporary output is still on disk."""
        rows = rows or self.list_rows()
        st = self.file_states()
        return [r["key"][:8] for r in rows if st.get(r["key"][:8], ("", ""))[0] == "DONE" and self.is_kept(r)]

    def accepted_files(self, rows=None):
        """The ids of runs/<ST>/<split>/accepted-files.tsv (the manager writes it) that are files of the split's list."""
        rows = rows or self.list_rows()
        ids = {r["key"][:8] for r in rows}
        got = set()
        path = P("%s/accepted-files.tsv" % self.rundir)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for l in f.read().split("\n"):
                    l = l.strip()
                    if l and not l.startswith("#"):
                        c = l.split("\t")[0].strip()
                        if len(c) == 8 and c in ids:
                            got.add(c)
        return got

    def check_hold(self):
        if os.path.exists(P(self.hold_path)):
            raise Stop("STOPPED (HOLD)")

    def poll_sleep(self, secs):
        end = time.time() + secs
        while True:
            if self.interrupted:
                raise Interrupted()
            left = end - time.time()
            if left <= 0:
                return
            time.sleep(min(0.2, left))

    def bridge_send(self, kind, fid, targets, msg):
        """Send msg to the first target that takes it (timeout 180 s, an exception means not delivered and never raises). Every attempt is appended to
        <run folder>/nudges.tsv. Returns (delivered, result text)."""
        if self.sandbox and kind != "end":
            msg = msg.replace(FILE_TAIL, TEST_TAIL)
        result = "no target"
        for t in targets:
            try:
                r = subprocess.run([self.send_path, t, msg], capture_output=True, text=True, timeout=SEND_TIMEOUT)
                ok = r.returncode == 0
                if ok:
                    res = "delivered: %s" % (r.stdout.strip() or "ok")
                    result = "delivered to '%s': %s" % (t, (r.stdout.strip() or "ok"))
                else:
                    res = "failed (exit %d): %s" % (r.returncode, (r.stdout + r.stderr).strip()[:100])
                    result = "target '%s' failed (exit %d): %s" % (t, r.returncode, (r.stdout + r.stderr).strip()[:100])
            except (OSError, subprocess.TimeoutExpired) as e:
                ok = False
                res = "failed (%s: %s)" % (type(e).__name__, str(e)[:100])
                result = "target '%s' failed (%s: %s)" % (t, type(e).__name__, str(e)[:100])
            os.makedirs(P(self.rundir), exist_ok=True)
            npath = P("%s/nudges.tsv" % self.rundir)
            new = not os.path.exists(npath)
            with open(npath, "a", encoding="utf-8") as g:
                if new:
                    g.write("utc\tkind\tid\ttarget\tresult\n")
                g.write("%s\t%s\t%s\t%s\t%s\n" % (now(), kind, fid, t, res.replace("\t", " ").replace("\n", " ")))
            if ok:
                return True, result
        return False, result

    def file_report(self, fid, state, step=None):
        """One line to the manager after each file of this run."""
        rows = self.list_rows()
        st = self.file_states()
        p = sum(1 for r in rows if st.get(r["key"][:8], ("", ""))[0] == "DONE")
        kept = ", ".join(self.kept_ids(rows)) or "none"
        fw = ", ".join(self.failed_waiting()) or "none"
        head = "[PIPELINE %s %s file] " % (ST.lower(), self.split)
        if state == "DONE":
            msg = "%s%s DONE (%d of %d passed); kept until accepted: %s; failed waiting: %s; %s" % (head, fid, p, len(rows), kept, fw, FILE_TAIL)
        else:
            msg = "%s%s FAILED at %s, its source stays; kept until accepted: %s; failed waiting: %s; %s" % (head, fid, step, kept, fw, FILE_TAIL)
        ok, res = self.bridge_send("file-" + state.lower(), fid, self.file_targets, msg)
        self.out("file report %s: %s" % (state, res[:60]))
        return ok

    def deletion_pass(self, rows=None):
        """Delete, in the list's order, each DONE, kept and accepted file. Never under the hold."""
        self.check_hold()
        rows = rows or self.list_rows()
        acc = self.accepted_files(rows)
        st = self.file_states()
        for r in rows:
            fid = r["key"][:8]
            if fid not in acc or st.get(fid, ("", ""))[0] != "DONE" or not self.is_kept(r):
                continue
            src, dest, temps = self.paths_of(r)
            sums = "%s/%s/SHA256SUMS" % (dest, r["recid"])
            if not os.path.exists(P(sums)):
                self.notes.append("%s: accepted, but %s is missing: nothing deleted" % (fid, sums))
                continue
            self.check_hold()
            self.delete_file(fid, src, dest, temps, sums)

    def wait_for_space(self, fid, size):
        """The space check before a download, with a wait for the manager's acceptances (they free the space)."""
        need = size / float(1 << 30) + self.floor
        if self.free_gib() >= need:
            return
        ids = ", ".join(self.kept_ids()) or "none"
        msg = "[PIPELINE %s %s file] waiting for disk space before %s (free %.1f GiB, need %.1f GiB); kept until accepted: %s; %s" % (
            ST.lower(), self.split, fid, self.free_gib(), need, ids, FILE_TAIL)
        ok, res = self.bridge_send("disk-wait", fid, self.file_targets, msg)
        deadline = time.time() + self.wait_h * 3600.0
        while True:
            self.out("waiting for disk space before %s: free %.1f GiB, need %.1f GiB; kept: %s" % (fid, self.free_gib(), need, ", ".join(self.kept_ids()) or "none"))
            if time.time() >= deadline:
                raise Stop("STOPPED at %s (disk; kept until accepted: %s)" % (fid, ", ".join(self.kept_ids()) or "none"))
            self.poll_sleep(min(self.poll_s, max(0.0, deadline - time.time())))
            self.check_hold()
            self.deletion_pass()
            if self.free_gib() >= need:
                return

    def end_wait(self):
        """After the facts stage, while a DONE file is kept, poll (hold, deletion pass) for up to ENV+WAIT_H hours."""
        deadline = time.time() + self.wait_h * 3600.0
        while True:
            self.check_hold()
            self.deletion_pass()
            k = self.kept_ids()
            if not k:
                return
            if time.time() >= deadline:
                return
            self.out("end of the split: waiting for the manager's acceptance of %s" % ", ".join(k))
            self.poll_sleep(min(self.poll_s, max(0.0, deadline - time.time())))

    def step_keep(self, fid):
        """The keep step: the file is DONE; nothing is deleted (the deletion comes in a deletion pass, after the manager accepted the file)."""
        self.record_file(fid, "DONE")

    # ---------- one file
    def free_gib(self):
        probe = P("downloads") if os.path.isdir(P("downloads")) else ROOT
        return shutil.disk_usage(probe).free / float(1 << 30)

    def download(self, fid, r, lst, dest):
        self.child_forward = False
        self.child = subprocess.Popen([DOWNLOADER, lst, dest], cwd=ROOT)
        forwarded = False
        while self.child.poll() is None:
            time.sleep(0.2)
            if self.interrupted and not forwarded and time.time() - self.sigint_time > 3.0:
                forwarded = True
                try:
                    os.kill(self.child.pid, signal.SIGINT)
                except OSError:
                    pass
        rc = self.child.returncode
        self.child = None
        self.child_forward = True
        if self.interrupted or rc == 130:
            raise Interrupted()
        return rc

    def do_file(self, r):
        fid, key = r["key"][:8], r["key"]
        recid = r["recid"]
        size = int(r["size"])
        rd = "%s/%s" % (self.rundir, fid)
        os.makedirs(P(self.rundir + "/lists"), exist_ok=True)
        os.makedirs(P(rd), exist_ok=True)
        lst = "%s/lists/%s.tsv" % (self.rundir, fid)
        dest = self.dl_dir(fid)
        src = "%s/%s/%s" % (dest, recid, key)
        J = lambda step: self.jid(fid, step)
        if JOBS:
            last_att = self.attempts(J(JOBS[-1][1]))
            if last_att and last_att[-1][1] and last_att[-1][1]["outcome"] == "exit 0":
                # every job of this file passed in an earlier run, which was cut off inside the keep step: keep again (no download)
                self.out("file %s: all jobs passed earlier; %s again (keep)" % (fid, KEEP_STEP))
                self.step_keep(fid)
                return
        # space
        self.wait_for_space(fid, size)
        # download
        with open(P(lst), "w", encoding="utf-8") as g:
            g.write("recid\tkey\tsize\tadler32\turl\n%s\t%s\t%s\t%s\t%s\n" % (recid, key, r["size"], r["adler32"], r["url"]))
        self.out("download %s (%s bytes) into %s" % (fid, r["size"], dest))
        rc = self.download(fid, r, lst, dest)
        if rc == 3:
            raise Stop("STOPPED at %s (download exit 3: disk space, or another download uses the folder)" % fid)
        if rc == 2:
            raise Stop("FAILED: download exit 2 at %s (wrong usage or a folder that holds something else)" % fid)
        if rc != 0:
            raise FileFail("download")
        # the jobs, in order, each through the logger
        f = dict(self.fields(r), list=lst, dest=dest, src=src, rd=rd)
        for stage, step, limit, cmd, outputs in JOBS:
            outs = [self.q(o.format(sfx="", **f)) for o in outputs]

            def prep(sfx, outs=outs):
                for pth in outs:
                    if os.path.exists(P(pth)):
                        n = 1
                        while os.path.exists(P("%s.failed-%d" % (pth, n))):
                            n += 1
                        os.rename(P(pth), P("%s.failed-%d" % (pth, n)))

            self.need(stage, J(step), limit, lambda s, cmd=cmd: [a.format(sfx=s, **f) for a in cmd], prepare=prep if outs else None)
        # keep (the deletion comes later, in a deletion pass, after the manager accepted the file)
        self.step_keep(fid)

    def delete_file(self, fid, src, dest, temps, sums):
        """Each path by its full name; each logged before it is removed."""
        allowed = [P(dest) + os.sep] + [P(os.path.dirname(t)) + os.sep for t in temps]
        known = {}
        with open(P(sums), encoding="utf-8") as f:
            for l in f.read().split("\n"):
                if l.strip():
                    h, _, n = l.partition("  ")
                    if n == os.path.basename(src):
                        known[P(src)] = h
        paths = [src] + sorted(os.path.relpath(x, ROOT) for x in glob.glob(P(src) + ".part*")) + temps
        dpath = "%s/deletions.tsv" % self.rundir
        os.makedirs(P(self.rundir), exist_ok=True)
        new = not os.path.exists(P(dpath))
        for pth in paths:
            full = P(pth)
            if not any(os.path.realpath(full).startswith(os.path.realpath(a.rstrip(os.sep)) + os.sep) for a in allowed):
                raise Stop("FAILED: internal error (refusing to delete %s: outside the allowed folders)" % pth)
            if not os.path.exists(full):
                continue
            size = os.path.getsize(full)
            h = known.get(full) or sha256(pth)
            with open(P(dpath), "a", encoding="utf-8") as g:
                if new:
                    g.write("path\tbytes\tsha256\tutc\n")
                    new = False
                g.write("%s\t%d\t%s\t%s\n" % (pth, size, h, now()))
                g.flush()
                os.fsync(g.fileno())
            os.remove(full)
            self.deleted.append((pth, size))
            self.out("deleted %s (%d bytes)" % (pth, size))

    # ---------- the split
    def failed_waiting(self, except_id=None):
        return [i for i, (s, _) in self.file_states().items() if s.startswith("FAILED") and i != except_id]

    def process_files(self):
        rows = self.list_rows()
        for r in rows:
            fid = r["key"][:8]
            states = self.file_states()
            if states.get(fid, ("", ""))[0] == "DONE":
                self.file_rows.append((fid, "DONE (earlier run)", "", ""))
                continue
            if self.pilot and any(s == "DONE" for s, _ in states.values()) and PILOT_NAME not in accepted_names():
                raise Stop("PAUSED after the pilot file")
            if len(self.failed_waiting(fid)) >= 3:
                raise Stop("STOPPED, 3 failed files waiting")
            if self.interrupted:
                raise Interrupted()
            self.check_hold()
            self.deletion_pass(rows)
            self.out("file %s (%d of %d)" % (fid, rows.index(r) + 1, len(rows)))
            try:
                self.do_test_file(r) if self.test else (self.do_fake_file(r) if self.fake else self.do_file(r))
                self.file_rows.append((fid, "DONE", "", ""))
                self.file_report(fid, "DONE")
            except FileFail as e:
                self.record_file(fid, "FAILED " + e.step, e.step)
                self.file_rows.append((fid, "FAILED", e.step, ""))
                self.out("file %s FAILED at %s: its source and %s stay" % (fid, e.step, KEPT_WORD))
                self.file_report(fid, "FAILED", e.step)
                if self.pilot and PILOT_NAME not in accepted_names():
                    # before the pilot is accepted, a failed file stops the split at once
                    raise Stop("STOPPED at the pilot (%s failed at %s)" % (fid, e.step))
            states = self.file_states()
            if self.pilot and states.get(fid, ("", ""))[0] == "DONE" and sum(1 for s, _ in states.values() if s == "DONE") == 1 \
                    and PILOT_NAME not in accepted_names():
                raise Stop("PAUSED after the pilot file")

    def do_test_file(self, r):
        """Test mode: made-up steps."""
        fid = r["key"][:8]
        mode = self.test
        if self.floor > 1e6 or self.free_gib() < self.floor:
            raise Stop("STOPPED at %s (disk)" % fid)
        if mode == "error" and fid.startswith("T1"):
            raise ValueError("%s-error: the made-up step raises on purpose" % TEST_PREFIX)
        for step in TEST_STEPS:
            if mode == "sleep":
                cmd, lim = ["/bin/sleep", "30"], 60
            elif (mode in ("fail", "pilot") and fid[:2] in ("T1", "T3", "T4") and step == "skim1") or (mode == "partial" and fid[:2] == "T2" and step == "skim1"):
                cmd, lim = ["/bin/sh", "-c", "exit 1"], 10
            else:
                cmd, lim = ["/bin/sleep", "3" if mode == "cap" else "1"], 10
            self.need("T", self.jid(fid, step), lim, lambda s, cmd=cmd: cmd)
        self.record_file(fid, "DONE")

    def do_fake_file(self, r):
        """Test only: made-up steps through the logger on made-up files inside the test folder: a dummy source with its SHA256SUMS, a dummy .part0,
        dummy temporary and kept outputs. The keep, the file report, the deletion pass and the waits are the real code."""
        fid, key = r["key"][:8], r["key"]
        src, dest, temps = self.paths_of(r)
        self.wait_for_space(fid, int(r["size"]))
        for pth, text in [(src, "dummy source of %s\n" % fid), (src + ".part0", "dummy part\n")] + [(t, "dummy %s of %s\n" % (KEPT_WORD, fid)) for t in temps] \
                + [(k, "dummy kept output of %s\n" % fid) for k in self.kept_paths(r)]:
            os.makedirs(os.path.dirname(P(pth)), exist_ok=True)
            with open(P(pth), "w") as g:
                g.write(text)
        with open(P("%s/%s/SHA256SUMS" % (dest, r["recid"])), "w", encoding="utf-8") as g:
            g.write("%s  %s\n" % (sha256(src), key))
        os.makedirs(P(self.rundir), exist_ok=True)
        fail = os.environ.get(TESTENV + "FAKE_FAIL", "").split(",")
        for step in FAKE_STEPS:
            cmd = ["/bin/sh", "-c", "exit 1"] if (fid in fail and step == FAKE_STEPS[-1]) else ["/bin/sleep", "1"]
            self.need("T", self.jid(fid, step), 10, lambda s_, cmd=cmd: cmd)
        self.step_keep(fid)

    # ---------- the end of the split
    def done_outputs(self, split=None):
        p = self if split is None else Pipe(split)
        st = p.file_states()
        out = []
        for r in p.list_rows():
            if st.get(r["key"][:8], ("", ""))[0] == "DONE":
                out += p.kept_paths(r)
        return out

    def all_done_outputs(self):
        out = []
        for sp in SPLITS:
            if os.path.exists(P("%s/splits/files-%s.tsv" % (RUNS, sp))):
                out += self.done_outputs(sp)
        return out

    def end_cmd(self, cmd, sfx, dep_sfx=""):
        argv = []
        for a in cmd:
            if a == "{done_outputs}":
                argv += self.done_outputs()
            elif a == "{all_done_outputs}":
                argv += self.all_done_outputs()
            else:
                argv.append(a.format(rundir=self.rundir, split=self.split, sfx=sfx, dep_sfx=dep_sfx))
        return argv

    def stage_analysis(self):
        if not END_JOBS:
            return
        if not any(s == "DONE" for s, _ in self.file_states().values()):
            raise Stop("FAILED at analysis (no file of the split passed)")
        for step, limit, cmd, depends in END_JOBS:
            base = "%s-%s" % (self.jp, step)
            dep_sfx = ""
            if depends:
                dep = "%s-%s" % (self.jp, depends)
                id_used, rec = latest_attempt(read_log(), ST, dep)
                if not rec or rec["outcome"] != "exit 0":
                    self.jobs_run.append((base, "not run (%s failed or did not run)" % dep, 0.0, 0.0, "S9"))
                    self.out("S9 %s passed over (%s did not exit 0)" % (base, dep))
                    continue
                dep_sfx = sfx_of(id_used, dep)
            st, jid, sfx = self.execute("S9", base, limit, lambda s, cmd=cmd, dep_sfx=dep_sfx: self.end_cmd(cmd, s, dep_sfx))
            if st == "nocap":
                self.jobs_run.append((base, "not run (compute cap)", 0.0, 0.0, "S9"))
                self.failed_analysis.append(base + " (not run: compute cap)")
            elif st == "failed":
                self.failed_analysis.append(jid)

    def stage_facts(self):
        if FACTS_JOB is None:
            return False
        base = self.jp + "-facts"
        limit, cmd = FACTS_JOB
        st, jid, sfx = self.execute("S8", base, limit, lambda s: self.end_cmd(cmd, s))
        if st == "nocap":
            self.notes.append("facts not run: compute cap")
            raise Stop("STOPPED at %s (compute cap)" % jid)
        if st == "failed":
            self.notes.append("facts failed: %s" % jid)
            raise Stop("FAILED at %s" % jid)
        return True

    def copy_records(self):
        """At the end of the split: download.log and fetch-log.tsv of every file's download folder go to runs/<ST>/<split>/download-records/<id>/, compared (filecmp)."""
        import filecmp
        base = os.path.dirname(P(self.dl_dir("x")))
        n = bad = 0
        if os.path.isdir(base):
            for fid in sorted(os.listdir(base)):
                for name in ("download.log", "fetch-log.tsv"):
                    src = os.path.join(base, fid, name)
                    if os.path.exists(src):
                        dst = os.path.join(P(self.rundir), "download-records", fid, name)
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        if not os.path.exists(dst) or not filecmp.cmp(src, dst, shallow=False):
                            shutil.copyfile(src, dst)
                        n += 1
                        if not filecmp.cmp(src, dst, shallow=False):
                            bad += 1
        self.notes.append("download records: %d file(s) copied to %s/download-records/ and compared; %d differ" % (n, self.rundir, bad))

    # ---------- report and nudge
    def report_name(self):
        n = 1
        while True:
            fn = "report%s.md" % ("" if n == 1 else "-%d" % n)
            if not os.path.exists(P("%s/%s" % (self.rundir, fn))):
                return fn
            n += 1

    def output_bytes(self, r):
        paths = [P(k) for k in self.kept_paths(r)]
        return str(sum(os.path.getsize(k) for k in paths if os.path.exists(k))) if paths else ""

    def write_report(self, facts_made):
        os.makedirs(P(self.rundir), exist_ok=True)
        fn = self.report_name()
        rows = self.list_rows()
        states = self.file_states()
        lines = ["# Split script, split %s: report" % self.split, "", "Written %s by tools/%s." % (now(), os.path.basename(__file__)), "", "**Status: %s**" % self.status, "",
                 "## Files", "", "| id | outcome | failed step | %s bytes | source |" % OUTPUT_WORD, "|---|---|---|---|---|"]
        kept = self.kept_ids(rows)
        for r in rows:
            fid = r["key"][:8]
            s, step = states.get(fid, ("not started", ""))
            src_state = ("kept" if fid in kept else "deleted") if s == "DONE" else "-"
            lines.append("| %s | %s | %s | %s | %s |" % (fid, s, step, self.output_bytes(r) if s == "DONE" else "", src_state))
        lines += ["", "Files DONE: %d of %d; failed (sources kept): %d; kept until accepted: %d." % (sum(1 for r in rows if states.get(r["key"][:8], ("", ""))[0] == "DONE"), len(rows),
                                                                                                    len(self.failed_waiting()), len(kept))]
        lines += ["", "## Jobs of this run", "", "| id | outcome | seconds | peak MB | stage |", "|---|---|---|---|---|"]
        for jid, outc, wall, peak, stg in self.jobs_run:
            lines.append("| %s | %s | %.1f | %.1f | %s |" % (jid, outc, wall, peak, stg))
        lines += ["", "Compute (the sum of `wall_s` of the step-%s lines whose id starts `%s-`): %.2f of %g min." % (ST, self.jp, self.compute_min(), self.cap)]
        dels = read_tsv_rows("%s/deletions.tsv" % self.rundir)
        lines += ["", "## Deletions", "", "%d deletion(s) logged in %s/deletions.tsv (%d in this run)." % (len(dels), self.rundir, len(self.deleted))]
        for pth, sz in self.deleted:
            lines.append("- this run: `%s` (%d bytes)" % (pth, sz))
        if self.traceback_text:
            lines += ["", "## Internal error: traceback", "", "```"] + self.traceback_text.rstrip("\n").split("\n") + ["```"]
        if self.failed_analysis:
            lines += ["", "## Analysis jobs that failed or did not run", ""] + ["- " + x for x in self.failed_analysis]
        if self.notes:
            lines += ["", "## Notes", ""] + ["- " + x for x in self.notes]
        lines += ["", "## Paths", "", "- facts: %s" % ("%s/facts.md" % self.rundir if facts_made else "not made"),
                  "- analysis outputs: %s" % (("%s/%s" % (self.rundir, ", ".join(e[0] for e in END_JOBS))) if END_JOBS else "none"),
                  "- per-file outputs: %s/<id>/" % self.rundir, "- the file states: %s" % self.files_path(),
                  "- job outputs: %s/<job id>.out and .err; the log: runs/log.jsonl" % RUNS, "", "## Nudge", "", "{{NUDGE}}"]
        self._report = (fn, lines)
        with open(P("%s/%s" % (self.rundir, fn)), "w", encoding="utf-8") as g:
            g.write("\n".join(lines) + "\n")
        return fn

    def finish_report(self, fn):
        _, lines = self._report
        with open(P("%s/%s" % (self.rundir, fn)), "w", encoding="utf-8") as g:
            g.write("\n".join(lines).replace("{{NUDGE}}", self.nudge_result) + "\n")

    def update_status_tsv(self):
        if self.sandbox:
            return
        rows = status_rows()
        files = read_tsv_rows(self.files_path())
        st = {}
        for r in files:
            st[r["id"]] = r["status"]
        total = len(self.list_rows())
        rows[self.split] = [self.split, self.status, "%d/%d" % (sum(1 for s in st.values() if s == "DONE"), total), now()]
        with open(P(RUNS + "/status.tsv"), "w", encoding="utf-8") as g:
            g.write("split\tstatus\tfiles_done_of_total\tutc\n")
            for sp in SPLITS:
                if sp in rows:
                    g.write("\t".join(rows[sp]) + "\n")

    def nudge(self, fn, facts_made):
        kind = "%s %s" % (ST.lower(), ("test " + self.test) if self.test else self.split)
        msg = ("[PIPELINE %s] %s; report %s/%s; facts %s; compute %.1f of %g min; %s"
               % (kind, self.status, self.rundir, fn, ("%s/facts.md" % self.rundir) if facts_made else "not made", self.compute_min(), self.cap, NUDGE_TAIL))
        if self.sandbox:
            msg = msg.replace(NUDGE_TAIL, SANDBOX_NUDGE_TAIL)
        ok, res = self.bridge_send("end", "-", self.nudge_targets, msg)
        self.nudge_result = res
        if ok:
            self.out("nudge: %s" % res[:60])
            return True
        print("NUDGE NOT DELIVERED to any target; pass this on yourself:\n" + msg, flush=True)
        self.nudge_result = "not delivered to any of %s; message: %s" % (self.nudge_targets, msg)
        return False

    # ---------- the run
    def run(self, dry=False):
        signal.signal(signal.SIGINT, self.on_sigint)
        signal.signal(signal.SIGTERM, self.on_sigint)
        if not self.sandbox:
            g = gate_problem(self.split)
            if g:
                print(g)
                return 4
        if dry:
            lst = "%s/splits/files-%s.tsv" % (RUNS, self.split) if not self.test_root else os.path.join(self.test_root, "files-%s.tsv" % self.split)
            self.child = None
            return subprocess.run([DOWNLOADER, lst, self.dl_dir("dry")], cwd=ROOT).returncode
        self.take_lock()
        try:
            return self._run()
        except Interrupted:
            print("interrupted: the job's group was ended; a rerun resumes", flush=True)
            return 130
        finally:
            self.release_lock()

    def _run(self):
        probs = self.preflight()
        if probs:
            for x in probs:
                print("PREFLIGHT: " + x)
            return 2
        facts_made = False
        try:
            self.process_files()
            if not (self.test or self.fake):
                self.stage_analysis()
                facts_made = self.stage_facts()
            self.end_wait()
            fw = self.failed_waiting()
            # a split that ends with failed files is never plain DONE
            if fw:
                self.status = "DONE, %d file(s) failed: %s" % (len(fw), ", ".join(fw))
                if self.failed_analysis:
                    self.status += ", %d analysis job(s) failed: %s" % (len(self.failed_analysis), ", ".join(self.failed_analysis))
            elif self.failed_analysis:
                self.status = "DONE, %d analysis job(s) failed: %s" % (len(self.failed_analysis), ", ".join(self.failed_analysis))
            else:
                self.status = "DONE"
            kept = self.kept_ids()
            if kept:
                self.status += ", %d file(s) kept until accepted: %s" % (len(kept), ", ".join(kept))
        except Stop as s:
            self.status = s.status
        except Interrupted:
            raise
        except Exception as e:
            self.status = ("FAILED: internal error (%s: %s)" % (type(e).__name__, e)).replace("\n", " ")[:160]
            self.traceback_text = traceback.format_exc()
        if not (self.test or self.fake):
            post = self.pins_ok()
            if post and self.status.startswith("DONE"):
                self.status = "FAILED after the split (pins changed: %s)" % post[0]
        try:
            self.copy_records()
        except OSError as e:
            self.notes.append("download records could not be copied: %s" % e)
        fn = self.write_report(facts_made)
        self.update_status_tsv()
        delivered = self.nudge(fn, facts_made)
        self.finish_report(fn)
        self.out("status: %s" % self.status)
        self.out("report: %s/%s" % (self.rundir, fn))
        ok_status = self.status == "DONE" or self.status.startswith("PAUSED") or (self.status.startswith("DONE, ") and "file(s) failed" not in self.status
                                                                                  and "kept until accepted" not in self.status)
        return 0 if (ok_status and delivered) else 1


# ---------- status
def status_cmd(split=None):
    recs = read_log()
    cap = float(os.environ.get(ENV + "CAP_MIN", "840"))
    if split is None:
        print("%s %s split script: status (no network; nothing is created)" % (PROJECT, STEP_WORD))
        rows = status_rows()
        for sp in SPLITS:
            lst = read_tsv_rows("%s/splits/files-%s.tsv" % (RUNS, sp))
            st = {}
            for r in read_tsv_rows("%s/%s/files.tsv" % (RUNS, sp)):
                st[r["id"]] = r["status"]
            done = sum(1 for s in st.values() if s == "DONE")
            fail = sum(1 for s in st.values() if s.startswith("FAILED"))
            pp = Pipe(sp)
            kept = sum(1 for r in lst if st.get(r["key"][:8]) == "DONE" and pp.is_kept(r))
            pre = sp + "-"
            comp = sum(r.get("wall_s", 0.0) for r in recs if r["step"] == ST and r["id"].startswith(pre)) / 60.0
            print("%s  status: %-40s files DONE %d of %d, kept %d, failed %d; compute %.1f of %g min" % (sp, (rows[sp][1] if sp in rows else "not finished")[:40], done, len(lst), kept, fail, comp, cap))
        acc = accepted_names()
        print("accepted by the manager: %s" % (", ".join(sorted(acc)) if acc else "none"))
        print("hold: %s" % ("YES (%s/HOLD exists)" % RUNS if os.path.exists(P(RUNS + "/HOLD")) else "no"))
        print("pins: %s" % ("OK" if not Pipe(SPLITS[0]).pins_ok() else "; ".join(Pipe(SPLITS[0]).pins_ok())))
        print("free space: %.1f GiB" % Pipe(SPLITS[0]).free_gib())
        return 0
    lst = read_tsv_rows("%s/splits/files-%s.tsv" % (RUNS, split))
    st = {}
    for r in read_tsv_rows("%s/%s/files.tsv" % (RUNS, split)):
        st[r["id"]] = (r["status"], r.get("step", ""), r["utc"])
    print("%s %s split script: status of split %s (no network; nothing is created)" % (PROJECT, STEP_WORD, split))
    print("%-9s %-18s %s" % ("id", "state", "last job"))
    pp = Pipe(split)
    for r in lst:
        fid = r["key"][:8]
        last = None
        for x in recs:
            if x["step"] == ST and x["id"].startswith("%s-%s-" % (split, fid)):
                last = x
        s = st.get(fid, ("not started", "", ""))[0]
        if s == "DONE" and pp.is_kept(r):
            s = "DONE kept"
        print("%-9s %-18s %s" % (fid, s[:18], ("%s %s" % (last["id"], last["outcome"])) if last else "-"))
    return 0


def main(a):
    os.chdir(ROOT)
    if a and a[0] == "status":
        if len(a) == 1:
            return status_cmd()
        if len(a) == 2 and a[1] in SPLITS:
            return status_cmd(a[1])
        print("usage: %s status [SPLIT]" % WRAPPER, file=sys.stderr)
        return 2
    if len(a) == 2 and a[0] == "--test" and a[1] in ("fail", "partial", "pilot", "disk", "cap", "error", "sleep"):
        t = a[1]
        p = Pipe("test", test=t)
        if t == "disk":
            p.floor = 1e9
        if t == "cap":
            p.cap = 0.3
        return p.run()
    if len(a) == 1 and (a[0] in SPLITS or (os.environ.get(TESTENV + "TEST_ROOT") and a[0].startswith("tst"))):
        return Pipe(a[0]).run(dry=os.environ.get(DL_DRY_RUN) == "1")
    print("usage: %s SPLIT | status [SPLIT]    (SPLIT: %s)" % (WRAPPER, " ".join(SPLITS)), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
