#!/usr/bin/env python3
"""Which of the listed rule files has a session read whole? The answer is taken from the session's own log.

Usage:
  ack_reads.py SESSION_ID            one line per listed file: "read <path>" or "unread <path>: <why>"
  ack_reads.py --needs SESSION_ID    only the paths that are not read, one per line
  ack_reads.py --selftest

  SESSION_ID   agy-<conversation id>
               codex-<thread id>, or codex-<pid> of a Codex session that is running on this machine. The pid form
               reads /proc, so it works on Linux and WSL only; on macOS give the thread id.

A file counts as read when the text that the session's tools returned, after the file last changed, holds the
file's lines from the first to the last. Several calls may share one file. A part of the file does not count, and
neither does a read made before the file's last change. The list is general/rules/mandatory-repo-read/
reading-list.txt at HEAD ("linux <path>" and "darwin <path>" apply on that platform only), and a file's text and
the time of its last change are taken from the repository at HEAD.

Where the logs are (the variable in brackets overrides the folder):
  agy    ~/.gemini/antigravity-cli/brain/<conversation id>/.system_generated/logs/transcript_full.jsonl
         [AI_MGMT_AGY_BRAIN]; the rows of type GENERIC hold what a tool returned
  Codex  ${CODEX_HOME:-~/.codex}/sessions/<yyyy>/<mm>/<dd>/rollout-<time>-<thread id>.jsonl
         [AI_MGMT_CODEX_SESSIONS]; the response items whose type ends in "_output" hold what a tool returned

It reads; it changes nothing. Exit status:
  0  every listed file is read
  1  at least one is not
  3  the check cannot be made for this id: a brand whose log is not known here, agy's log folder is not on this
     machine, or no log is found for a Codex id
  2  usage
"""
import calendar
import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("AI_MGMT_REPO") or os.path.normpath(os.path.join(HERE, "..", "..", ".."))
LIST = "general/rules/mandatory-repo-read/reading-list.txt"
NUMBER = re.compile(r"^\d+\s*[:|]?\s?")      # the line number that a reading tool, nl or grep -n puts first
STAMP = re.compile(r"(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(?:\.\d+)?(Z|[+-]\d\d:?\d\d)?$")
MAX_LOG = 400 * 1024 * 1024                  # of a longer log, only the end is read


def git(*args):
    return subprocess.run(["git", "-C", REPO] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True, encoding="utf-8", errors="replace")


def listed():
    """The reading list at HEAD, for this platform."""
    r = git("show", "HEAD:" + LIST)
    if r.returncode != 0:
        raise OSError("cannot read %s at HEAD of %s: %s" % (LIST, REPO, r.stderr.strip()))
    out = []
    for line in r.stdout.split("\n"):
        words = line.split()
        if not words or words[0].startswith("#"):
            continue
        if len(words) == 2:
            if not sys.platform.startswith(words[0]):
                continue
            words = words[1:]
        out.append(words[0])
    return out


def norm(text):
    return re.sub(r"\s+", " ", text).strip()


def evidence_lines(text):
    """The lines of a file that are looked for in the log: plain lines that a tool returns unchanged."""
    lines = [norm(x) for x in text.split("\n")]
    good = [x for x in lines if 25 <= len(x) <= 400 and x.isascii() and not re.search(r"[<>&]", x)]
    if len(good) < 5:
        good = [x for x in lines if len(x) >= 10]
    return good


def when(stamp):
    """Seconds since 1970 of an ISO time (no zone means UTC); None if it is not one."""
    m = STAMP.match(stamp or "")
    if not m:
        return None
    t = calendar.timegm(tuple(int(x) for x in m.groups()[:6]) + (0, 0, 0))
    zone = m.group(7)
    if zone and zone != "Z":
        t -= (1 if zone[0] == "+" else -1) * (int(zone[1:3]) * 3600 + int(zone[-2:]) * 60)
    return t


def rows(path, marker):
    """The JSON rows of a log that contain the marker."""
    with open(path, "rb") as f:
        size = os.fstat(f.fileno()).st_size
        if size > MAX_LOG:
            f.seek(size - MAX_LOG)
            f.readline()
        for raw in f:
            if marker not in raw:
                continue
            try:
                row = json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                continue
            if isinstance(row, dict):
                yield row


def strings(value):
    """Every text inside a tool's output, whatever its shape."""
    if isinstance(value, str):
        if value.lstrip()[:1] in ("{", "["):
            try:
                inner = json.loads(value)
            except ValueError:
                inner = None
            if isinstance(inner, (dict, list)):
                for s in strings(inner):
                    yield s
                return
        yield value
    elif isinstance(value, list):
        for v in value:
            for s in strings(v):
                yield s
    elif isinstance(value, dict):
        for v in value.values():
            for s in strings(v):
                yield s


def outputs_agy(path):
    for row in rows(path, b'"GENERIC"'):
        if row.get("type") == "GENERIC" and isinstance(row.get("content"), str):
            yield when(row.get("created_at")), row["content"]


def outputs_codex(path):
    for row in rows(path, b'_output"'):
        p = row.get("payload")
        if row.get("type") == "response_item" and isinstance(p, dict) and str(p.get("type", "")).endswith("_output"):
            t = when(row.get("timestamp"))
            for s in strings(p.get("output")):
                yield t, s


def rollout_of_pid(pid):
    """The session log that a running Codex process, or one of its children, has open (Linux)."""
    if not os.path.isdir("/proc/%d" % pid):
        return None
    children = {}
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            with open("/proc/%s/stat" % name) as f:
                parent = int(f.read().rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            continue
        children.setdefault(parent, []).append(int(name))
    todo, seen = [pid], set()
    while todo:
        p = todo.pop()
        if p in seen:
            continue
        seen.add(p)
        try:
            fds = os.listdir("/proc/%d/fd" % p)
        except OSError:
            fds = []
        for fd in fds:
            try:
                target = os.readlink("/proc/%d/fd/%s" % (p, fd))
            except OSError:
                continue
            if re.search(r"/rollout-[^/]*\.jsonl$", target) and os.path.isfile(target):
                return target
        todo.extend(children.get(p, []))
    return None


def find_log(sid):
    """(brand, path of the log or None, whether the check can be made, a word on where it was looked for)."""
    if ".." in sid or "/" in sid:
        return None, None, False, "not a session id"
    if sid.startswith("agy-"):
        root = os.environ.get("AI_MGMT_AGY_BRAIN") or os.path.expanduser("~/.gemini/antigravity-cli/brain")
        path = os.path.join(root, sid[4:], ".system_generated", "logs", "transcript_full.jsonl")
        if not os.path.isdir(root):
            return "agy", None, False, "agy's log folder %s is not on this machine" % root
        return "agy", (path if os.path.isfile(path) else None), True, path
    if sid.startswith("codex-"):
        root = os.environ.get("AI_MGMT_CODEX_SESSIONS") or os.path.join(
            os.environ.get("CODEX_HOME") or os.path.expanduser("~/.codex"), "sessions")
        key = sid[6:]
        if key.isdigit():
            path = rollout_of_pid(int(key))
            return "codex", path, bool(path), "no running Codex process %s has a session log open" % key
        if re.match(r"[0-9a-fA-F][0-9a-fA-F-]{7,}$", key):
            hits = sorted(glob.glob(os.path.join(root, "*", "*", "*", "rollout-*%s*.jsonl" % key)))
            return "codex", (hits[-1] if hits else None), bool(hits), os.path.join(root, "*", "*", "*", "rollout-*%s*.jsonl" % key)
        return "codex", None, False, "a Codex id is codex-<thread id> or codex-<pid>"
    return None, None, False, "only the logs of agy and Codex sessions are known here"


def check(sid):
    """(exit status, [(path, read?, why)], a word when the check cannot be made)."""
    brand, path, can, where = find_log(sid)
    if not can:
        return 3, [], "the reads of %s cannot be checked: %s" % (sid, where)
    latest = {}                               # a line the tools returned -> the last time it was returned
    if path:
        for t, text in (outputs_agy(path) if brand == "agy" else outputs_codex(path)):
            if t is None:
                continue
            for raw in text.split("\n"):
                line = norm(raw)
                if len(line) < 10:
                    continue
                for form in (line, NUMBER.sub("", line, 1)):
                    if latest.get(form, -1) < t:
                        latest[form] = t
    result, bad = [], False
    for f in listed():
        body = git("show", "HEAD:" + f)
        if body.returncode != 0:
            result.append((f, False, "it is on the list but not in the repository at HEAD"))
            bad = True
            continue
        stamp = git("log", "-1", "--format=%ct", "HEAD", "--", f).stdout.strip()
        changed = int(stamp) if stamp.isdigit() else 0
        want = evidence_lines(body.stdout)
        since = sum(1 for x in want if latest.get(x, -1) >= changed)
        ever = sum(1 for x in want if x in latest)
        slack = max(1, len(want) // 50) if len(want) >= 20 else (1 if len(want) >= 8 else 0)
        if since >= len(want) - slack:
            result.append((f, True, ""))
            continue
        bad = True
        if not path:
            why = "this session has no log yet (%s)" % where
        elif since == 0 and ever * 2 > len(want):
            why = "read before the file last changed; read it again, whole"
        elif since == 0:
            why = "not read in this session"
        else:
            why = "a part only: %d of its %d checked lines are in this session's log since the file last changed" % (
                since, len(want))
        result.append((f, False, why))
    return (1 if bad else 0), result, ""


# ---------------------------------------------------------------- self-test
def selftest():
    import shutil
    import tempfile
    global REPO
    bad = []
    tmp = tempfile.mkdtemp(prefix="ack-reads-test.")
    keep = (REPO, os.environ.get("AI_MGMT_AGY_BRAIN"), os.environ.get("AI_MGMT_CODEX_SESSIONS"))
    try:
        REPO = os.path.join(tmp, "repo")
        os.makedirs(os.path.join(REPO, os.path.dirname(LIST)))
        os.makedirs(os.path.join(REPO, "rules"))
        text_a = "".join("Rule A line %02d says something long enough to be checked.\n" % k for k in range(1, 41))
        text_b = "".join("Rule B line %02d says another thing long enough to count.\n" % k for k in range(1, 31))
        with open(os.path.join(REPO, LIST), "w") as f:
            f.write("# the list\nrules/a.md\nrules/b.md\nnosuchplatform rules/skipped.md\n")
        with open(os.path.join(REPO, "rules", "a.md"), "w") as f:
            f.write(text_a)
        with open(os.path.join(REPO, "rules", "b.md"), "w") as f:
            f.write(text_b)
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid", GIT_COMMITTER_NAME="t",
                   GIT_COMMITTER_EMAIL="t@example.invalid", GIT_AUTHOR_DATE="2026-01-01T00:00:00Z",
                   GIT_COMMITTER_DATE="2026-01-01T00:00:00Z")
        for cmd in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "test"]):
            subprocess.run(["git", "-C", REPO] + cmd, check=True, env=env, stdout=subprocess.DEVNULL)
        brain = os.path.join(tmp, "brain")
        sessions = os.path.join(tmp, "sessions")
        os.environ["AI_MGMT_AGY_BRAIN"] = brain
        os.environ["AI_MGMT_CODEX_SESSIONS"] = sessions

        def numbered(text, first=1):
            lines = text.split("\n")[:-1]
            return "Showing lines %d-%d of %d\n" % (first, first + len(lines) - 1, 40) + "\n".join(
                "%d: %s" % (first + k, x) for k, x in enumerate(lines))

        def agy(cid, items):
            d = os.path.join(brain, cid, ".system_generated", "logs")
            os.makedirs(d)
            with open(os.path.join(d, "transcript_full.jsonl"), "w") as f:
                for stamp, text in items:
                    f.write(json.dumps({"type": "GENERIC", "created_at": stamp, "content": text}) + "\n")
                f.write(json.dumps({"type": "USER_INPUT", "created_at": "2026-02-01T00:00:00Z", "content": text_a + text_b}) + "\n")

        def codex(thread, items):
            d = os.path.join(sessions, "2026", "02", "01")
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "rollout-2026-02-01T00-00-00-%s.jsonl" % thread), "w") as f:
                for stamp, kind, output in items:
                    f.write(json.dumps({"timestamp": stamp, "type": "response_item", "payload": {"type": kind, "output": output}}) + "\n")

        def expect(label, sid, status, reads=None, says=None):
            rc, result, word = check(sid)
            got = {f: ok for f, ok, _ in result}
            text = " ".join(why for _, _, why in result) + " " + word
            if rc != status or (reads is not None and got != reads) or (says and says not in text):
                bad.append("%s: exit %d %s %r" % (label, rc, got, text.strip()))

        after, before = "2026-02-01T10:00:00Z", "2025-12-01T10:00:00Z"
        half = "".join(text_a.split("\n")[k] + "\n" for k in range(20))
        os.makedirs(brain)
        agy("whole", [(after, numbered(text_a)), (after, numbered(text_b))])
        expect("agy: both files whole, with line numbers", "agy-whole", 0, {"rules/a.md": True, "rules/b.md": True})
        agy("two-calls", [(after, numbered(half)), ("2026-02-01T18:00:00+08:00", numbered(text_a[len(half):], 21)), (after, text_b)])
        expect("agy: one file in two calls, the second with a time zone", "agy-two-calls", 0)
        agy("part", [(after, numbered(half)), (after, numbered(text_b))])
        expect("agy: half of a file", "agy-part", 1, {"rules/a.md": False, "rules/b.md": True}, "a part only: 20 of its 40")
        agy("old", [(before, numbered(text_a)), (after, numbered(text_b))])
        expect("agy: a read made before the file last changed", "agy-old", 1, {"rules/a.md": False, "rules/b.md": True}, "before the file last changed")
        agy("asked-only", [(after, "nothing was read")])
        expect("agy: the text only in the user's message", "agy-asked-only", 1, {"rules/a.md": False, "rules/b.md": False}, "not read in this session")
        expect("agy: a conversation with no log", "agy-nolog", 1, {"rules/a.md": False, "rules/b.md": False}, "no log yet")
        codex("0a1b2c3d-1111", [(after, "custom_tool_call_output", [{"type": "input_text", "text": "Output:\n"}, {"type": "input_text", "text": text_a + text_b}])])
        expect("codex: both files in one output", "codex-0a1b2c3d-1111", 0)
        codex("0a1b2c3d-2222", [(after, "custom_tool_call_output", [{"type": "input_text", "text": "Warning: truncated output\n" + half + text_b}])])
        expect("codex: an output that was cut", "codex-0a1b2c3d-2222", 1, {"rules/a.md": False, "rules/b.md": True}, "a part only")
        codex("0a1b2c3d-3333", [(after, "function_call_output", json.dumps({"output": text_a + text_b, "metadata": {"exit_code": 0}}))])
        expect("codex: an output wrapped in JSON text", "codex-0a1b2c3d-3333", 0)
        expect("codex: a thread with no log", "codex-0a1b2c3d-9999", 3, says="cannot be checked")
        expect("another brand", "gemini-1", 3, says="only the logs of agy and Codex")
        expect("an id with a path in it", "agy-../x", 3, says="not a session id")
        shutil.rmtree(brain)
        expect("agy: its log folder is not on this machine", "agy-whole", 3, says="is not on this machine")
        if when("2026-02-01T18:00:00+08:00") != when("2026-02-01T10:00:00Z") or when("2026-02-01T10:00:00.250Z") != when("2026-02-01T10:00:00"):
            bad.append("times: a zone or a fraction of a second is read wrongly")
    finally:
        REPO = keep[0]
        for name, value in (("AI_MGMT_AGY_BRAIN", keep[1]), ("AI_MGMT_CODEX_SESSIONS", keep[2])):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        shutil.rmtree(tmp, ignore_errors=True)
    for line in bad:
        print("SELFTEST FAIL: " + line)
    print("selftest: %s" % ("FAILED" if bad else "ok (read: whole files, in one call or two, from agy's and Codex's logs; "
                            "not read: a half, a cut output, a read before the last change, text that only the user "
                            "sent, a missing log; cannot be checked: another brand, a missing log folder)"))
    return 1 if bad else 0


def main(argv):
    if argv == ["--selftest"]:
        return selftest()
    needs = argv[:1] == ["--needs"]
    ids = argv[1:] if needs else argv
    if len(ids) != 1 or ids[0].startswith("-"):
        print(__doc__, file=sys.stderr)
        return 2
    try:
        status, result, word = check(ids[0])
    except OSError as e:
        print(str(e), file=sys.stderr)
        return 3
    if status == 3:
        print(word, file=sys.stderr)
        return 3
    for f, ok, why in result:
        if needs:
            if not ok:
                print(f)
        else:
            print("read %s" % f if ok else "unread %s: %s" % (f, why))
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
