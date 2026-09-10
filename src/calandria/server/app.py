"""The local HTTP server: the viewer's static files, the JSON API over one Session, the idle
watchdog and the quit route. See the package docstring for the API."""
from __future__ import annotations

import base64
import json
import logging
import os
import sys
import threading
import time
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from urllib.parse import parse_qs, quote, urlsplit

from .. import __version__
from .session import BadRequest, NoComparison, Session, check_render, parse_options
from .launch import open_viewer

STATIC = {"index.html": "text/html; charset=utf-8", "style.css": "text/css; charset=utf-8",
          "app.js": "text/javascript; charset=utf-8", "changes.js": "text/javascript; charset=utf-8",
          "sources.js": "text/javascript; charset=utf-8"}
MAX_BODY = 64 * 1024 * 1024
DRAIN_CAP = 256 * 1024 * 1024
DEFAULT_IDLE = 8.0          # seconds without a request, once the page has been seen (it pings every 2 s)
DEFAULT_GRACE = 120.0       # seconds allowed before the first request (a cold Edge start)
HIDDEN_IDLE = 90.0          # above Chromium's one-wake-per-minute floor for a page hidden over five minutes
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


def _disposition(name: str) -> str:
    """A Content-Disposition value for a download name that came from the uploaded file names.

    Headers are latin-1 and line-oriented, so a name is never interpolated raw: control
    characters go, a quote or a backslash becomes `_`, and the value carries both the ASCII
    `filename="..."` fallback (every non-ASCII character replaced by `_`) and the percent-encoded
    UTF-8 `filename*` every current browser prefers (RFC 5987 / 6266).
    """
    clean = "".join("_" if c in '"\\' else c for c in name if 0x20 <= ord(c) != 0x7f)
    ascii_name = "".join(c if c.isascii() else "_" for c in clean)
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(clean, safe='')}"


def _same_origin(headers, port: int) -> bool:
    """A localhost server is reachable from any page in the browser, so a POST that another site
    aimed at us is refused before it is read. Both signals are optional (a same-origin fetch may
    send neither) and both are believed only to say no: an Origin that is not this server, or a
    Sec-Fetch-Site that is neither same-origin nor a direct navigation."""
    origin = headers.get("Origin")
    if origin is not None and urlsplit(origin).netloc not in (f"127.0.0.1:{port}", f"localhost:{port}"):
        return False
    site = headers.get("Sec-Fetch-Site")
    return site is None or site in ("same-origin", "none")


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
    timeout = 60                            # StreamRequestHandler puts this on the socket
    _sent = False                           # set once this request's headers are on the wire

    def log_message(self, fmt, *args):
        if self.server.verbose:
            super().log_message(fmt, *args)

    # -- responses ----------------------------------------------------------------------------
    def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if self.close_connection:
            # Tell an HTTP/1.1 client not to reuse this socket for whatever reason we're already
            # closing it (oversized body, cross-origin refusal, a stalled read, an unhandled
            # error) — otherwise it would try the next request on a socket we're about to drop.
            self.send_header("Connection", "close")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self._sent = True                   # past this point a second response would corrupt the stream
        self.wfile.write(body)

    def _json(self, obj, status: int = 200) -> None:
        self._send(status, json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8")

    def _error(self, status: int, message: str) -> None:
        if self._sent:                      # a failure after the headers went out: say no more, hang up
            self.close_connection = True
            return
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
                except (TimeoutError, OSError):
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
                    except (TimeoutError, OSError):
                        self.close_connection = True
                self._consumed = True
        self._json({"error": message}, status)

    def _read(self, length: int) -> bytes:
        """Read exactly `length` bytes, or give up. A client that announced a body and then stalled
        would otherwise pin this handler thread for as long as it stayed connected; the socket
        timeout turns that into an error, and the connection goes with it."""
        try:
            return self.rfile.read(length)
        except (TimeoutError, OSError):
            self.close_connection = True
            self._consumed = True           # nothing more will arrive, so do not try to drain it
            raise _Bad(400, "request body incomplete") from None

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
            self._read(length)
        self._consumed = True

    def _body(self) -> dict:
        length = self._length()
        raw = self._read(length) if length else b""
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
        self._consumed = self._sent = False
        parts = urlsplit(self.path)
        path, query = parts.path, parse_qs(parts.query)
        try:
            if method == "POST" and not _same_origin(self.headers, self.server.server_address[1]):
                raise _Bad(403, "cross-origin request refused")
            session.touch()                 # only a request that could be our own page counts,
            self.server.visited = True      # for the idle clock as for the first visit
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
        except BadRequest as e:
            self._error(400, str(e))
        except NoComparison as e:
            self._error(409, str(e))
        except Exception as e:
            self.close_connection = True
            if self.server.verbose:
                self.log_error("%s", traceback.format_exc())
            if not self._sent:
                self._json({"error": f"internal error: {type(e).__name__}"}, 500)

    # -- the API --------------------------------------------------------------------------------
    def _api_state(self, session, query):
        with session.lock:
            payload = session.state()
        self._json(payload)

    def _api_ping(self, session, query):
        hidden = _flag(query, "hidden", False)
        self._drain()
        self.server.hidden = hidden
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
            payload = session.payload(render_set, change_bars)
        self._json(payload)      # written outside the lock: a slow client must not stall the rest

    def _api_layout(self, session, query):
        body = self._body()
        if "options" not in body:
            raise _Bad(400, "options are required")
        render_set, change_bars = _style(body)
        with session.lock:
            options = parse_options(body["options"], session.options)
            session.relayout(options)
            payload = session.payload(render_set, change_bars)
        self._json(payload)

    def _api_pages(self, session, query):
        rs = query.get("render_set", ["Standard"])[0]
        bars = _flag(query, "change_bars", True)
        with session.lock:
            payload = session.pages(rs, bars)
        self._json(payload)

    def _api_pdf(self, session, query):
        rs = query.get("render_set", ["Standard"])[0]
        bars = _flag(query, "change_bars", True)
        report = query.get("report", ["last"])[0]
        check_render(rs, report)
        with session.lock:
            data, name = session.pdf(rs, bars, report)
        self._send(200, data, "application/pdf", {"Content-Disposition": _disposition(name)})


class Server(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        """A client that hung up mid-request (the app window closed, a reset keep-alive socket) is
        not an error worth a traceback in the log; anything else still gets socketserver's report."""
        if not isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)):
            super().handle_error(request, client_address)


def make_server(session: Session, host: str = HOST, port: int = 0, verbose: bool = False) -> ThreadingHTTPServer:
    server = Server((host, port), Handler)
    server.daemon_threads = True
    server.session = session
    server.verbose = verbose
    server.stopped = False
    server.visited = False
    server.hidden = False
    return server


def url_of(server) -> str:
    host, port = server.server_address[:2]
    return f"http://{host}:{port}/"


def _watchdog(server, idle: float, grace: float, clock=time.monotonic, sleep=time.sleep) -> None:
    """Stop the server after `idle` seconds without a request -- or `max(idle, grace)` before the
    first one, so a slow browser start is not mistaken for a closed window. A gap between two
    ticks far longer than the tick means the machine slept (the page could not ping); that counts
    as a touch, not as silence, and the page gets its grace back to resume. A page that says it is
    hidden gets HIDDEN_IDLE instead: a hidden window's timers are throttled to one wake a minute."""
    step = max(0.05, min(1.0, idle / 4))
    last = clock()
    while not server.stopped:
        sleep(step)
        now = clock()
        if now - last > 4 * step + 2.0:
            server.session.touch()
            server.visited = False      # a woken browser gets the grace back, not one idle window
        last = now
        if server.stopped:
            return
        limit = idle if server.visited else max(idle, grace)
        if server.visited and server.hidden:
            limit = max(limit, HIDDEN_IDLE)
        if now - server.session.last_seen > limit:
            server.shutdown()
            return


def run(server, idle: float = 0.0, grace: float = 0.0) -> None:
    """Serve until /api/quit, the idle watchdog (idle > 0) or shutdown() from another thread."""
    if idle > 0:
        threading.Thread(target=_watchdog, args=(server, idle, grace), daemon=True).start()
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        server.stopped = True
        server.server_close()


def serve(port: int = 0, open_browser: bool = True, idle: float = DEFAULT_IDLE, grace: float = DEFAULT_GRACE,
          verbose: bool = False, fonts=None, ready=None) -> None:
    logging.getLogger("fontTools").setLevel(logging.ERROR)     # "'created' timestamp seems very low"
    session = Session(fonts=fonts)
    server = make_server(session, port=port, verbose=verbose)
    url = url_of(server)
    if ready is not None:
        ready(url)
    if open_browser:
        open_viewer(url)
    try:
        run(server, idle, grace)
    except KeyboardInterrupt:
        pass                # Ctrl+C in a console is a quit, not a crash; run() still closes
