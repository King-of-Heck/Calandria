"""The page's files exist, agree with each other (every id the scripts look up is
in the HTML, every static reference is a served file) and parse (node --check when node is here)."""
import re
import shutil
import subprocess
from importlib import resources

import pytest

from calandria.server.app import DEFAULT_IDLE, STATIC

VIEWER = resources.files("calandria.viewer")


def _read(name):
    return VIEWER.joinpath(name).read_text("utf-8")


def _ids_in_html():
    return set(re.findall(r'\sid="([A-Za-z0-9_-]+)"', _read("index.html")))


@pytest.mark.parametrize("name", sorted(STATIC))
def test_static_file_exists(name):
    assert VIEWER.joinpath(name).read_bytes(), name


def test_index_references_only_served_files():
    refs = re.findall(r'(?:src|href)="/static/([^"]+)"', _read("index.html"))
    assert refs and set(refs) <= set(STATIC)
    assert "app.js" in refs and "style.css" in refs


def test_index_declares_a_module_script_charset_and_title():
    html = _read("index.html")
    assert '<meta charset="utf-8">' in html and "<title>Calandria</title>" in html
    assert '<script type="module" src="/static/app.js">' in html


@pytest.mark.parametrize("script", ["app.js", "changes.js", "sources.js"])
def test_every_id_the_script_looks_up_exists(script):
    wanted = set(re.findall(r'\$\("([A-Za-z0-9_-]+)"\)', _read(script)))
    assert wanted, script
    missing = wanted - _ids_in_html()
    assert not missing, f"{script} looks up ids missing from index.html: {sorted(missing)}"


def test_the_v41_caveat_is_on_the_page():
    assert "nothing is written to Word" in _read("index.html")


def test_the_heartbeat_is_faster_than_the_server_idle_timeout():
    js = _read("app.js")
    ping_ms = int(re.search(r"const PING_MS = (\d+);", js).group(1))
    misses = int(re.search(r"const PING_MISSES = (\d+);", js).group(1))
    assert ping_ms == 2000
    # the server stops DEFAULT_IDLE s after the last ping: three pings must fit inside that
    assert ping_ms * misses / 1000 < DEFAULT_IDLE
    assert "close this window" in js and "close this tab" not in js


def test_the_ping_carries_the_page_visibility():
    js = _read("app.js")
    # a hidden page's timers are throttled to one wake a minute, so the server has to be told
    assert "/api/ping?hidden=" in js
    assert "visibilitychange" in js


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not on PATH")
@pytest.mark.parametrize("script", ["app.js", "changes.js", "sources.js"])
def test_scripts_parse(script):
    path = VIEWER.joinpath(script)
    r = subprocess.run([shutil.which("node"), "--check", str(path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_a_closed_page_does_not_ping():
    js = _read("app.js")
    body = js[js.index("function ping()"):]
    body = body[:body.index("\n}\n")]
    assert "if (state.closed) return;" in body.splitlines()[1]


def _main_html():
    html = _read("index.html")
    return html[:html.index("<main")], html[html.index("<main"):]


def test_the_source_cards_are_in_the_page_area_not_the_toolbar():
    head, main = _main_html()
    for id_ in ("cardA", "cardB", "fileA", "fileB", "nameA", "nameB", "clearA", "clearB", "swap", "compare", "sources"):
        assert f'id="{id_}"' in main, id_
        assert f'id="{id_}"' not in head, id_


def test_the_empty_state_teaches():
    _, main = _main_html()
    assert "nothing is written to Word" in main
    assert "Closing this window closes Calandria" in main
    assert "Drop the .docx here or click to choose" in main
