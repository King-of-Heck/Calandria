import base64
import http.client
import json
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from urllib.parse import urlsplit

import pytest

from calandria import __version__
from calandria.layout.fonts import default_dirs
from calandria.server import app as appmod
from calandria.server.app import DEFAULT_IDLE, MAX_BODY, STATIC, make_server, run, url_of
from calandria.server.session import Session
from calandria.testing.fakefonts import FakeResolver
from calandria.testing.makedocx import DOC, P, STYLES, make_docx

STY = STYLES('<w:rFonts w:ascii="Fake"/><w:sz w:val="20"/>')
WHEN = datetime(2026, 9, 9, 14, 5)


def _docx(body):
    return make_docx({"word/document.xml": DOC(body), "word/styles.xml": STY})


def _b64(data):
    return base64.b64encode(data).decode("ascii")


def _req(url, method="GET", body=None, raw=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def _json(url, method="GET", body=None, raw=None):
    status, headers, data = _req(url, method, body, raw)
    return status, json.loads(data)


class Served:
    def __init__(self, session, idle=0.0):
        self.session = session
        self.server = make_server(session)
        self.url = url_of(self.server)
        self.thread = threading.Thread(target=run, args=(self.server, idle), daemon=True)
        self.thread.start()

    def stop(self):
        if self.thread.is_alive():
            self.server.shutdown()
        self.thread.join(5)


@pytest.fixture
def srv():
    s = Served(Session(fonts=FakeResolver(), clock=lambda: WHEN))
    yield s
    s.stop()


def _compare_body(a=P("aaaa"), b=P("aaaa bbbb"), options=None):
    body = {"a": {"name": "a.docx", "data": _b64(_docx(a))}, "b": {"name": "b.docx", "data": _b64(_docx(b))}}
    if options is not None:
        body["options"] = options
    return body


def test_defaults():
    assert DEFAULT_IDLE == 300.0 and MAX_BODY == 64 * 1024 * 1024
    assert set(STATIC) == {"index.html", "style.css", "app.js", "changes.js"}


def test_url_is_loopback_with_the_bound_port(srv):
    assert srv.url.startswith("http://127.0.0.1:") and srv.url.endswith("/")


def test_state_and_unknown_routes(srv):
    assert _json(srv.url + "api/state") == (200, {"version": __version__, "loaded": False, "names": None})
    assert _json(srv.url + "nope")[0] == 404
    assert _json(srv.url + "api/nope")[0] == 404
    assert _json(srv.url + "static/../pyproject.toml")[0] == 404
    assert _json(srv.url + "static/secret.txt")[0] == 404


def test_methods_are_checked(srv):
    assert _json(srv.url + "api/pages", "POST", {})[0] == 405
    assert _json(srv.url + "api/compare")[0] == 405
    assert _json(srv.url + "api/ping")[0] == 405


def test_before_a_comparison_is_loaded(srv):
    status, d = _json(srv.url + "api/pages")
    assert status == 409 and d == {"error": "no comparison loaded"}
    assert _json(srv.url + "api/layout", "POST", {"options": {}})[0] == 409
    assert _req(srv.url + "api/pdf")[0] == 409


def test_compare_then_pages_layout_and_state(srv):
    status, d = _json(srv.url + "api/compare", "POST", _compare_body())
    assert status == 200
    assert d["names"] == {"original": "a.docx", "modified": "b.docx"} and d["page_count"] == 1
    assert d["summary"]["total"] == 1 and "bbbb" in d["pages"][0] and d["anchors"] == {"1": {"page": 1, "top": 72.0}}
    assert d["options"]["ignore_case"] is False and d["render_set"] == "Standard"
    assert _json(srv.url + "api/state")[1]["loaded"] is True

    status, d = _json(srv.url + "api/pages?render_set=Black%20and%20White&change_bars=0")
    assert status == 200 and d["render_set"] == "Black and White" and d["change_bars"] is False
    assert "#0000ff" not in d["pages"][0] and d["report_lines"][3] == "Rendering set: Black and White"
    assert _json(srv.url + "api/pages")[1]["change_bars"] is True

    status, d = _json(srv.url + "api/layout", "POST", {"options": {"show_insertions": False}})
    assert status == 200 and d["options"]["show_insertions"] is False and "bbbb" not in d["pages"][0]
    status, d = _json(srv.url + "api/layout", "POST", {"options": {}})
    assert status == 200 and d["options"]["show_insertions"] is False     # merged over the current options


def test_compare_options_are_applied(srv):
    body = _compare_body(P("Alpha") + P("Beta gamma"), P("Alpha") + P("beta gamma"), {"ignore_case": True})
    status, d = _json(srv.url + "api/compare", "POST", body)
    assert status == 200 and d["summary"]["total"] == 0 and d["options"]["ignore_case"] is True


def test_bad_requests(srv):
    assert _json(srv.url + "api/compare", "POST", raw=b"{not json")[0] == 400
    assert _json(srv.url + "api/compare", "POST", raw=b"[]") == (400, {"error": "expected a JSON object"})
    assert _json(srv.url + "api/compare", "POST", {"a": {"name": "a", "data": "AA=="}}) == \
        (400, {"error": "both files are required (a and b)"})
    assert _json(srv.url + "api/compare", "POST", {"a": {"name": "", "data": "AA=="}, "b": {"name": "b", "data": "AA=="}}) == \
        (400, {"error": "a file name is required"})
    assert _json(srv.url + "api/compare", "POST", {"a": {"name": "a", "data": "@@"}, "b": {"name": "b", "data": "AA=="}}) == \
        (400, {"error": "a: the file data is not base64"})
    body = _compare_body()
    body["b"]["data"] = _b64(b"not a zip")
    status, d = _json(srv.url + "api/compare", "POST", body)
    assert status == 400 and d["error"].startswith("b.docx: not a Word document")
    status, d = _json(srv.url + "api/compare", "POST", _compare_body(options={"zoom": 2}))
    assert status == 400 and d["error"] == "unknown options: zoom"
    assert _json(srv.url + "api/compare", "POST", _compare_body(options=[]))[0] == 400
    _json(srv.url + "api/compare", "POST", _compare_body())
    assert _json(srv.url + "api/layout", "POST", {"options": {"ignore_case": "yes"}}) == \
        (400, {"error": "option ignore_case must be true or false"})
    assert _json(srv.url + "api/layout", "POST", {})[0] == 400
    assert _json(srv.url + "api/pages?render_set=Sepia")[0] == 400
    assert _json(srv.url + "api/pages?change_bars=maybe") == (400, {"error": "change_bars must be 0 or 1"})
    assert _json(srv.url + "api/pdf?report=middle")[0] == 400


def test_body_cap(srv, monkeypatch):
    monkeypatch.setattr(appmod, "MAX_BODY", 10)
    status, d = _json(srv.url + "api/compare", "POST", raw=b"x" * 20)
    assert status == 413 and "10" in d["error"]


def test_file_names_are_reduced_to_their_base_name(srv):
    body = _compare_body()
    body["a"]["name"] = "C:\\docs\\one.docx"
    body["b"]["name"] = "/tmp/two.docx"
    status, d = _json(srv.url + "api/compare", "POST", body)
    assert status == 200 and d["names"] == {"original": "one.docx", "modified": "two.docx"}


def test_ping_touches_and_quit_stops_the_server(srv):
    before = srv.session.last_seen
    time.sleep(0.01)
    assert _json(srv.url + "api/ping", "POST", {}) == (200, {"ok": True})
    assert srv.session.last_seen > before
    assert _json(srv.url + "api/quit", "POST", {}) == (200, {"ok": True})
    srv.thread.join(5)
    assert not srv.thread.is_alive() and srv.server.stopped


def test_ping_without_a_body_is_fine(srv):
    req = urllib.request.Request(srv.url + "api/ping", data=b"", method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        assert r.status == 200 and json.loads(r.read()) == {"ok": True}


def test_idle_watchdog_stops_an_unvisited_server():
    s = Served(Session(fonts=FakeResolver()), idle=0.3)
    s.thread.join(5)
    assert not s.thread.is_alive() and s.server.stopped


def test_requests_keep_the_watchdog_quiet():
    s = Served(Session(fonts=FakeResolver()), idle=0.6)
    try:
        for _ in range(4):
            time.sleep(0.3)
            assert _json(s.url + "api/state")[0] == 200
        assert s.thread.is_alive()
    finally:
        s.stop()


def test_concurrent_requests_are_serialized(srv):
    _json(srv.url + "api/compare", "POST", _compare_body())
    results = []

    def hit():
        results.append(_json(srv.url + "api/pages")[0])

    threads = [threading.Thread(target=hit) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert results == [200] * 6


def test_error_before_the_body_is_read_keeps_the_connection_usable(srv):
    parts = urlsplit(srv.url)
    conn = http.client.HTTPConnection(parts.hostname, parts.port, timeout=10)
    try:
        payload = json.dumps({"filler": "x" * 300}).encode()
        conn.request("POST", "/api/nope", body=payload, headers={"Content-Type": "application/json"})
        r = conn.getresponse()
        assert r.status == 404
        r.read()

        conn.request("GET", "/api/state")
        r = conn.getresponse()
        assert r.status == 200
        assert json.loads(r.read())["loaded"] is False

        conn.request("POST", "/api/pages", body=b"{}", headers={"Content-Type": "application/json"})
        r = conn.getresponse()
        assert r.status == 405
        r.read()

        conn.request("GET", "/api/state")
        r = conn.getresponse()
        assert r.status == 200
        assert json.loads(r.read())["loaded"] is False
    finally:
        conn.close()


def test_negative_content_length_is_rejected(srv):
    parts = urlsplit(srv.url)
    conn = http.client.HTTPConnection(parts.hostname, parts.port, timeout=10)
    try:
        conn.putrequest("POST", "/api/ping")
        conn.putheader("Content-Length", "-5")
        conn.endheaders()
        r = conn.getresponse()
        assert r.status == 400
        assert json.loads(r.read()) == {"error": "bad Content-Length"}
    finally:
        conn.close()


def test_state_is_read_under_the_lock(srv):
    done = threading.Event()
    result = {}

    def hit():
        result["status"], result["body"] = _json(srv.url + "api/state")
        done.set()

    with srv.session.lock:
        t = threading.Thread(target=hit, daemon=True)
        t.start()
        assert not done.wait(0.3)

    assert done.wait(5)
    t.join(5)
    assert result["status"] == 200


def test_unexpected_exception_is_a_json_500(srv, monkeypatch):
    def boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(srv.session, "state", boom)
    status, d = _json(srv.url + "api/state")
    assert status == 500 and d == {"error": "internal error: RuntimeError"}


@pytest.mark.skipif(not any(os.path.isdir(d) for d in default_dirs()), reason="no system font directory")
def test_pdf_download_with_real_fonts():
    s = Served(Session(clock=lambda: WHEN))
    try:
        body = {"a": {"name": "Draft v1.docx", "data": _b64(make_docx({"word/document.xml": DOC(P("aaaa"))}))},
                "b": {"name": "Draft v2.docx", "data": _b64(make_docx({"word/document.xml": DOC(P("aaaa bbbb"))}))}}
        assert _json(s.url + "api/compare", "POST", body)[0] == 200
        status, headers, data = _req(s.url + "api/pdf?render_set=Standard&change_bars=1&report=none")
        assert status == 200 and headers["Content-Type"] == "application/pdf" and data.startswith(b"%PDF")
        assert headers["Content-Disposition"] == 'attachment; filename="Draft v1 vs Draft v2 redline.pdf"'
        assert int(headers["Content-Length"]) == len(data)
    finally:
        s.stop()


def test_index_and_static_files_are_served_with_their_types(srv):
    status, headers, data = _req(srv.url)
    assert status == 200 and headers["Content-Type"] == "text/html; charset=utf-8" and b"<title>Calandria</title>" in data
    status, headers, data = _req(srv.url + "static/app.js")
    assert status == 200 and headers["Content-Type"] == "text/javascript; charset=utf-8" and b"api" in data
    status, headers, data = _req(srv.url + "static/style.css")
    assert status == 200 and headers["Content-Type"] == "text/css; charset=utf-8"
    assert headers["Cache-Control"] == "no-store"
