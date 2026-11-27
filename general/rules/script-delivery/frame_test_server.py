#!/usr/bin/env python3
"""A local test server for capturing the screen of a download (The Script Delivery Rule, beside this file).

It makes test files (two, or more with --files), writes a file list in the templates' format, and serves the files
slowly on 127.0.0.1, so that a downloader built from general/templates/download-ui/ draws several frames before it
ends. It is a test fixture: nothing that a user runs is built from it.

Usage:
  frame_test_server.py DIR [--port N] [--kib N] [--files N] [--magic TEXT]

  DIR      a folder that does not exist yet, or is empty. The server writes:
             DIR/www/AAAA1111-a.bin   6291456 bytes, record 81001
             DIR/www/BBBB2222-b.bin   3145728 bytes, record 81002
             DIR/www/C0000001-c.bin   ... with --files N above 2: N - 2 more files of 1, 2 or 3 MiB, C0000001-c.bin
                                      to C<N-2, 7 digits>-c.bin, in records 81001 and 81002 by turns
             DIR/files-tst1.tsv       the list: a header line "recid key size adler32 url" (tab-separated), then
                                      one line per file; adler32 is 8 hexadecimal digits
           The list is written as DIR/files-tst1.tsv.partial and renamed when the files are ready and the port is
           open, so the list's presence means that a download can start.
  --port   the port on 127.0.0.1 (default 18765); the list's URLs name it
  --kib    KiB per second on each connection (default 700: the two files take about 9 s and 5 s)
  --files  how many files the list has, 2 to 999 (default 2); a pipeline capture needs more files than workers
  --magic  the files begin with these characters (for a project whose verify step checks a file's first bytes)

It prints the list's path and one "serving" line, and serves until it is killed (kill <pid>, or Ctrl-C).
Exit status: 0 after Ctrl-C; 2 on a usage error, when DIR holds something, or when the port is taken.
"""
import http.server
import os
import re
import sys
import time
import zlib

FILES = (("AAAA1111-a.bin", 81001, 6 << 20), ("BBBB2222-b.bin", 81002, 3 << 20))


def all_files(n):
    """The two files, then n - 2 more: C0000001-c.bin, ... of 1, 2 or 3 MiB, in records 81001 and 81002 by turns."""
    extra = [("C%07d-c.bin" % k, 81001 + (k - 1) % 2, (1 + (k - 1) % 3) << 20) for k in range(1, n - 1)]
    return list(FILES) + extra
LIST = "files-tst1.tsv"


def handler(www, bytes_per_second):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            path = os.path.join(www, os.path.basename(self.path))
            if not os.path.isfile(path):
                self.send_error(404)
                return
            size = os.path.getsize(path)
            start, stop = 0, size
            m = re.match(r"bytes=(\d+)-(\d*)$", self.headers.get("Range", ""))
            if m:
                start = min(int(m.group(1)), size)
                stop = min(int(m.group(2)) + 1, size) if m.group(2) else size
                self.send_response(206)
                self.send_header("Content-Range", "bytes %d-%d/%d" % (start, stop - 1, size))
            else:
                self.send_response(200)
            self.send_header("Content-Length", str(max(0, stop - start)))
            self.end_headers()
            with open(path, "rb") as f:
                f.seek(start)
                left = stop - start
                while left > 0:
                    block = f.read(min(left, max(1, bytes_per_second // 10)))
                    if not block:
                        break
                    try:
                        self.wfile.write(block)
                        self.wfile.flush()
                    except OSError:
                        return
                    left -= len(block)
                    time.sleep(0.1)
    return Handler


def main(argv):
    port, kib, nfiles, magic, paths = 18765, 700, 2, b"", []
    it = iter(argv)
    for arg in it:
        if arg in ("-h", "--help"):
            print(__doc__)
            return 0
        if arg in ("--port", "--kib", "--files"):
            try:
                value = int(next(it, ""))
            except ValueError:
                print("%s needs a number" % arg, file=sys.stderr)
                return 2
            if value <= 0:
                print("%s needs a number above 0" % arg, file=sys.stderr)
                return 2
            if arg == "--files" and not 2 <= value <= 999:
                print("--files needs a number from 2 to 999", file=sys.stderr)
                return 2
            if arg == "--port":
                port = value
            elif arg == "--kib":
                kib = value
            else:
                nfiles = value
        elif arg == "--magic":
            magic = next(it, "").encode("utf-8")
        elif arg.startswith("--"):
            print("unknown option %s" % arg, file=sys.stderr)
            return 2
        else:
            paths.append(arg)
    if len(paths) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    root = os.path.abspath(paths[0])
    if os.path.exists(root) and (not os.path.isdir(root) or os.listdir(root)):
        print("refused: %s exists and is not an empty folder" % root, file=sys.stderr)
        return 2
    www = os.path.join(root, "www")
    try:
        server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler(www, kib * 1024))
    except OSError as e:
        print("cannot open 127.0.0.1:%d: %s" % (port, e), file=sys.stderr)
        return 2
    os.makedirs(www)
    rows = ["recid\tkey\tsize\tadler32\turl"]
    for key, recid, size in all_files(nfiles):
        data = magic + os.urandom(size - len(magic))
        with open(os.path.join(www, key), "wb") as f:
            f.write(data)
        rows.append("%d\t%s\t%d\t%08x\thttp://127.0.0.1:%d/%s" % (recid, key, size, zlib.adler32(data) & 0xffffffff, port, key))
    path = os.path.join(root, LIST)
    with open(path + ".partial", "w", encoding="utf-8") as f:
        f.write("\n".join(rows) + "\n")
    os.replace(path + ".partial", path)
    print("list: %s" % path)
    print("serving %s on http://127.0.0.1:%d at %d KiB/s per connection; kill %d to stop" % (www, port, kib, os.getpid()), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
