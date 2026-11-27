#!/usr/bin/env python3
"""Verify a downloaded list independently of the downloader (template: general/templates/chunked-pipeline/).
This is e7's tools/s2_verify.py of the user's project e7-upsilon-omega (sha256 1b00e420..., pinned in e7's
tools/s6_all_in_one.pins); the only change: e7's check that a file starts with the 4 bytes b"root" is the constant MAGIC
(None: no such check; then the line still shows the first 4 bytes and OK).
Reads each listed file once (size, adler32, sha256, first 4 bytes); compares with the list (size, adler32), with
DEST/<recid>/SHA256SUMS and with DEST/fetch-log.tsv. Nothing is parsed or changed.
usage: verify_download.py LIST.tsv DEST        exit 0 if every check passes"""
import hashlib
import os
import sys
import zlib

MAGIC = None   # PROJECT: the first 4 bytes every file must have, or None (e7: b"root", a ROOT file)


def main(a):
    lst, dest = a
    rows = [l.split("\t") for l in open(lst, encoding="utf-8").read().split("\n")[1:] if l.strip()]
    fl = {}
    p = os.path.join(dest, "fetch-log.tsv")
    if os.path.exists(p):
        for l in open(p, encoding="utf-8").read().split("\n")[1:]:
            if l.strip():
                c = l.split("\t"); fl[(c[0], c[1])] = c
    bad = 0
    for recid, key, size, adler, url in rows:
        path = os.path.join(dest, recid, key)
        sums = {}
        sp = os.path.join(dest, recid, "SHA256SUMS")
        if os.path.exists(sp):
            for l in open(sp, encoding="utf-8").read().split("\n"):
                if l.strip():
                    h, _, n = l.partition("  "); sums[n] = h
        ad, h, n = 1, hashlib.sha256(), 0
        with open(path, "rb") as f:
            magic = f.read(4); f.seek(0)
            for b in iter(lambda: f.read(1 << 22), b""):
                ad = zlib.adler32(b, ad); h.update(b); n += len(b)
        ok_size = n == int(size)
        ok_ad = "%08x" % ad == adler
        ok_sum = sums.get(key) == h.hexdigest()
        c = fl.get((recid, key))
        ok_fl = c is not None and c[2] == size and c[3] == adler and c[4] == h.hexdigest()
        ok_magic = MAGIC is None or magic == MAGIC
        good = ok_size and ok_ad and ok_sum and ok_fl and ok_magic
        bad += 0 if good else 1
        print("%s/%s: size %d (list %s) %s; adler32 %08x (list %s) %s; sha256 %s; SHA256SUMS %s; fetch-log %s; magic %r %s -> %s" % (
            recid, key, n, size, "OK" if ok_size else "BAD", ad, adler, "OK" if ok_ad else "BAD", h.hexdigest(),
            "OK" if ok_sum else "BAD", "OK" if ok_fl else "BAD", magic, "OK" if ok_magic else "BAD", "PASS" if good else "FAIL"))
    print("files %d, failed %d" % (len(rows), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
