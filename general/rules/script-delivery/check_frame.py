#!/usr/bin/env python3
"""Check a captured screen against the ordered format of the download and pipeline templates.

The Script Delivery Rule (The_Script_Delivery_Rule.md, beside this file) says that a claim about a script's format
needs a check that can fail. This is that check. It reads the text a script printed and compares every dashboard
frame in it, row by row, with the frame that general/templates/download-ui/fetch_dst.py draws (its render()), and,
for a pipeline, the lines that general/templates/chunked-pipeline/pipe.py prints.

Usage:
  check_frame.py [--kind download|pipeline] [--complete] [--columns N] CAPTURE [CAPTURE ...]
  check_frame.py --selftest

  CAPTURE      a text file with what the script printed ("-" reads standard input). Escape codes are removed,
               so the capture of a terminal works as well as piped output.
  --kind       download (default): the dashboard frames, and the start and end lines where they appear.
               pipeline: the same, and the driver's lines (file, job, file report).
  --complete   the capture holds a whole run: the start lines, the end lines and, for a pipeline, the SUMMARY,
               nudge, status and report lines must all be there.
  --columns N  the terminal's width when the capture was made. A line of N-1 characters was cut there, and its
               end is not checked. Without it the width is taken as 80 or 100, whichever the longest line fits.

How to capture (Linux; on macOS: script -q FILE COMMAND ...):
  COMMAND > capture-100.txt                                              # piped: a 100-column frame every 30 s
  COLUMNS=80 LINES=30 script -q -c "COMMAND" capture-80.txt              # a terminal of 80 columns
COMMAND must really download: a dry run, the pipeline's --test modes and its made-up files draw no frame.
frame_test_server.py, beside this file, serves two test files slowly for that; the rule gives the commands.

It changes nothing. Exit status: 0 when every frame and line fits, 1 when something does not fit or no frame was
found, 2 on a usage error.
"""
import os
import re
import sys

ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[()][0-9A-B]|\x1b[=>]")
HUM = r"(?:\d+\.\d\d (?:GB|MB|KB)|\d+ B)"
RATE = r"(?:\d+\.\d\d MB/s|\d+ KB/s)"
CLK = r"\d\d:\d\d:\d\d"                 # a time of day
DUR = r"\d{2,}:\d\d:\d\d"               # a length of time, from clock(): the hours go past 99 (100:00:00)
NUM = r"\d+(?:\.\d+)?(?:e[+-]?\d+)?"    # a number printed with %g
BAR_REC = r"(?:[█░]{20}|[█░]{10})"      # a group's or a record's bar: 20 characters, 10 below 100 columns
BAR_FILE = r"(?:[█░]{16}|[█░]{6})"      # a file's bar: 16 characters, 6 below 100 columns
UTC = r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ"
WHERE = "general/templates/download-ui/README.md, \"The dashboard\""

# The nine fixed rows at the top of a frame: (name, how it reads, its parts in order).
# The first part of a row must fit even when the terminal cut the line.
HEAD = [
    ("title", "<TITLE> <run>  |  HH:MM:SS  |  elapsed HH:MM:SS  |  <N> workers  |  time-out <S> s",
     [r".+?  \|  " + CLK, r"  \|  elapsed " + DUR, r"  \|  \d+ workers", r"  \|  time-out " + NUM + " s"]),
    ("STEP", "STEP     <i> of <n>  group <G>  |  downloading <a>, processing 0, finished <c> of <d> files",
     [r"STEP     \d+ of \d+  group ", r".*?  \|  downloading \d+, processing 0, finished \d+ of \d+ files"]),
    ("THIS STEP", "THIS STEP <20-character bar> <p>%  moved <X> of <Y>",
     [r"THIS STEP [█░]{20} +\d+\.\d%", r"  moved " + HUM + " of " + HUM]),
    ("TO DOWNLOAD (estimate)", "TO DOWNLOAD (estimate)  <X> in all   moved <Y>",
     [r"TO DOWNLOAD \(estimate\)  " + HUM + " in all", r"   moved " + HUM]),
    ("TOTAL", "TOTAL    <30-character bar> <p>%   <got> / <size>",
     [r"TOTAL    [█░]{30} +\d+\.\d%", r"   " + HUM + " / " + HUM]),
    ("FILES", "FILES    <n>/<N> complete   <d> downloading   <w> workers alive",
     [r"FILES    \d+/\d+ complete", r"   \d+ downloading", r"   \d+ workers alive"]),
    ("SPEED", "SPEED    now <rate>   average <rate>   ETA HH:MM:SS",
     [r"SPEED    now (?:measuring|" + RATE + ")", r"   average (?:measuring|" + RATE + ")",
      r"   ETA (?:" + DUR + "|unknown)"]),
    ("LINKS", "LINKS    <c> connections open   <rate> each   <s> stalled right now",
     [r"LINKS    \d+ connections open", r"   (?:measuring|-|" + RATE + ") each", r"   \d+ stalled right now"]),
    ("HEALTH", "HEALTH   failed attempts <a>   stalls dropped <b>   certificate events <c>[   LASTERR ...]"
               "[   NETWORK DOWN? waiting, retrying]",
     [r"HEALTH   failed attempts \d+", r"   stalls dropped \d+", r"   certificate events \d+",
      r"(?:   LASTERR .*)?(?:   NETWORK DOWN\? waiting, retrying)?"]),
]
GROUPS_HDR = "GROUPS (moved / estimate)"
RECORDS_HDR = "RECORDS"
NOW_HDR = re.compile(r"DOWNLOADING NOW \(showing \d+ of \d+, nearest to done first\)$")
GROUP_ROW = ("a GROUPS line", "  <G>  <bar> <p>%  <d>/<n>   files  <moved> / <estimate>",
             [r"  [^█░]*? " + BAR_REC + r" +\d+\.\d%", r"  +\d+/\d+ +files", r"  " + HUM + " / " + HUM])
RECORD_ROW = ("a RECORDS line", "  <recid> <name> <bar> <p>%   <d>/<n>   files   <got> / <size>",
              [r"  \d+ [^█░]*?" + BAR_REC + r" +\d+\.\d%", r"   +\d+/\d+ +files", r"   " + HUM + " / " + HUM])
FILE_ROW = ("a DOWNLOADING NOW line", "  <recid> <key> <bar> <p>%  <got> / <size>  <rate>  ETA HH:MM:SS",
            [r"  \d+ [^█░]+? +" + BAR_FILE + r" +\d+%", r"  +" + HUM + " */ *" + HUM, r" +.+"])
MORE_ROW = re.compile(r"  … and \d+ more$")
BOTTOM = re.compile(r"Ctrl-C stops cleanly; rerun resumes   \|   log: .")
BOTTOM_ANY = re.compile(r"Ctrl-C stops cleanly")
TITLE_LIKE = re.compile(r"\S.*\|\s*\d\d:\d\d(?::\d\d)?\s*\|")

START_LINES = [("DOWNLOAD START UTC", re.compile(r"DOWNLOAD START UTC: " + UTC + "$")),
               ("DOWNLOAD ROOT", re.compile(r"DOWNLOAD ROOT: .")),
               ("DOWNLOAD LOG", re.compile(r"DOWNLOAD LOG: .")),
               ("TOTAL FILES", re.compile(r"TOTAL FILES: \d+$")),
               ("TOTAL BYTES", re.compile(r"TOTAL BYTES: \d+$")),
               ("ON DISK AT START", re.compile(r"ON DISK AT START: \d+ files complete, \d+ bytes of \d+$")),
               ("WORKERS", re.compile(r"WORKERS: \d+ \(set \S+ to change\); refresh every \d+ s$"))]
# Two of these labels as the downloader's dry run prints them (fetch_dst.py, dry_run()): they are not start lines.
DRY_FORMS = {"TOTAL FILES": re.compile(r"TOTAL FILES: \d+, TOTAL BYTES: \d+$"),
             "WORKERS": re.compile(r"WORKERS: \d+, max attempts without progress per file: \d+$")}
END_LINES = [("DOWNLOAD END UTC", re.compile(r"DOWNLOAD END UTC: " + UTC + "$")),
             ("done <n> of <N> files", re.compile(r"done \d+ of \d+ files, \d+ of \d+ bytes; exit reason: ."))]
END_WORD = re.compile(r"DOWNLOAD COMPLETE$|DOWNLOAD INCOMPLETE \(.+\); rerun the script to resume\. Details: .|"
                      r"INTERRUPTED: partial files are kept\. Rerun the script to resume\.$")
COMPUTE = r" \| compute \d+\.\d of " + NUM + r" min\s*$"
JOB_START = r"\S.*? start \(limit \d+ s\)"
JOB_END = r"\S.* \d+\.\d s"
# (name, the whole line, its beginning). The driver cuts a line at the terminal's width (99 characters when piped),
# so a line that long needs only its beginning.
PIPE_LINES = [("file <id> (<i> of <n>)", re.compile(r"file \S+ \(\d+ of \d+\)\s*$"), None),
              ("<stage> <job id> start (limit <s> s) | compute <x> of <cap> min",
               re.compile(JOB_START + COMPUTE), re.compile(JOB_START)),
              ("<stage> <job id> <outcome> <t> s | compute <x> of <cap> min",
               re.compile(JOB_END + COMPUTE), re.compile(JOB_END)),
              ("[<utc>] file report DONE|FAILED: ...", re.compile(r"\[" + UTC + r"\] file report (?:DONE|FAILED): ."), None)]
PIPE_END = [("[<utc>] SUMMARY: ...", re.compile(r"\[" + UTC + r"\] SUMMARY: ."), None),
            ("nudge: ...", re.compile(r"nudge: ."), None),
            ("status: ...", re.compile(r"status: ."), None),
            ("report: ...", re.compile(r"report: ."), None)]
STAMPED = re.compile(r"\[" + UTC + r"\] (?:file report (?:DONE|FAILED): |file \S+ FAILED at |deleted |WAITING |SUMMARY: )")
STAMP_START = re.compile(r"\[\d{4}-\d\d-\d\dT")


def clean(text):
    """The capture as lines: escape codes out, and of a line rewritten with a carriage return only its last state."""
    out = []
    for line in ANSI.sub("", text).split("\n"):
        parts = [p for p in line.split("\r") if p.strip()]
        out.append(parts[-1].rstrip("\r") if parts else "")
    return out


def fit(line, parts, cut_len):
    """None when the line is made of the parts in order; otherwise what is wrong. A line that the terminal cut
    (it reaches cut_len) needs only its first part."""
    pos = 0
    was_cut = bool(cut_len) and len(line) >= cut_len - 3
    for k, part in enumerate(parts):
        m = re.compile(part).match(line, pos)
        if not m:
            if k >= 1 and was_cut:
                return None
            return "does not fit at character %d: %r" % (pos + 1, line[pos:pos + 46])
        pos = m.end()
    if line[pos:].strip() and not was_cut:
        return "has text after its end: %r" % line[pos:pos + 46]
    return None


# How a line shows which of the fixed rows it is meant to be, even when it does not fit that row.
LABEL = {"STEP": "STEP ", "THIS STEP": "THIS STEP ", "TO DOWNLOAD (estimate)": "TO DOWNLOAD", "TOTAL": "TOTAL ",
         "FILES": "FILES ", "SPEED": "SPEED ", "LINKS": "LINKS ", "HEALTH": "HEALTH "}
BAR_HINT = " (bars are made of █ and ░ only, with no brackets)"


def is_row(line, k):
    """True when the line carries the label of fixed row k."""
    label = LABEL.get(HEAD[k][0])
    return bool(label) and line.startswith(label)


def bar_hint(line):
    return BAR_HINT if re.search(r"\[[-#=.█░ ]|#{2,}|={3,}", line) else ""


def check_frame(lines, start, columns):
    """Check the frame whose title is lines[start]. Returns (errors, index of the line after the frame)."""
    errs = []
    end = start + 1
    while end < len(lines) and end - start < 5000:      # a frame has one line per group and per record
        if BOTTOM_ANY.match(lines[end]):
            end += 1
            break
        if end > start + 1 and TITLE_LIKE.match(lines[end]) and not lines[end].startswith(" "):
            break
        end += 1
    frame = lines[start:end]
    longest = max(len(x) for x in frame)
    cut_len = (columns - 1) if columns else (79 if longest <= 79 else 99 if longest <= 99 else longest)

    def bad(n, text):
        errs.append("line %d: %s" % (start + n + 1, text))

    # the nine fixed rows, in order; a row that is absent is named, a row that is not one of them is named
    n, k = 0, 0
    while k < len(HEAD) and n < len(frame):
        name, reads, parts = HEAD[k]
        line = frame[n]
        why = fit(line, parts, cut_len)
        if why is None:
            n += 1
            k += 1
            continue
        if is_row(line, k) or (k == 0 and n == 0):
            bad(n, "the %s row %s; it reads: %s%s" % (name, why, reads, bar_hint(line)))
            n += 1
            k += 1
            continue
        later = [j for j in range(k + 1, len(HEAD)) if is_row(line, j)]
        if later or line == GROUPS_HDR:
            bad(n, "the %s row is missing before %r; it reads: %s" % (name, line[:40], reads))
            k += 1
            continue
        if not line.strip():
            bad(n, "the %s row is missing (a blank line is there); it reads: %s" % (name, reads))
            k += 1
            continue
        bad(n, "a row that the format does not have: %r" % line[:60])
        n += 1
    for j in range(k, len(HEAD)):
        if n >= len(frame):
            bad(n - 1, "the %s row is missing; it reads: %s" % (HEAD[j][0], HEAD[j][1]))

    # the three sections and the bottom line
    order = ["GROUPS", "RECORDS", "NOW", "BOTTOM"]
    seen = {}
    section = None
    counts = {"GROUPS": 0, "RECORDS": 0}
    for m in range(n, len(frame)):
        line = frame[m]
        if not line.strip():
            continue
        if line == GROUPS_HDR:
            section = "GROUPS"
        elif line == RECORDS_HDR:
            section = "RECORDS"
        elif NOW_HDR.match(line):
            section = "NOW"
        elif BOTTOM_ANY.match(line):
            section = "BOTTOM"
            if not BOTTOM.match(line):
                bad(m, "the bottom line does not fit; it reads: Ctrl-C stops cleanly; rerun resumes   |   log: "
                       "<folder>/download.log")
        elif line.startswith("  ") and section in ("GROUPS", "RECORDS", "NOW"):
            if section == "NOW" and MORE_ROW.match(line):
                continue
            spec = {"GROUPS": GROUP_ROW, "RECORDS": RECORD_ROW, "NOW": FILE_ROW}[section]
            why = fit(line, spec[2], cut_len)
            if why:
                bad(m, "%s %s; it reads: %s%s" % (spec[0], why, spec[1], bar_hint(line)))
            if section in counts:
                counts[section] += 1
            continue
        else:
            bad(m, "a row that the format does not have: %r" % line[:60])
            continue
        if section in seen:
            bad(m, "the %s part appears twice" % section)
        for earlier in order[order.index(section) + 1:]:
            if earlier in seen:
                bad(m, "the %s part comes after the %s part" % (section, earlier))
        seen[section] = m
    names = {"GROUPS": GROUPS_HDR, "RECORDS": RECORDS_HDR, "NOW": "DOWNLOADING NOW (showing <a> of <b>, nearest to done "
             "first)", "BOTTOM": "Ctrl-C stops cleanly; rerun resumes   |   log: ..."}
    for part in order:
        if part not in seen:
            bad(len(frame) - 1, "the frame has no line %r" % names[part])
    for part, cnt in counts.items():
        if part in seen and cnt == 0:
            bad(seen[part], "%s has no line under it" % names[part])
    return errs, end


def check_text(text, kind="download", complete=False, columns=None):
    """Returns (errors, frames found)."""
    lines = clean(text)
    errs, frames, i = [], 0, 0
    while i < len(lines):
        if TITLE_LIKE.match(lines[i]) and not lines[i].startswith(" "):
            e, i = check_frame(lines, i, columns)
            frames += 1
            errs += e
        else:
            i += 1
    if frames == 0:
        errs.append("no dashboard frame found: a frame starts with the title row "
                    "'<TITLE> <run>  |  HH:MM:SS  |  elapsed ...'")

    cut_at = (columns - 1) if columns else 79       # the shortest line that the driver can have cut

    def need(specs, what):
        for name, rx, head in specs:
            if not any(rx.match(line) or (head and len(line.rstrip()) >= cut_at and head.match(line)) for line in lines):
                errs.append("%s: no line %r" % (what, name))

    def well_formed(specs, what):
        """A line that starts like one of these, but does not fit it."""
        for name, rx in specs:
            label = name.split(" <")[0]
            dry = DRY_FORMS.get(label)
            for n, line in enumerate(lines):
                if line.startswith(label + ":") and not rx.match(line) and not (dry and dry.match(line)):
                    errs.append("line %d: the %s line %r does not fit %r" % (n + 1, what, line[:50], name))

    well_formed(START_LINES, "start")
    well_formed(END_LINES[:1], "end")
    if complete:
        need([(name, rx, None) for name, rx in START_LINES], "the start lines")
        need([(name, rx, None) for name, rx in END_LINES], "the end lines")
        if not any(END_WORD.match(line) for line in lines):
            errs.append("the end lines: no 'DOWNLOAD COMPLETE', 'DOWNLOAD INCOMPLETE (...)' or 'INTERRUPTED: ...' line")
    if kind == "pipeline":
        need(PIPE_LINES, "the pipeline's lines")
        if complete:
            need(PIPE_END, "the end of the split")
        for n, line in enumerate(lines):
            if STAMP_START.match(line) and not STAMPED.match(line):
                errs.append("line %d: a stamped line that the pipeline does not print: %r" % (n + 1, line[:60]))
    return errs, frames


def report(path, text, kind, complete, columns):
    errs, frames = check_text(text, kind, complete, columns)
    for e in errs[:40]:
        print("FAIL %s: %s" % (path, e))
    if len(errs) > 40:
        print("FAIL %s: ... and %d more" % (path, len(errs) - 40))
    print("Checked %s as %s%s: %d frame(s), %d finding(s). The format: %s" % (
        path, kind, " (complete run)" if complete else "", frames, len(errs), WHERE))
    return len(errs)


# ---------------------------------------------------------------- self-test
# Two frames that were delivered as "the original format" on 2026-11-27 and were not (the incident behind the rule).
NOT_THE_FORMAT_1 = """E2 S234 Pipeline | 14:48:12 | 00:41 | 8w | step2
TOTAL   [--------------]   0.0%  0/163 (skip 0, fail 7)
RATE     0.00 job/s   active 2   ETA unknown
STAGES
  step2 [----------]  0/9  skip=0 fail=7
  step3 [----------]  0/77 skip=0 fail=0
  step4 [----------]  0/77 skip=0 fail=0
ACTIVE (2)
  step2:mc:qf1584.qf1584.5ne-mc7  41.2s
  step2:mc:qf1651.qf1651.5ne-mc7  17.1s
Ctrl-C stops cleanly; rerun resumes | report: /path/to/project/runs/S234
"""
NOT_THE_FORMAT_2 = """E2 S234 pipeline  |  15:09:08  |  elapsed 00:26  |  8 workers
TOTAL    [#############-----------------]  42.9%   70 / 163 jobs
FILES    70/163 complete   7 running   7 workers alive
SPEED    now 3.30/s   average 2.54/s   ETA 00:36
LINKS    7 jobs open   0.47/s each   0 slow right now
HEALTH   skipped 2   errors 0

GROUPS
  data_1996_1998   [####------]  44.9%    61/136 jobs
  mc_zqq           [###-------]  33.3%     9/27  jobs

RUNNING NOW (showing 5 of 7, longest running first)
  step3      ...in_mdst.7b1 [------]   1.9s
"""
# A frame drawn by general/templates/download-ui/fetch_dst.py in a terminal of 80 columns: copied unchanged from a
# run against a local test server on 2026-11-27 (COLUMNS=80 LINES=30 script -q -c ...). Three of its lines were cut
# at 79 characters by the terminal's width.
NARROW = """PROJECT download set1  |  18:03:14  |  elapsed 00:00:04  |  2 workers  |  time-
STEP     1 of 1  group set1  |  downloading 2, processing 0, finished 0 of 2 fi
THIS STEP █████████████░░░░░░░  63.0%  moved 5.67 MB of 9.00 MB
TO DOWNLOAD (estimate)  9.00 MB in all   moved 5.67 MB
TOTAL    ███████████████████░░░░░░░░░░░  63.0%   5.67 MB / 9.00 MB
FILES    0/2 complete   2 downloading   2 workers alive
SPEED    now 1.37 MB/s   average 1.32 MB/s   ETA 00:00:02
LINKS    2 connections open   700 KB/s each   0 stalled right now
HEALTH   failed attempts 0   stalls dropped 0   certificate events 0

GROUPS (moved / estimate)
  81001 █████░░░░░  49.0%    0/1   files  2.94 MB / 6.00 MB
  81002 █████████░  91.1%    0/1   files  2.73 MB / 3.00 MB

RECORDS
  81001             █████░░░░░  49.0%     0/1   files   2.94 MB / 6.00 MB
  81002             █████████░  91.1%     0/1   files   2.73 MB / 3.00 MB

DOWNLOADING NOW (showing 2 of 2, nearest to done first)
  81002 b.bin          █████░  91%  2.73 MB / 3.00 MB  700 KB/s  ETA 00:00:00
  81001 a.bin          ███░░░  49%  2.94 MB / 6.00 MB  700 KB/s  ETA 00:00:04

Ctrl-C stops cleanly; rerun resumes   |   log: /tmp/frame-test.wOYLDk/out80/dow
"""


def readme_screen():
    """The screen recorded in the pipeline template's README: the reference this checker is held to."""
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.normpath(os.path.join(here, "..", "..", "templates", "chunked-pipeline", "README.md"))
    with open(path, encoding="utf-8") as f:
        text = f.read()
    i = text.index("## The screen")
    j = text.index("```text\n", i) + len("```text\n")
    return text[j:text.index("\n```", j)] + "\n", path


def template_formatters():
    """The download template itself, loaded from its file: its human(), clock(), rate_text() and bar() write the
    values that this checker's patterns must take."""
    import importlib.util
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.normpath(os.path.join(here, "..", "..", "templates", "download-ui", "fetch_dst.py"))
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("fetch_dst_template", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def selftest():
    bad = []

    def expect(label, text, ok, kind="download", complete=False, columns=None, must_say=None):
        errs, frames = check_text(text, kind, complete, columns)
        if ok and errs:
            bad.append("%s: should pass, but: %s" % (label, errs[0]))
        if not ok and not errs:
            bad.append("%s: should fail, but passed" % label)
        if must_say and not any(must_say in e for e in errs):
            bad.append("%s: no finding says %r (findings: %s)" % (label, must_say, "; ".join(errs[:3])))

    screen, path = readme_screen()
    expect("the pipeline README's screen, as a complete pipeline run", screen, True, "pipeline", True)
    expect("the pipeline README's screen, as a download", screen, True)
    expect("a frame of 80 columns from the template", NARROW, True)
    expect("the 14:48 frame of the incident", NOT_THE_FORMAT_1, False, must_say="title row")
    expect("the 15:09 frame of the incident", NOT_THE_FORMAT_2, False, must_say="STEP row is missing")
    lines = screen.split("\n")
    step = [k for k, x in enumerate(lines) if x.startswith("STEP     ")][0]
    expect("the screen without its STEP row", "\n".join(lines[:step] + lines[step + 1:]), False, must_say="STEP row is missing")
    expect("the screen with # bars", screen.replace("█", "#").replace("░", "-"), False, must_say="THIS STEP row")
    hdr = lines.index(GROUPS_HDR)
    expect("the screen with a STAGES part", "\n".join(lines[:hdr] + ["STAGES", "  step2 ████  1/9", ""] + lines[hdr:]),
           False, must_say="does not have")
    expect("the screen without RECORDS", screen.replace("\nRECORDS\n", "\n"), False, must_say="'RECORDS'")
    expect("the screen without its SUMMARY, as a complete pipeline run",
           "\n".join(x for x in lines if "SUMMARY:" not in x and not x.startswith("  until accepted")), False, "pipeline",
           True, must_say="SUMMARY")
    expect("the screen without its job lines, as a pipeline", "\n".join(x for x in lines if "| compute" not in x), False,
           "pipeline", must_say="start (limit")
    expect("an empty capture", "nothing here\n", False, must_say="no dashboard frame")

    # The edges of the ranges. The values are written by the template's own formatters, not typed here.
    t = template_formatters()
    for rx, fn, args in [(HUM, t.human, (0, 1, 1023, 1024, (1 << 20) - 1, 1 << 20, (1 << 30) - 1, 1 << 30, 5 << 40)),
                         (RATE, t.rate_text, (0, 1, 1023, 1024, (1 << 20) - 1, 1 << 20, 9e9)),
                         (DUR, t.clock, (0, 59, 99 * 3600 + 3599, 100 * 3600, 1300 * 3600)),
                         (BAR_REC, lambda f: t.bar(f, 20), (-1, 0, 0.5, 1, 1.7)), (BAR_REC, lambda f: t.bar(f, 10), (0, 0.5, 1)),
                         (BAR_FILE, lambda f: t.bar(f, 16), (0, 0.5, 1)), (BAR_FILE, lambda f: t.bar(f, 6), (0, 0.5, 1))]:
        for a in args:
            if not re.fullmatch(rx, fn(a)):
                bad.append("the template writes %r for %r, and the pattern %s does not take it" % (fn(a), a, rx))
    if t.rate_text(None) != "measuring":
        bad.append("the template's word for a rate not yet measured is %r, not 'measuring'" % t.rate_text(None))
    long_run = screen.replace("elapsed 00:00:02", "elapsed " + t.clock(100 * 3600)).replace("ETA 00:00:01", "ETA " + t.clock(1300 * 3600))
    if long_run.count("elapsed 100:00:00") != 1 or long_run.count("ETA 1300:00:00") != 2:
        bad.append("the README's screen no longer has the elapsed time and the two ETAs that the 100-hour test replaces")
    expect("the screen after 100 hours, with an ETA of 1300 hours", long_run, True, "pipeline", True)
    rec = [k for k, x in enumerate(lines) if x.startswith("  81001 DatasetA")][0]
    many = [lines[rec].replace("81001", str(82000 + j)) for j in range(150)]
    expect("a frame with 150 records", "\n".join(lines[:rec] + many + lines[rec + 1:]), True, "pipeline", True)
    dry_lines = "TOTAL FILES: %d, TOTAL BYTES: %d\nWORKERS: %d, max attempts without progress per file: %d\n" % (2, 9437184, 2, 10)
    expect("the screen after the two lines of a dry run", dry_lines + screen, True, "pipeline", True)
    expect("a start line that does not fit", "TOTAL FILES: two\n" + screen, False, must_say="TOTAL FILES")
    grp = hdr + 1
    expect("a group's bar of 15 characters", "\n".join(lines[:grp] + [lines[grp].replace("░" * 5, "", 1)] + lines[grp + 1:]),
           False, must_say="a GROUPS line")
    fil = [k for k, x in enumerate(lines) if x.startswith("  81001 AAAA1111")][0]
    expect("a file's bar of 12 characters", "\n".join(lines[:fil] + [lines[fil].replace("░" * 4, "", 1)] + lines[fil + 1:]),
           False, must_say="a DOWNLOADING NOW line")
    wide = [x.replace("g1-AAAA1111-verify", "a-long-split-name-AAAA1111-verify")[:79] if " start (limit" in x else x for x in lines]
    if not any(len(x) == 79 and " start (limit" in x for x in wide):
        bad.append("the README's screen no longer has the job line that the cut-line test lengthens to 79 characters")
    expect("a job's start line that the terminal cut at 79 characters", "\n".join(wide), True, "pipeline", True)
    expect("a job's start line without its compute part",
           "\n".join(x.split(" | compute")[0] if " start (limit" in x else x for x in lines), False, "pipeline",
           must_say="start (limit")

    for line in bad:
        print("SELFTEST FAIL: " + line)
    print("selftest: %s" % ("FAILED" if bad else "ok (pass: the template README's screen, a real 80-column frame, and that "
                            "screen after 100 hours, with 150 records, after a dry run's lines and with a cut job line; "
                            "fail: the two frames of the incident, 10 broken copies of the screen and an empty capture; "
                            "the value patterns take what the template's own formatters write at the edges of their ranges)"))
    return 1 if bad else 0


def main(argv):
    if "--selftest" in argv:
        return selftest()
    kind, complete, columns, paths = "download", False, None, []
    it = iter(argv)
    for arg in it:
        if arg in ("-h", "--help"):
            print(__doc__)
            return 0
        if arg == "--kind":
            kind = next(it, "")
            if kind not in ("download", "pipeline"):
                print("--kind is download or pipeline", file=sys.stderr)
                return 2
        elif arg == "--complete":
            complete = True
        elif arg == "--columns":
            try:
                columns = int(next(it, ""))
            except ValueError:
                print("--columns needs a number", file=sys.stderr)
                return 2
        elif arg.startswith("--"):
            print("unknown option %s" % arg, file=sys.stderr)
            return 2
        else:
            paths.append(arg)
    if not paths:
        print(__doc__, file=sys.stderr)
        return 2
    total = 0
    for path in paths:
        try:
            text = sys.stdin.read() if path == "-" else open(path, encoding="utf-8", errors="replace").read()
        except OSError as e:
            print("cannot read %s: %s" % (path, e), file=sys.stderr)
            return 2
        total += report(path, text, kind, complete, columns)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
