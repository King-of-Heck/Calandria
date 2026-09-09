"""The local HTTP server: the viewer's static files, the JSON API over one Session, the idle
watchdog and the quit route. See the package docstring for the API."""
from __future__ import annotations

import base64
import json
import logging
import os
import threading
import time
import traceback
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from urllib.parse import parse_qs, urlsplit

from .. import __version__
from .session import BadDocument, Session, check_render, parse_options

STATIC = {"index.html": "text/html; charset=utf-8", "style.css": "text/css; charset=utf-8",
          "app.js": "text/javascript; charset=utf-8", "changes.js": "text/javascript; charset=utf-8"}
MAX_BODY = 64 * 1024 * 1024
DRAIN_CAP = 256 * 1024 * 1024
DEFAULT_IDLE = 300.0
HOST = "127.0.0.1"


class _Bad(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def _static_bytes(name: str) -> bytes | None:
    if name not in STATIC:
        return None
    path = resources.files("calandria.viewer").joinpath(name)
    return path.read_bytes() if path.is_file() else None


def _flag(query: dict, key: str, default: bool) -> bool:
    v = query.get(key, [None])[0]
    if v is None:
        return default
    if v in ("0", "1"):
        return v == "1"
    raise _Bad(400, f"{key} must be 0 or 1")


def _file(body: dict, key: str) -> tuple[str, bytes]:
    f = body.get(key)
    if not isinstance(f, dict):
        raise _Bad(400, "both files are required (a and b)")
    name = f.get("name")
    if not isinstance(name, str) or not name.strip():
        raise _Bad(400, "a file name is required")
    name = os.path.basename(name.replace("\\", "/")).strip()
    if not name:
        raise _Bad(400, "a file name is required")
    try:
        data = base64.b64decode(f.get("data", ""), validate=True)
    except (ValueError, TypeError):
        raise _Bad(400, f"{key}: the file data is not base64") from None
    return name, data


def _style(body: dict) -> tuple[str, bool]:
    render_set = body.get("render_set", "Standard")
    if not isinstance(render_set, str):
        raise _Bad(400, "render_set must be a string")
    check_render(render_set)
    change_bars = body.get("change_bars", True)
    if not isinstance(change_bars, bool):
        raise _Bad(400, "change_bars must be true or false")
    return render_set, change_bars


class Handler(BaseHTTPRequestHandler):
    server_version = "Calandria/" + __version__
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        if self.server.verbose:
            super().log_message(fmt, *args)

    # -- responses ----------------------------------------------------------------------------
    def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, status: int = 200) -> None:
        self._send(status, json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8")

    def _error(self, status: int, message: str) -> None:
        if status == 413:
            self.close_connection = True        # the unread body would poison a kept-alive socket
            # A client still writing an oversized body can have the OS abort the connection
            # before it gets to read our 413, if we close the socket without reading anything;
            # draining the declared body first lets the write finish so the client sees the 413.
            raw = self.headers.get("Content-Length")
            try:
                remaining = int(raw) if raw is not None else 0
            except ValueError:
                remaining = -1
            if 0 <= remaining <= DRAIN_CAP:
                try:
                    while remaining > 0:
                        chunk = self.rfile.read(min(remaining, 1 << 20))
                        if not chunk:
                            break
                        remaining -= len(chunk)
                except OSError:
                    pass
                self._consumed = True
        elif not self._consumed:
            # an early error (404/405/400 before _body()/_drain() ran) left a declared body
            # unread; either drain it or close the connection so the next request on this
            # kept-alive socket doesn't get misparsed.
            try:
                length = self._length()
            except _Bad:
                self.close_connection = True
            else:
                if length:
                    try:
                        self.rfile.read(length)
                    except OSError:
                        self.close_connection = True
                self._consumed = True
        self._json({"error": message}, status)

    def _length(self) -> int:
        raw = self.headers.get("Content-Length")
        if raw is None:
            return 0
        try:
            length = int(raw)
        except ValueError:
            raise _Bad(400, "bad Content-Length") from None
        if length < 0:
            raise _Bad(400, "bad Content-Length")
        if length > MAX_BODY:
            raise _Bad(413, f"request body over {MAX_BODY} bytes")
        return length

    def _drain(self) -> None:
        """Read and ignore a small body (a browser POST with no payload sends Content-Length: 0)."""
        length = self._length()
        if length:
            self.rfile.read(length)
        self._consumed = True

    def _body(self) -> dict:
        length = self._length()
        raw = self.rfile.read(length) if length else b""
        self._consumed = True
        try:
            obj = json.loads(raw.decode("utf-8")) if raw else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise _Bad(400, "the request body is not JSON") from None
        if not isinstance(obj, dict):
            raise _Bad(400, "expected a JSON object")
        return obj

    # -- routing ------------------------------------------------------------------------------
    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def _route(self, method: str) -> None:
        session: Session = self.server.session
        session.touch()
        self._consumed = False
        parts = urlsplit(self.path)
        path, query = parts.path, parse_qs(parts.query)
        try:
            if path == "/" or path.startswith("/static/"):
                if method != "GET":
                    raise _Bad(405, "method not allowed")
                name = "index.html" if path == "/" else path[len("/static/"):]
                data = _static_bytes(name)
                if data is None:
                    raise _Bad(404, "not found")
                self._send(200, data, STATIC[name])
                return
            if not path.startswith("/api/"):
                raise _Bad(404, "not found")
            route = path[len("/api/"):]
            allowed = {"state": "GET", "pages": "GET", "pdf": "GET", "compare": "POST", "layout": "POST",
                       "ping": "POST", "quit": "POST"}.get(route)
            if allowed is None:
                raise _Bad(404, "not found")
            if allowed != method:
                raise _Bad(405, "method not allowed")
            getattr(self, "_api_" + route)(session, query)
        except _Bad as e:
            self._error(e.status, e.message)
        except (BadDocument, ValueError) as e:
            self._error(400, str(e))
        except LookupError as e:
            self._error(409, str(e))
        except Exception as e:
            self.close_connection = True
            if self.server.verbose:
                self.log_error("%s", traceback.format_exc())
            self._json({"error": f"internal error: {type(e).__name__}"}, 500)

    # -- the API --------------------------------------------------------------------------------
    def _api_state(self, session, query):
        with session.lock:
            self._json(session.state())

    def _api_ping(self, session, query):
        self._drain()
        self._json({"ok": True})

    def _api_quit(self, session, query):
        self._drain()
        self._json({"ok": True})
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def _api_compare(self, session, query):
        body = self._body()
        a_name, a_data = _file(body, "a")
        b_name, b_data = _file(body, "b")
        render_set, change_bars = _style(body)
        with session.lock:
            options = parse_options(body.get("options", {}), session.options)
            session.load(a_name, a_data, b_name, b_data, options)
            self._json(session.payload(render_set, change_bars))

    def _api_layout(self, session, query):
        body = self._body()
        if "options" not in body:
            raise _Bad(400, "options are required")
        render_set, change_bars = _style(body)
        with session.lock:
            options = parse_options(body["options"], session.options)
            session.relayout(options)
            self._json(session.payload(render_set, change_bars))

    def _api_pages(self, session, query):
        rs = query.get("render_set", ["Standard"])[0]
        bars = _flag(query, "change_bars", True)
        with session.lock:
            self._json(session.pages(rs, bars))

    def _api_pdf(self, session, query):
        rs = query.get("render_set", ["Standard"])[0]
        bars = _flag(query, "change_bars", True)
        report = query.get("report", ["last"])[0]
        check_render(rs, report)
        with session.lock:
            data, name = session.pdf(rs, bars, report)
        self._send(200, data, "application/pdf", {"Content-Disposition": f'attachment; filename="{name}"'})


def make_server(session: Session, host: str = HOST, port: int = 0, verbose: bool = False) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    server.session = session
    server.verbose = verbose
    server.stopped = False
    return server


def url_of(server) -> str:
    host, port = server.server_address[:2]
    return f"http://{host}:{port}/"


def _watchdog(server, idle: float) -> None:
    step = max(0.05, min(1.0, idle / 4))
    while not server.stopped:
        time.sleep(step)
        if not server.stopped and time.monotonic() - server.session.last_seen > idle:
            server.shutdown()
            return


def run(server, idle: float = 0.0) -> None:
    """Serve until /api/quit, the idle watchdog (idle > 0) or shutdown() from another thread."""
    if idle > 0:
        threading.Thread(target=_watchdog, args=(server, idle), daemon=True).start()
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        server.stopped = True
        server.server_close()


def serve(port: int = 0, open_browser: bool = True, idle: float = DEFAULT_IDLE, verbose: bool = False,
          fonts=None, ready=None) -> None:
    logging.getLogger("fontTools").setLevel(logging.ERROR)     # "'created' timestamp seems very low"
    session = Session(fonts=fonts)
    server = make_server(session, port=port, verbose=verbose)
    url = url_of(server)
    if ready is not None:
        ready(url)
    if open_browser:
        webbrowser.open(url)
    run(server, idle)
