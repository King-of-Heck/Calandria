import json
import os
from datetime import datetime

import pytest

from calandria import __version__
from calandria.layout.fonts import default_dirs
from calandria.server.session import (OPTION_KEYS, BadDocument, Options, Session, change_marks, check_render,
                                      parse_options)
from calandria.testing.fakefonts import FakeResolver
from calandria.testing.makedocx import DOC, P, STYLES, TBL, make_docx

FR = FakeResolver()
STY = STYLES('<w:rFonts w:ascii="Fake"/><w:sz w:val="20"/>')
WHEN = datetime(2026, 9, 9, 14, 5)


def _docx(body):
    return make_docx({"word/document.xml": DOC(body), "word/styles.xml": STY})


def _session(a=P("aaaa"), b=P("aaaa bbbb"), **kw):
    s = Session(fonts=FR, clock=lambda: WHEN)
    s.load("a.docx", _docx(a), "b.docx", _docx(b), **kw)
    return s


def test_options_defaults_and_layout_options():
    o = Options()
    assert (o.ignore_case, o.count_numbering, o.show_equal, o.show_insertions, o.show_deletions,
            o.show_formatting) == (False, True, True, True, True, True)
    lo = Options(show_equal=False).layout_options(FR)
    assert (lo.show_equal, lo.show_insertions, lo.fonts) == (False, True, FR)
    assert OPTION_KEYS == ("ignore_case", "count_numbering", "show_equal", "show_insertions",
                           "show_deletions", "show_formatting")


def test_parse_options_merges_over_a_base_and_rejects_bad_input():
    assert parse_options({}) == Options()
    assert parse_options({"ignore_case": True}, Options(show_equal=False)) == Options(ignore_case=True, show_equal=False)
    with pytest.raises(ValueError, match="unknown options: zoom"):
        parse_options({"zoom": 2})
    with pytest.raises(ValueError, match="ignore_case must be true or false"):
        parse_options({"ignore_case": "yes"})
    with pytest.raises(ValueError, match="must be an object"):
        parse_options([])


def test_check_render():
    check_render("Standard")
    check_render("Black and White", "first")
    with pytest.raises(ValueError, match="Sepia"):
        check_render("Sepia")
    with pytest.raises(ValueError, match="report"):
        check_render("Standard", "middle")


def test_state_before_and_after_load():
    s = Session(fonts=FR, clock=lambda: WHEN)
    assert s.state() == {"version": __version__, "loaded": False, "names": None}
    assert not s.loaded
    s.load("a.docx", _docx(P("x")), "b.docx", _docx(P("x")))
    assert s.state() == {"version": __version__, "loaded": True, "names": {"original": "a.docx", "modified": "b.docx"}}


def test_methods_need_a_loaded_comparison():
    s = Session(fonts=FR)
    for call in (lambda: s.relayout(Options()), lambda: s.pages(), lambda: s.payload(), lambda: s.pdf()):
        with pytest.raises(LookupError, match="no comparison loaded"):
            call()


def test_bad_document_names_the_file():
    s = Session(fonts=FR)
    with pytest.raises(BadDocument, match="b.docx: not a Word document"):
        s.load("a.docx", _docx(P("x")), "b.docx", b"not a zip")
    assert not s.loaded


def test_a_failed_second_load_leaves_the_first_pair_intact():
    s = _session()
    with pytest.raises(BadDocument, match="d.docx: not a Word document"):
        s.load("c.docx", _docx(P("cccc")), "d.docx", b"not a zip")
    assert s.state()["names"] == {"original": "a.docx", "modified": "b.docx"}
    assert s.payload()["summary"]["total"] == 1 and "bbbb" in s.payload()["pages"][0]


def test_a_load_that_fails_after_parsing_leaves_the_first_pair_intact(monkeypatch):
    """Both files parse before anything is committed, so the not-a-zip case above never got as far
    as the fields; a failure in the comparison or the layout did, and left the session describing
    the new pair while still holding the old one's drawings."""
    import calandria.server.session as sessmod

    s = _session()
    monkeypatch.setattr(sessmod, "layout", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError, match="boom"):
        s.load("c.docx", _docx(P("cccc")), "d.docx", _docx(P("cccc dddd")))
    monkeypatch.undo()
    assert s.state()["names"] == {"original": "a.docx", "modified": "b.docx"}
    d = s.payload()
    assert d["summary"]["total"] == 1 and "bbbb" in d["pages"][0] and "dddd" not in d["pages"][0]


def test_payload_of_a_one_line_insertion():
    s = _session()
    d = s.payload()
    assert d["names"] == {"original": "a.docx", "modified": "b.docx"}
    assert d["options"] == {"ignore_case": False, "count_numbering": True, "show_equal": True,
                            "show_insertions": True, "show_deletions": True, "show_formatting": True}
    assert d["summary"]["total"] == 1 and d["summary"]["insertions"] == 1 and d["summary"]["amendments"] == 1
    assert len(d["changes"]) == 1 and d["changes"][0]["cid"] == 1 and d["changes"][0]["category"] == "amendment"
    assert d["page_count"] == 1 and len(d["pages"]) == 1 and "bbbb" in d["pages"][0]
    assert d["anchors"] == {1: {"page": 1, "top": 72.0}}
    assert d["marks"] == [[1, 72.0, 12.0, [1]]]
    assert d["render_sets"] == ["Standard", "Black and White"]
    assert d["render_set_styles"]["Standard"]["insert"]["color"] == "0000ff"
    assert d["render_set_styles"]["Black and White"]["delete"]["color"] == "000000"
    assert (d["render_set"], d["change_bars"]) == ("Standard", True)
    assert d["report_lines"][0] == "Original: a.docx" and d["report_lines"][2] == "Compared: 2026-09-09 14:05"
    assert d["report_lines"][3] == "Rendering set: Standard"
    assert d["changed_pages"] == [1]
    json.dumps(d)


def test_pages_follow_the_render_set_and_the_bars_toggle():
    s = _session()
    d = s.pages("Black and White", change_bars=False)
    assert set(d) == {"render_set", "change_bars", "side_marks", "pages", "sides", "report_lines"}
    assert d["render_set"] == "Black and White" and d["change_bars"] is False
    assert "#0000ff" not in d["pages"][0] and 'stroke-width="1.50"' not in d["pages"][0]
    assert d["report_lines"][3] == "Rendering set: Black and White"
    with pytest.raises(ValueError):
        s.pages("Sepia")


def test_relayout_reruns_the_comparison_with_the_new_options():
    s = _session(P("Alpha") + P("Beta gamma"), P("Alpha") + P("beta gamma"))
    assert s.payload()["summary"]["total"] == 1
    s.relayout(Options(ignore_case=True))
    d = s.payload()
    assert d["summary"]["total"] == 0 and d["options"]["ignore_case"] is True and d["anchors"] == {}
    assert s.options == Options(ignore_case=True)


def test_hidden_insertions_leave_the_page_and_load_keeps_the_current_options():
    s = _session(options=Options(show_insertions=False))
    assert "bbbb" not in s.payload()["pages"][0] and s.options.show_insertions is False
    s.load("a.docx", _docx(P("cccc")), "b.docx", _docx(P("cccc dddd")))
    assert "dddd" not in s.payload()["pages"][0]          # the options survive a new pair
    s.load("a.docx", _docx(P("cccc")), "b.docx", _docx(P("cccc dddd")), options=Options())
    assert "dddd" in s.payload()["pages"][0]


def test_change_marks_include_changed_table_rows_and_anchor_every_number():
    s = _session(P("aaaa") + TBL([["x", "y"]], [4680, 4680]), P("aaaa bbbb") + TBL([["x", "z"]], [4680, 4680]))
    anchors, marks = change_marks(s.layout)
    cids = {r["cid"] for r in s.cmp.to_dict()["changes"] if r["cid"] is not None}
    assert set(anchors) == cids and 1 in cids and len(cids) >= 2       # the paragraph, then the cell(s)
    assert all(len(m) == 4 and m[0] == 1 for m in marks)
    row_marks = [m for m in marks if set(m[3]) & (cids - {1})]
    assert row_marks and any(m[2] > 12.0 for m in row_marks)      # a row box is taller than a line
    assert all(cid in anchors for m in marks for cid in m[3])


def test_touch_updates_last_seen():
    s = Session(fonts=FR)
    before = s.last_seen
    s.touch()
    assert s.last_seen >= before


@pytest.mark.skipif(not any(os.path.isdir(d) for d in default_dirs()), reason="no system font directory")
def test_pdf_bytes_and_file_name():
    s = Session(clock=lambda: WHEN)
    s.load("Draft v1.docx", make_docx({"word/document.xml": DOC(P("aaaa"))}),
           "Draft v2.docx", make_docx({"word/document.xml": DOC(P("aaaa bbbb"))}))
    data, name = s.pdf()
    assert data.startswith(b"%PDF") and name == "Draft v1 vs Draft v2 redline.pdf"
    data2, _ = s.pdf("Black and White", change_bars=False, report="none")
    assert data2.startswith(b"%PDF") and data2 != data
    with pytest.raises(ValueError):
        s.pdf(report="middle")


@pytest.mark.skipif(not any(os.path.isdir(d) for d in default_dirs()), reason="no system font directory")
def test_pdf_changed_only_changes_the_name_and_the_report():
    s = Session(clock=lambda: WHEN)
    s.load("a.docx", make_docx({"word/document.xml": DOC(P("aaaa"))}),
           "b.docx", make_docx({"word/document.xml": DOC(P("aaaa bbbb"))}))
    data, name = s.pdf(changed_only=True)
    assert name == "a vs b redline (changed pages).pdf" and data.startswith(b"%PDF")
    _, plain = s.pdf()
    assert plain == "a vs b redline.pdf"


# v2.4.0: three sides per comparison (spec §12.2).

from calandria.server.session import row_map


def test_row_map_names_the_first_line_of_every_row():
    s = _session(P("aaaa") + P("bbbb"), P("aaaa") + P("bbbb") + P("cccc"))
    assert row_map(s.layout) == {0: {"page": 1, "top": 72.0, "height": 12.0},
                                 1: {"page": 1, "top": 84.0, "height": 12.0},
                                 2: {"page": 1, "top": 96.0, "height": 12.0}}
    assert row_map(s.layouts["original"]) == {0: {"page": 1, "top": 72.0, "height": 12.0},
                                              1: {"page": 1, "top": 84.0, "height": 12.0}}


def test_the_session_lays_out_three_sides_and_ships_them():
    s = _session(P("aaaa") + P("old old"), P("aaaa") + P("new new"))
    assert set(s.layouts) == {"blackline", "original", "modified"} and s.layouts["blackline"] is s.layout
    d = s.payload()
    assert d["side_marks"] is False and set(d["sides"]) == {"blackline", "original", "modified"}
    for side in ("blackline", "original", "modified"):
        blk = d["sides"][side]
        assert set(blk) == {"pages", "page_count", "changed_pages", "rows"} and blk["page_count"] == len(blk["pages"]) == 1
    assert d["sides"]["blackline"]["pages"] == d["pages"] and d["sides"]["blackline"]["changed_pages"] == d["changed_pages"]
    assert "old" in d["sides"]["original"]["pages"][0] and "new" not in d["sides"]["original"]["pages"][0]
    assert "new" in d["sides"]["modified"]["pages"][0] and "old" not in d["sides"]["modified"]["pages"][0]
    assert d["sides"]["original"]["rows"] == {0: {"page": 1, "top": 72.0, "height": 12.0},
                                              1: {"page": 1, "top": 84.0, "height": 12.0}}
    assert d["sides"]["original"]["changed_pages"] == [1]


def test_marks_tint_the_side_pages_and_a_relayout_rebuilds_every_side():
    s = _session(P("aaaa") + P("old old"), P("aaaa") + P("new new"))
    plain, marked = s.pages(), s.pages(marks=True)
    assert "<rect" not in plain["sides"]["original"]["pages"][0]
    assert "<rect" in marked["sides"]["original"]["pages"][0] and marked["side_marks"] is True
    assert marked["pages"] == plain["pages"]                     # the blackline never changes with marks
    s.relayout(Options(show_equal=False))
    assert "aaaa" not in s.payload()["sides"]["modified"]["pages"][0]
