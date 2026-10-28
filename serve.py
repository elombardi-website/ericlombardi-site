#!/usr/bin/env python3
"""Local preview server for the built site. Serves docs/ (or --dir) on port 8790 (or --port).
Understands both the plain build (links like /writing/) and the GitHub Pages test build
(links like /ericlombardi-site/writing/), so whatever was built last works at
http://localhost:8790/ . Standard library only; works with no internet connection.
"""
import argparse
import http.server
import pathlib
import sys
import urllib.parse

ap = argparse.ArgumentParser()
ap.add_argument("--dir", default=str(pathlib.Path(__file__).resolve().parent / "docs"))
ap.add_argument("--port", type=int, default=8790)
ap.add_argument("--prefix", default="/ericlombardi-site")
args = ap.parse_args()
ROOT = pathlib.Path(args.dir).resolve()


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def translate_path(self, path):
        path = urllib.parse.urlparse(path).path
        if path == args.prefix or path.startswith(args.prefix + "/"):
            path = path[len(args.prefix):] or "/"
        return super().translate_path(path)

    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        if p == args.prefix:
            self.send_response(301)
            self.send_header("Location", args.prefix + "/")
            self.end_headers()
            return
        full = pathlib.Path(self.translate_path(self.path))
        if not full.exists() and not full.suffix and (ROOT / "404.html").exists():
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write((ROOT / "404.html").read_bytes())
            return
        return super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *a):
        sys.stderr.write("%s %s\n" % (self.log_date_time_string(), fmt % a))


print(f"serving {ROOT} at http://localhost:{args.port}/ (also under {args.prefix}/)", flush=True)
http.server.ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
