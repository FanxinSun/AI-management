#!/usr/bin/env python3
"""Read-only inventory of what each AI agent on this machine holds about a workspace.

The Brand Neutrality Rule (The_Brand_Neutrality_Rule.md, beside this file) asks a
session to look in every brand's store, each in the way that store is keyed, before it
keeps, deletes or reports on AI-related content. A file-name search cannot do that:
Claude Code names its stores after the workspace path, while agy and Codex name
theirs by conversation or thread ID. This script reads each store by content.

Usage:
  ai_content_inventory.py WORKSPACE [WORKSPACE ...] [--keyword WORD ...]
  ai_content_inventory.py --selftest

  WORKSPACE   an absolute project folder; a session counts when its working folder
              is that folder or lies below it (the folder need not exist any more)
  --keyword   also report names and small text records that contain WORD
              (case-insensitive): a wider, noisier net, shown apart

It changes nothing. Exit status: 0 on a normal run (whatever was found), 2 on a usage
error, 1 when --selftest fails. Homes can be overridden with CLAUDE_HOME, CODEX_HOME,
AGY_HOME (default ~/.gemini/antigravity-cli) and CLAUDE_CACHE_HOME.
"""
import json
import os
import sys
import tempfile
from pathlib import Path


def homes():
    home = Path.home()
    cache = os.environ.get("CLAUDE_CACHE_HOME")
    caches = [Path(cache)] if cache else [
        home / ".cache" / "claude-cli-nodejs",                 # Linux / WSL
        home / "Library" / "Caches" / "claude-cli-nodejs",     # macOS
    ]
    return {
        "claude": Path(os.environ.get("CLAUDE_HOME") or home / ".claude"),
        "claude_caches": caches,
        "codex": Path(os.environ.get("CODEX_HOME") or home / ".codex"),
        "agy": Path(os.environ.get("AGY_HOME") or home / ".gemini" / "antigravity-cli"),
    }


def under(path, workspaces):
    """True when path is one of the workspaces or lies below one."""
    if not isinstance(path, str) or not path:
        return False
    p = path.rstrip("/")
    return any(p == w or p.startswith(w + "/") for w in workspaces)


def slug(path):
    """Claude Code's directory name for a working folder: every non-alphanumeric
    character becomes '-' (so /home/u/a_b and /home/u/a-b share one name)."""
    return "".join(c if c.isalnum() else "-" for c in path)


def jsonl(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    yield row
    except OSError:
        return


def names_with(root, words, depth=4):
    """Paths under root whose own name contains a keyword (bounded depth)."""
    hits = []
    if not words or not root.is_dir():
        return hits
    base = len(root.parts)
    for cur, dirs, files in os.walk(root):
        if len(Path(cur).parts) - base >= depth:
            dirs[:] = []
        for name in dirs + files:
            if any(w in name.lower() for w in words):
                hits.append(str(Path(cur) / name))
    return sorted(hits)


def files_mentioning(folder, needles):
    """Small text records (handovers) whose content contains a needle."""
    hits = []
    if not folder.is_dir():
        return hits
    for f in sorted(folder.iterdir()):
        if not f.is_file() or f.stat().st_size > 5_000_000:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace").lower()
        except OSError:
            continue
        if any(n in text for n in needles):
            hits.append(str(f))
    return hits


def claude(h, workspaces, words):
    root = h["claude"]
    slugs = [slug(w) for w in workspaces]
    rows = []

    def by_slug(parent):
        out = []
        if parent.is_dir():
            for d in sorted(parent.iterdir()):
                if d.is_dir() and any(d.name == s or d.name.startswith(s + "-") for s in slugs):
                    out.append(d)
        return out

    proj = by_slug(root / "projects")
    transcripts = sum(1 for d in proj for f in d.glob("*.jsonl"))
    rows.append(("session transcripts", "projects/<workspace path with '-' for '/'>/<session id>.jsonl",
                 "%d folder(s), %d transcript(s)" % (len(proj), transcripts), [str(d) for d in proj]))
    caches = [d for c in h["claude_caches"] for d in by_slug(c)]
    rows.append(("cache", "claude-cli-nodejs/<same folder name>/", "%d folder(s)" % len(caches),
                 [str(d) for d in caches]))
    n = sum(1 for r in jsonl(root / "history.jsonl") if under(r.get("project"), workspaces))
    rows.append(("prompt history", 'history.jsonl, field "project"', "%d line(s)" % n,
                 [str(root / "history.jsonl")] if n else []))
    needles = [w.lower() for w in workspaces] + words
    ho = files_mentioning(root / "handover", needles)
    rows.append(("handovers and reports", "handover/*.md, by content", "%d file(s)" % len(ho), ho))
    return rows, names_with(root, words)


def agy(h, workspaces, words):
    root = h["agy"]
    rows = []
    ids, lines = [], 0
    for r in jsonl(root / "history.jsonl"):
        if under(r.get("workspace"), workspaces):
            lines += 1
            cid = r.get("conversationId")
            if cid and cid not in ids:
                ids.append(cid)
    rows.append(("prompt history", 'history.jsonl, field "workspace"',
                 "%d line(s), %d conversation id(s)" % (lines, len(ids)),
                 [str(root / "history.jsonl")] if lines else []))
    kept = []
    for cid in ids:
        parts = [p for p in (root / "conversations" / (cid + ".db"), root / "brain" / cid,
                             root / "presence" / (cid + ".lock")) if p.exists()]
        kept.append((cid, parts))
    alive = [k for k in kept if k[1]]
    detail = ["%s: %s" % (cid, ", ".join(str(p) for p in parts) if parts else "no files left")
              for cid, parts in kept]
    rows.append(("conversations of those ids", "conversations/<id>.db, brain/<id>/, presence/<id>.lock",
                 "%d of %d id(s) still have files" % (len(alive), len(ids)), detail))
    needles = [w.encode() for w in workspaces]
    dbs = []
    conv = root / "conversations"
    if conv.is_dir():
        for f in sorted(conv.glob("*.db")):
            if f.stem in ids:
                continue
            try:
                data = f.read_bytes()
            except OSError:
                continue
            if any(n in data for n in needles):
                dbs.append(str(f))
    rows.append(("other conversations that name the workspace", "conversations/*.db, by content",
                 "%d database(s)" % len(dbs), dbs))
    return rows, names_with(root, words)


def codex(h, workspaces, words):
    root = h["codex"]
    rows = []
    threads, files = [], []
    sess = root / "sessions"
    if sess.is_dir():
        for f in sorted(sess.rglob("rollout-*.jsonl")):
            try:
                with open(f, "r", encoding="utf-8", errors="replace") as fh:
                    first = json.loads(fh.readline() or "{}")
            except (OSError, ValueError):
                continue
            payload = first.get("payload") if isinstance(first, dict) else None
            if isinstance(payload, dict) and under(payload.get("cwd"), workspaces):
                files.append(str(f))
                tid = payload.get("id") or payload.get("session_id")
                if tid and tid not in threads:
                    threads.append(tid)
    rows.append(("session rollouts", 'sessions/<y>/<m>/<d>/rollout-*-<thread id>.jsonl, "cwd" in line 1',
                 "%d file(s), %d thread id(s)" % (len(files), len(threads)), files))
    idx = sum(1 for r in jsonl(root / "session_index.jsonl") if r.get("id") in threads)
    rows.append(("thread titles", 'session_index.jsonl, field "id"', "%d line(s)" % idx,
                 [str(root / "session_index.jsonl")] if idx else []))
    needles = [w.lower() for w in workspaces] + words
    n = 0
    for r in jsonl(root / "history.jsonl"):
        text = str(r.get("text", "")).lower()
        if r.get("session_id") in threads or any(x in text for x in needles):
            n += 1
    rows.append(("prompt history", 'history.jsonl, "session_id" of those threads or text',
                 "%d line(s)" % n, [str(root / "history.jsonl")] if n else []))
    ho = files_mentioning(root / "handover", needles)
    rows.append(("handovers and reports", "handover/*, by content", "%d file(s)" % len(ho), ho))
    return rows, names_with(root, words)


BRANDS = (("Claude Code", "claude", claude), ("Antigravity (agy)", "agy", agy), ("Codex", "codex", codex))


def inventory(workspaces, words):
    h = homes()
    out = []
    for label, key, fn in BRANDS:
        root = h[key]
        if not root.is_dir():
            out.append((label, root, None, []))
            continue
        rows, named = fn(h, workspaces, words)
        out.append((label, root, rows, named))
    return out


def report(workspaces, words, verbose=True):
    print("AI content inventory (read-only). Workspaces: %s" % ", ".join(workspaces)
          + ("; keywords: %s" % ", ".join(words) if words else ""))
    for label, root, rows, named in inventory(workspaces, words):
        print("\n== %s  (%s)" % (label, root))
        if rows is None:
            print("   store not present on this machine: not looked in")
            continue
        for what, keyed, count, paths in rows:
            print("   %-44s %s" % (what + ":", count))
            print("   %-44s keyed by %s" % ("", keyed))
            if verbose:
                for p in paths[:12]:
                    print("       " + p)
                if len(paths) > 12:
                    print("       ... and %d more" % (len(paths) - 12))
        if words:
            print("   %-44s %d path(s)" % ("names containing a keyword:", len(named)))
            if verbose:
                for p in named[:12]:
                    print("       " + p)
    print("\nAny other agent on this machine (Gemini CLI, a new tool) is not covered here: "
          "find its store and how it is keyed, and say so in the report.")


def selftest():
    """Build one fake store per brand and check that each is found by content."""
    ws = "/work/alpha"
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        c, a, x, cache = t / "claude", t / "agy", t / "codex", t / "cache"
        (c / "projects" / "-work-alpha").mkdir(parents=True)
        (c / "projects" / "-work-alpha" / "s1.jsonl").write_text("{}\n")
        (c / "projects" / "-work-other").mkdir()
        (c / "handover").mkdir()
        (c / "handover" / "h.md").write_text("see /work/alpha\n")
        (c / "history.jsonl").write_text(
            json.dumps({"project": "/work/alpha"}) + "\n" + json.dumps({"project": "/work/alphabet"}) + "\n")
        (cache / "-work-alpha").mkdir(parents=True)
        for d in ("conversations", "brain/1111", "presence"):
            (a / d).mkdir(parents=True)
        (a / "conversations" / "1111.db").write_bytes(b"x")
        (a / "conversations" / "2222.db").write_bytes(b"... /work/alpha ...")
        (a / "history.jsonl").write_text(
            json.dumps({"workspace": "/work/alpha/sub", "conversationId": "1111"}) + "\n"
            + json.dumps({"workspace": "/work/alpha", "conversationId": "3333"}) + "\n"
            + json.dumps({"workspace": "/work/beta", "conversationId": "4444"}) + "\n")
        (x / "sessions" / "2026" / "01" / "01").mkdir(parents=True)
        (x / "sessions" / "2026" / "01" / "01" / "rollout-a-t1.jsonl").write_text(
            json.dumps({"type": "session_meta", "payload": {"id": "t1", "cwd": "/work/alpha"}}) + "\n")
        (x / "sessions" / "2026" / "01" / "01" / "rollout-b-t2.jsonl").write_text(
            json.dumps({"type": "session_meta", "payload": {"id": "t2", "cwd": "/work/beta"}}) + "\n")
        (x / "session_index.jsonl").write_text(json.dumps({"id": "t1", "thread_name": "n"}) + "\n")
        (x / "history.jsonl").write_text(json.dumps({"session_id": "t1", "text": "hi"}) + "\n")
        old = {k: os.environ.get(k) for k in ("CLAUDE_HOME", "AGY_HOME", "CODEX_HOME", "CLAUDE_CACHE_HOME")}
        os.environ.update(CLAUDE_HOME=str(c), AGY_HOME=str(a), CODEX_HOME=str(x), CLAUDE_CACHE_HOME=str(cache))
        try:
            got = {label: {r[0]: r[2] for r in rows} for label, _, rows, _ in inventory([ws], [])}
            # the same stores, asked about a workspace nobody used: everything must read zero
            none = {label: {r[0]: r[2] for r in rows} for label, _, rows, _ in inventory(["/work/zzz"], [])}
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
    want = {
        "Claude Code": {"session transcripts": "1 folder(s), 1 transcript(s)", "cache": "1 folder(s)",
                        "prompt history": "1 line(s)", "handovers and reports": "1 file(s)"},
        "Antigravity (agy)": {"prompt history": "2 line(s), 2 conversation id(s)",
                              "conversations of those ids": "1 of 2 id(s) still have files",
                              "other conversations that name the workspace": "1 database(s)"},
        "Codex": {"session rollouts": "1 file(s), 1 thread id(s)", "thread titles": "1 line(s)",
                  "prompt history": "1 line(s)", "handovers and reports": "0 file(s)"},
    }
    bad = []
    for brand, rows in want.items():
        for what, count in rows.items():
            if got.get(brand, {}).get(what) != count:
                bad.append("%s / %s: expected %r, got %r" % (brand, what, count, got.get(brand, {}).get(what)))
    for brand, rows in none.items():
        for what, count in rows.items():
            if any(ch.isdigit() and ch != "0" for ch in count):
                bad.append("%s / %s: expected nothing for an unused workspace, got %r" % (brand, what, count))
    if under("/work/alphabet", [ws]) or not under("/work/alpha/sub", [ws]):
        bad.append("under(): a sibling folder matched, or a subfolder did not")
    for line in bad:
        print("SELFTEST FAIL: " + line)
    print("selftest: %s" % ("FAILED" if bad else "ok (3 brands, found by content, nothing for an unused workspace)"))
    return 1 if bad else 0


def main(argv):
    if "--selftest" in argv:
        return selftest()
    workspaces, words, quiet = [], [], False
    it = iter(argv)
    for arg in it:
        if arg in ("-h", "--help"):
            print(__doc__)
            return 0
        if arg == "--keyword":
            w = next(it, None)
            if not w:
                print("--keyword needs a word", file=sys.stderr)
                return 2
            words.append(w.lower())
        elif arg == "--counts":
            quiet = True
        elif arg.startswith("/"):
            workspaces.append(arg.rstrip("/") or "/")
        else:
            print("not an absolute workspace path: %s (use --keyword %s for a word)" % (arg, arg), file=sys.stderr)
            return 2
    if not workspaces:
        print(__doc__, file=sys.stderr)
        return 2
    report(workspaces, words, verbose=not quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
