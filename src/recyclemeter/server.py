"""Local development server: builds dist/ and serves it, rebuilding when sources change."""

from __future__ import annotations

import functools
import http.server
import socketserver
import threading
import time
from pathlib import Path

from .build import DATA, DIST, ROOT, STATIC, TEMPLATES, build


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".json": "application/json",
        ".css": "text/css",
        ".svg": "image/svg+xml",
    }

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        super().end_headers()

    def send_error(self, code, message=None, explain=None):
        if code == 404 and (DIST / "404.html").exists():
            body = (DIST / "404.html").read_bytes()
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
            return
        super().send_error(code, message, explain)

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()}  {fmt % args}")


def _snapshot() -> float:
    newest = 0.0
    for base in (TEMPLATES, STATIC, DATA, ROOT / "src"):
        for p in Path(base).rglob("*"):
            if p.is_file():
                newest = max(newest, p.stat().st_mtime)
    return newest


def _watch(stop: threading.Event) -> None:
    seen = _snapshot()
    while not stop.wait(1.0):
        now = _snapshot()
        if now > seen:
            seen = now
            try:
                build()
                print("  rebuilt dist/")
            except Exception as exc:  # keep serving the last good build
                print(f"  rebuild failed: {exc}")


def serve(host: str = "127.0.0.1", port: int = 8000, watch: bool = True) -> None:
    build()
    stop = threading.Event()
    if watch:
        threading.Thread(target=_watch, args=(stop,), daemon=True).start()
    handler = functools.partial(Handler, directory=str(DIST))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer((host, port), handler) as httpd:
        print(f"Serving on http://{host}:{port}  (Ctrl+C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")
        finally:
            stop.set()
