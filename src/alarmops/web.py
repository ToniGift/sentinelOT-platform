"""Small web front for the live deployment (Cloud Run). SIMULATION ONLY.

    GET  /                     the plain-English explainer page, with an interactive lab
    GET  /api/replay           measured replay results as JSON (summary; no raw series)
    GET  /api/lab/baseline     replay the current rules
    GET  /api/lab/compare?...  replay edited tank limits and apply the gate
    GET  /api/lab/monitor?log= drift check on a bundled simulated log
    POST /api/lab/scan         scan pasted text for credentials (never echoed back)
    GET  /healthz              health check

The lab runs a fixed set of safe functions: no shell, no file access beyond the bundled
data. Inputs are range-checked, request bodies are capped, work is concurrency-limited,
and nothing is stored. Standard library only.
"""
from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlsplit

from .explainer import render_explainer
from .lab import MAX_TEXT, Lab, LabError
from .labpage import LAB_JS
from .scenarios import build_report

HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; script-src 'self'; connect-src 'self'; "
        "img-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"),
    "Cache-Control": "no-store",
}
MAX_BODY = MAX_TEXT * 4 + 100     # JSON escaping can inflate the text; cap before reading


def make_handler(report: dict, lab: Lab | None = None):
    lab = lab or Lab()
    slots = threading.BoundedSemaphore(8)          # at most 8 lab runs at once
    page = render_explainer(report, interactive=True).encode("utf-8")
    js = LAB_JS.encode("utf-8")
    api = {k: v for k, v in report.items() if k not in ("series", "tank_faults")}
    api_body = (json.dumps(api, indent=2) + "\n").encode("utf-8")
    health = b'{"status":"ok","simulation":true}\n'

    class Handler(BaseHTTPRequestHandler):
        server_version = "AlarmOps"
        sys_version = ""

        def _send(self, code: int, body: bytes, ctype: str, head_only: bool = False):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for k, v in HEADERS.items():
                self.send_header(k, v)
            self.end_headers()
            if not head_only:
                self.wfile.write(body)

        def _json(self, code: int, obj: dict):
            self._send(code, (json.dumps(obj) + "\n").encode("utf-8"), "application/json")

        def _lab(self, fn, *args):
            if not slots.acquire(blocking=False):
                return self._json(503, {"error": "busy, try again in a moment"})
            try:
                self._json(200, fn(*args))
            except LabError as exc:
                self._json(400, {"error": str(exc)})
            finally:
                slots.release()

        def _route(self, head_only: bool):
            parts = urlsplit(self.path)
            path = parts.path
            q = dict(parse_qsl(parts.query, keep_blank_values=True)[:20])
            if path in ("/", "/index.html"):
                self._send(200, page, "text/html; charset=utf-8", head_only)
            elif path == "/lab.js":
                self._send(200, js, "text/javascript; charset=utf-8", head_only)
            elif path == "/api/replay":
                self._send(200, api_body, "application/json", head_only)
            elif path == "/healthz":
                self._send(200, health, "application/json", head_only)
            elif path == "/api/lab/baseline" and not head_only:
                self._lab(lab.baseline)
            elif path == "/api/lab/compare" and not head_only:
                self._lab(lab.compare, q)
            elif path == "/api/lab/monitor" and not head_only:
                self._lab(lab.monitor, q.get("log", ""))
            else:
                self._send(404, b"not found\n", "text/plain; charset=utf-8", head_only)

        def do_GET(self):
            self._route(False)

        def do_HEAD(self):
            self._route(True)

        def _body(self) -> bytes | None:
            """Read the request body, or None if it is missing, malformed or too large.

            A small body is always consumed before replying: closing a socket with unread
            data can reset the connection on some platforms and hide the response."""
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return None
            if not 0 < length <= MAX_BODY:
                return None
            return self.rfile.read(length)

        def do_POST(self):
            body = self._body()
            if urlsplit(self.path).path != "/api/lab/scan":
                return self._reject()
            if body is None:
                return self._json(400, {"error": "request body missing or too large"})
            try:
                text = json.loads(body).get("text", "")
            except (ValueError, AttributeError):
                return self._json(400, {"error": 'body must be JSON like {"text": "..."}'})
            self._lab(lab.scan, text)

        def _reject(self):
            self._send(405, b"method not allowed\n", "text/plain; charset=utf-8")

        def do_PUT(self):
            self._body()
            self._reject()

        do_DELETE = do_PATCH = do_PUT

        def log_message(self, fmt, *args):   # request lines only (Cloud Run logs); bodies are never logged
            super().log_message(fmt, *args)

    return Handler


def serve(host: str = "0.0.0.0", port: int | None = None) -> ThreadingHTTPServer:
    port = int(os.environ.get("PORT", "8080")) if port is None else port
    return ThreadingHTTPServer((host, port), make_handler(build_report()))


def main() -> int:
    server = serve()
    print(f"AlarmOps (simulation) listening on {server.server_address[0]}:{server.server_address[1]}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
