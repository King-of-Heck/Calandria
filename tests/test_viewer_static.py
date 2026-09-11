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


@pytest.mark.parametrize("script", ["app.js", "changes.js", "sources.js", "strip.js"])
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
@pytest.mark.parametrize("script", ["app.js", "changes.js", "sources.js", "strip.js", "copy.js", "panes.js", "sync.js"])
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


def test_the_source_cards_start_in_the_page_area_and_move_to_the_toolbar():
    head, main = _main_html()
    for id_ in ("cardA", "cardB", "fileA", "fileB", "nameA", "nameB", "clearA", "clearB", "swap", "compare", "sources"):
        assert f'id="{id_}"' in main, id_
        assert f'id="{id_}"' not in head, id_
    # once a comparison exists the strip is a second toolbar row, and it comes back for a fresh start
    js = _read("sources.js")
    body = js[js.index("function placeSources("):]
    assert 'compact ? $("bar") : $("pages")' in body and "home.append(src)" in body
    css = _read("style.css")
    assert "#bar {\n  display: flex; flex-wrap: wrap;" in css
    assert "#bar .sources.compact { flex: 1 0 100%;" in css
    # the remove button sits in the row with the name, not pinned to a corner
    assert "#bar .sources.compact .card .clear { position: static;" in css


def test_the_empty_state_teaches():
    _, main = _main_html()
    assert "nothing is written to Word" in main
    assert "Closing this window closes Calandria" in main
    assert "Drop the .docx here or click to choose" in main


def test_the_toolbar_holds_navigation_zoom_pdf_and_options_only():
    html = _read("index.html")
    header = html[html.index("<header"):html.index("</header>")]
    for id_ in ("navFirst", "navPrev", "navNext", "navLast", "goto", "changeStatus", "pdf", "options"):
        assert f'id="{id_}"' in header, id_
    # the per-comparison and per-office settings sit inside the Options popover, Quit with them
    popover = header[header.index('id="options"'):]
    for id_ in ("optIgnoreCase", "optCountNumbering", "showUnchanged", "showInsertions", "showDeletions",
                "showFormatting", "renderSet", "changeBars", "report", "quit"):
        assert f'id="{id_}"' in popover, id_
    assert "hideUnchanged" not in html and "hideInsertions" not in html


def test_the_option_labels_say_show_not_hide():
    html = _read("index.html")
    assert "Hide unchanged" not in html and "Show unchanged text" in html


def test_zoom_is_a_stepper_and_the_keys_have_a_sheet():
    html = _read("index.html")
    assert '<select id="zoom"' not in html
    for id_ in ("zoomOut", "zoomPct", "zoomIn", "zoomFit", "keys", "keysClose"):
        assert f'id="{id_}"' in html, id_
    assert '<dialog id="keys"' in html
    js = _read("changes.js")
    assert '"j"' in js and '"k"' in js and '"ArrowRight"' in js and '"ArrowLeft"' in js
    app = _read("app.js")
    assert '"?"' in app and "e.ctrlKey" in app and '"wheel"' in app


def test_progress_and_notice_elements_exist_and_closed_uses_the_card():
    html = _read("index.html")
    for id_ in ("progress", "notice", "noticeText", "noticeClose"):
        assert f'id="{id_}"' in html, id_
    js = _read("app.js")
    body = js[js.index("function closed("):]
    body = body[:body.index("\n}\n")]
    assert 'notice(text, "closed")' in body


def test_tiles_filter_and_the_checkbox_row_is_gone():
    html = _read("index.html")
    for id_ in ("fInsertion", "fDeletion", "fAmendment", "fNumbering"):
        assert f'id="{id_}"' not in html, id_
    js = _read("changes.js")
    assert "data-cat" in js and "anchors[String(" in js and "line-clamp" in _read("style.css")


def test_the_panel_collapses_and_remembers_it():
    assert 'id="panelToggle"' in _read("index.html")
    js = _read("changes.js")
    assert '"calandria.panel"' in js and "calandria:resized" in js
    css = _read("style.css")
    assert "#panel.collapsed" in css and ":focus-visible" in css


# v2.2.1: the minors deferred from the v2.2.0 reviews.

def _function_body(js, name):
    body = js[js.index(f"function {name}("):]
    return body[:body.index("\n}\n")]


def test_the_keys_sheet_has_an_opener_button():
    html = _read("index.html")
    header = html[html.index("<header"):html.index("</header>")]
    assert 'id="keysOpen"' in header
    assert 'id="keysOpen"' in html[html.index("<header"):html.index('id="options"')]   # before Options
    assert '$("keysOpen")' in _read("app.js")


def test_the_caveat_appears_once_in_the_empty_state():
    _, main = _main_html()
    assert main.count("nothing is written to Word") == 1


def test_closed_keeps_the_panel_toggle_and_the_keys_sheet_usable():
    body = _function_body(_read("app.js"), "closed")
    for id_ in ("panelToggle", "keysOpen", "keysClose"):
        assert id_ in body, id_
    assert '$("options").open = false' in body


def test_the_options_button_does_not_toggle_after_close_and_escape_returns_focus():
    body = _function_body(_read("app.js"), "wirePopover")
    assert "state.closed" in body
    assert "summary.focus()" in body


def test_fit_reports_the_scale_of_the_page_on_screen():
    js = _read("app.js")
    assert "function currentPage()" in js
    assert "showZoom()" in _function_body(js, "applyZoom")
    assert "currentPage()" in _function_body(js, "showZoom")
    assert "currentPage()" in _function_body(js, "updatePageStatus")


def test_the_change_rows_share_one_tab_stop():
    js = _read("changes.js")
    assert "li.tabIndex = 0;" not in js
    assert "tabIndex = " in js and "li.focus(" in js


def test_the_clamped_row_leaves_room_for_the_underline():
    css = _read("style.css")
    rule = next(line for line in css.splitlines() if "-webkit-line-clamp: 2" in line)
    assert "padding-bottom" in rule


def test_the_aria_roles_are_on_the_cards_toggle_progress_and_notice():
    html = _read("index.html")
    assert re.search(r'<div id="progress"[^>]*role="progressbar"', html)
    assert re.search(r'<div id="notice"[^>]*role="status"', html)
    assert re.search(r'<div id="cardA"[^>]*role="button"', html)
    assert re.search(r'<div id="cardB"[^>]*role="button"', html)
    assert re.search(r'<button id="panelToggle"[^>]*aria-controls="panel"', html)
    assert "aria-expanded" in _function_body(_read("changes.js"), "initPanel")


def test_the_formatting_tile_dims_with_the_others():
    assert ".formatting" in _function_body(_read("changes.js"), "markTiles")


def test_the_page_tells_the_server_it_is_going_when_it_unloads():
    js = _read("app.js")
    # the last ping before a close says hidden=1 (visibilitychange), which would give the server
    # 90 s of patience; a beacon on pagehide takes that back so the stop takes the normal 8 s
    assert '"pagehide"' in js and 'navigator.sendBeacon("/api/ping?hidden=0")' in js


# v2.3.0: the majors.
from pathlib import Path


def _node(script, code):
    """Runs `code` under node with the viewer module imported as `m` (modules whose top level
    never touches the DOM: strip.js, copy.js)."""
    uri = Path(str(VIEWER.joinpath(script))).as_uri()
    r = subprocess.run([shutil.which("node"), "--input-type=module", "-e", f'import * as m from "{uri}";\n{code}'],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def test_the_strip_is_served_and_sits_after_the_pages():
    assert "strip.js" in STATIC
    html = _read("index.html")
    assert html.index('id="strip"') > html.index("</main>") and html.index('id="strip"') < html.index('id="rowMenu"')
    assert 'initStrip()' in _function_body(_read("app.js"), "wire")
    js = _read("changes.js")
    assert "calandria:filtered" in _function_body(js, "refilter")
    assert "calandria:selected" in _function_body(js, "go")
    assert "calandria:goto" in _function_body(js, "initChanges")


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not on PATH")
def test_mark_position_is_page_index_plus_top_over_the_whole_document():
    out = _node("strip.js", "console.log(m.markTop({page: 1, top: 0}, 792, 4), m.markTop({page: 3, top: 396}, 792, 4));")
    assert out == "0 0.625"


def test_changed_pages_only_is_a_view_toggle_and_a_pdf_flag():
    html = _read("index.html")
    popover = html[html.index('id="options"'):html.index("</details>")]
    on_page = popover[popover.index("On the page"):popover.index("<h4>Rendering")]
    pdf = popover[popover.index("<h4>PDF"):]
    assert 'id="showChangedOnly"' in on_page and 'id="changedOnly"' in pdf
    js = _read("app.js")
    option_ids = re.search(r"const OPTION_IDS = \[(.*?)\];", js).group(1)
    assert "showChangedOnly" not in option_ids and "changedOnly" not in option_ids
    assert '"calandria.changedOnly"' in js
    assert "changed_only=" in _function_body(js, "savePdf")
    assert ".page:not([hidden])" in _function_body(js, "currentPage")
    assert ".page:not([hidden])" in _function_body(js, "applyZoom")
    assert "changed page" in _function_body(js, "updatePageStatus")


def test_copy_controls_exist():
    assert "copy.js" in STATIC
    html = _read("index.html")
    head = html[html.index('<div class="head">'):html.index('id="tiles"')]
    assert 'id="copyFinal"' in head
    menu = html[html.index('id="rowMenu"'):]
    assert 'role="menu"' in html[html.index('<div id="rowMenu"'):html.index('id="rowMenu"') + 60]
    assert menu.count('role="menuitem"') == 2 and 'data-side="modified"' in menu and 'data-side="original"' in menu
    js = _read("changes.js")
    assert 'class="more"' in _function_body(js, "renderList") and "contextmenu" in js
    assert "navigator.clipboard.writeText" in js and "flash(" in js
    assert "export function flash(" in _read("app.js")


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not on PATH")
def test_text_of_joins_one_side_of_the_rows():
    rows = ("[{oi:0,ni:0,marker:'1.',old_marker:null,num_changed:false,segments:[{m:'eq',t:'aa '},{m:'del',t:'bb'},{m:'ins',t:'cc'}]},"
            "{oi:null,ni:1,marker:'',old_marker:null,num_changed:false,segments:[{m:'ins',t:'new para'}]},"
            "{oi:1,ni:null,marker:'',old_marker:null,num_changed:false,segments:[{m:'del',t:'gone'}]},"
            "{oi:2,ni:2,marker:'b)',old_marker:'a)',num_changed:true,segments:[{m:'eq',t:'same'}]}]")
    out = _node("copy.js", f"const r = {rows}; console.log(JSON.stringify([m.textOf(r, 'modified'), m.textOf(r, 'original')]));")
    assert out == '["1. aa cc\\nnew para\\nb) same","1. aa bb\\ngone\\na) same"]'


def test_gutter_numerals_get_a_floor_on_screen():
    body = _function_body(_read("app.js"), "applyZoom")
    assert "text.gutter" in body and "GUTTER_MIN_PX" in body
    assert "const GUTTER_MIN_PX = 9;" in _read("app.js")


def test_the_tiles_filter_the_way_the_summary_counts():
    # the summary counts an amendment as an insertion AND a deletion (SorkWhare parity), so the
    # Insertions and Deletions tiles must show amendments too, or the tile and its list disagree
    js = _read("changes.js")
    assert "function matchesTile(" in js
    body = _function_body(js, "matchesTile")
    assert '"insertion"' in body and '"deletion"' in body and '"amendment"' in body
    assert "matchesTile(" in _function_body(js, "refilter")
    assert "en.category === solo" not in js


# v2.4.0: the side-by-side panes (spec section 12.4).

def test_the_toolbar_holds_the_four_view_toggles_before_the_navigation():
    html = _read("index.html")
    header = html[html.index("<header"):html.index("</header>")]
    views = header[header.index('id="views"'):header.index('class="nav"')]
    for id_, key in (("viewOriginal", "1"), ("viewBlackline", "2"), ("viewModified", "3"), ("viewMarks", "m")):
        assert f'id="{id_}"' in views and f"<kbd>{key}</kbd>" in views, id_
        assert 'aria-pressed=' in views[views.index(f'id="{id_}"'):views.index(f'id="{id_}"') + 160]
    assert 'id="viewBlackline" aria-pressed="true"' in views.replace("\n", " ")
    keys = html[html.index('<dialog id="keys"'):html.index("</dialog>")]
    assert "<kbd>1</kbd>" in keys and "<kbd>m</kbd>" in keys


def test_the_page_area_is_a_row_of_three_panes_with_the_blackline_keeping_its_id():
    html = _read("index.html")
    body = html[html.index('<div id="body">'):html.index('<div id="strip"')]
    assert body.index('id="view"') < body.index('id="paneOriginal"') < body.index('id="pages"') < body.index('id="paneModified"')
    for id_ in ("paneOriginal", "pages", "paneModified"):
        seg = body[body.index(f'id="{id_}"'):]
        assert 'class="caption"' in seg[:400], id_          # every pane starts with its caption
    assert 'id="paneOriginal" class="pane" data-side="original" hidden' in body.replace("\n", " ")
    assert 'id="pages" class="pane" data-side="blackline"' in body.replace("\n", " ")
    css = _read("style.css")
    assert "#view { display: flex;" in css and "#view .pane" in css and "#view.multi .caption" in css
    assert "#view .page rect.hl" in css                  # the current-change band is drawn in the side panes too


def test_panes_js_is_served_wired_and_owns_the_toggles():
    assert "panes.js" in STATIC
    js = _read("panes.js")
    for name in ("initPanes", "applyPanes", "renderPanes", "resetPanes", "visiblePanes", "leadPane", "paneOf", "highlightSides"):
        assert f"export function {name}(" in js, name
    assert 'SIDE_ORDER = ["original", "blackline", "modified"]' in js
    body = _function_body(js, "toggleView")
    assert "visiblePanes().length === 1" in body           # the last pane on cannot be turned off
    assert '"calandria:panes"' in _function_body(js, "applyPanes")
    assert "$(\"viewMarks\").disabled" in _function_body(js, "applyPanes")
    app = _read("app.js")
    assert "initPanes()" in _function_body(app, "wire") and "views: { original: false, blackline: true, modified: false }" in app
    assert "marks: false" in app and "resetPanes()" in _function_body(app, "compareNow")
    assert "&marks=" in _function_body(app, "restyle") and "marks: state.marks" in _function_body(app, "compareNow")
    assert "renderPanes()" in _function_body(app, "renderPages")


def test_zoom_changed_pages_and_lookups_span_the_panes():
    app = _read("app.js")
    assert "visiblePanes()" in _function_body(app, "applyZoom") and "pane.el.clientWidth" in _function_body(app, "applyZoom")
    assert "state.data.sides[" in _function_body(app, "applyChangedOnly")
    assert "leadPane()" in _function_body(app, "currentPage")
    ch = _read("changes.js")
    assert 'document.querySelector(`.page[data-page=' not in ch and '$("pages").querySelector(`.page[data-page=' in ch
    assert "highlightSides(" in _function_body(ch, "highlight")
    assert '$("pages").querySelector(`.page[data-page=' in _read("strip.js")


# v2.4.0: the scroll sync (spec §12.5).

@pytest.mark.skipif(shutil.which("node") is None, reason="node is not on PATH")
def test_the_row_index_is_sorted_by_position_and_skips_hidden_pages():
    code = """
const rows = {"0": {page: 1, top: 72, height: 12}, "1": {page: 1, top: 84, height: 12}, "5": {page: 2, top: 72, height: 24}, "7": {page: 3, top: 72, height: 12}};
const pageTop = (p) => ({1: 0, 2: 1000, 3: null})[p];     // page 3 is hidden (changed pages only)
const ix = m.buildIndex(rows, pageTop, 2);
console.log(JSON.stringify(ix));
console.log(m.rowAt(ix, 0), m.rowAt(ix, 167), m.rowAt(ix, 168), m.rowAt(ix, 5000), m.rowAt(ix, -1));
console.log(m.follow(ix, 5, 0.5), m.follow(ix, 3, 0.25), m.follow(ix, 9, 0), m.follow([], 0, 0));
"""
    out = _node("sync.js", code).splitlines()
    assert out[0] == '[{"row":0,"top":144,"height":24},{"row":1,"top":168,"height":24},{"row":5,"top":1144,"height":48}]'
    assert out[1] == "-1 0 1 2 -1"                      # index positions: the greatest top <= y; -1 above the first
    assert out[2] == "1168 192 1192 0"                  # row 5 + half its height; row 3 is absent -> the end of row 1; row 9 -> the end of row 5; nothing -> 0


def test_sync_js_is_served_and_hung_on_the_panes():
    assert "sync.js" in STATIC
    js = _read("sync.js")
    for name in ("buildIndex", "rowAt", "follow", "initSync", "refreshSync", "syncFrom"):
        assert f"export function {name}(" in js, name
    assert "lastSet" in _function_body(js, "onScroll")     # a follower's own programmatic scroll is not a lead
    app = _read("app.js")
    assert "initSync()" in _function_body(app, "wire") and "refreshSync()" in _function_body(app, "applyZoom")
    assert "syncFrom(" in _function_body(_read("changes.js"), "go")
    assert "syncFrom(" in _function_body(_read("panes.js"), "applyPanes") or "calandria:panes" in js


# Task 5 review fixes: per-page scale under Fit, a clamped follower write, a jump that lands past
# an absent row, and initSync registered before initPanes first announces the panes.

@pytest.mark.skipif(shutil.which("node") is None, reason="node is not on PATH")
def test_the_sync_index_scales_each_page_by_its_own_fit():
    code = """
const rows = {"0": {page: 1, top: 10, height: 10}, "1": {page: 2, top: 10, height: 10}};
const pageTop = (p) => ({1: 0, 2: 500})[p];
const scale = (p) => (p === 1 ? 2 : 4);
console.log(JSON.stringify(m.buildIndex(rows, pageTop, scale)));
"""
    out = _node("sync.js", code)
    assert out == '[{"row":0,"top":20,"height":20},{"row":1,"top":540,"height":40}]'


def test_the_follower_write_is_clamped_to_the_panes_end():
    assert "pane.scrollHeight - pane.clientHeight" in _function_body(_read("sync.js"), "syncFrom")


def test_a_jump_to_an_absent_row_lands_after_the_nearest_earlier_one():
    assert "while (j >= 0 && !rows[String(j)]) j--;" in _function_body(_read("changes.js"), "jumpTo")


def test_sync_listens_before_the_panes_first_announce_themselves():
    body = _function_body(_read("app.js"), "wire")
    assert body.index("initSync()") < body.index("initPanes()")
