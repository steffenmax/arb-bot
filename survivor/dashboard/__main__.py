"""Serve the survivor dashboard: python3 -m survivor.dashboard [--port 8765] [--host 127.0.0.1]"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import threading
import traceback
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from . import config as cfgmod
from . import service

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
VERSION = "1.0.0"
_lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    server_version = "SurvivorDashboard/" + VERSION

    def log_message(self, fmt, *args):  # quieter default logging
        if self.server.verbose:  # type: ignore[attr-defined]
            super().log_message(fmt, *args)

    # ---- helpers ----------------------------------------------------------
    def _json(self, status: int, payload) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        if "chunked" in (self.headers.get("Transfer-Encoding") or "").lower():
            raise cfgmod.ConfigError("chunked request bodies are not supported; send Content-Length")
        length = max(0, int(self.headers.get("Content-Length") or 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode() or "{}")
        except json.JSONDecodeError as exc:
            raise cfgmod.ConfigError(f"invalid JSON body: {exc}") from exc

    def _static(self, path: str) -> None:
        rel = path.lstrip("/") or "index.html"
        full = os.path.normpath(os.path.join(STATIC_DIR, rel))
        if not full.startswith(STATIC_DIR) or not os.path.isfile(full):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        ctype, _ = mimetypes.guess_type(full)
        if full.endswith(".js"):
            ctype = "text/javascript"
        with open(full, "rb") as fh:
            body = fh.read()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    # ---- routes -----------------------------------------------------------
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            self._json(200, {"ok": True, "version": VERSION})
        elif path == "/api/config":
            self._json(200, cfgmod.load())
        elif path.startswith("/api/"):
            self._json(404, {"error": "not found"})
        else:
            self._static(path)

    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/config":
            self._json(404, {"error": "not found"})
            return
        try:
            self._json(200, cfgmod.save(self._read_json()))
        except cfgmod.ConfigError as exc:
            self._json(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._json(500, {"error": f"{type(exc).__name__}: {exc}"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/dashboard":
                cfg = cfgmod.normalize(self._read_json())
                with _lock:
                    payload = service.build_dashboard(cfg)
                self._json(200, payload)
            elif path == "/api/refresh":
                with _lock:
                    ages, warns = service.refresh_all()
                self._json(200, {"ok": not warns, "dataAge": ages, "warnings": warns})
            else:
                self._json(404, {"error": "not found"})
        except cfgmod.ConfigError as exc:
            self._json(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001 - surface to the UI
            traceback.print_exc()
            self._json(500, {"error": f"{type(exc).__name__}: {exc}"})


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python3 -m survivor.dashboard")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--open", action="store_true", help="open the dashboard in a browser")
    ap.add_argument("--verbose", action="store_true", help="log every request")
    args = ap.parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.verbose = args.verbose  # type: ignore[attr-defined]
    url = f"http://{args.host}:{args.port}/"
    print(f"Survivor dashboard at {url}  (Ctrl+C to stop)")
    if args.open:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
        sys.exit(0)


if __name__ == "__main__":
    main()
