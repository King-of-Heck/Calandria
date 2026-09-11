from datetime import datetime

import pytest

from calandria.diff.changes import Comparison, empty_summary
from calandria.pdf.report import (GAP, LINE_GAP, SIZE, TITLE, TITLE_SIZE, ReportInfo, draw_report,
                                  report_height, report_info, report_lines)
from calandria.testing.fakefonts import FakeResolver
from calandria.testing.recpaint import RecordingPainter

FR = FakeResolver()
WHEN = datetime(2026, 9, 9, 14, 5)


def _info(**kw):
    s = empty_summary()
    s.update({"total": 7, "insertions": 4, "deletions": 3, "amendments": 2, "numbering": 1, "formatting": 5})
    base = dict(original="a.docx", modified="b.docx", when=WHEN, render_set="Standard", summary=s,
                ignore_case=False, count_numbering=True)
    base.update(kw)
    return ReportInfo(**base)


def test_report_lines():
    assert report_lines(_info()) == [
        "Original: a.docx", "Modified: b.docx", "Compared: 2026-09-09 14:05", "Rendering set: Standard",
        "Options: ignore case off; count numbering changes on",
        "Changes: 7 (insertions 4, deletions 3, amendments 2, numbering 1); formatting 5 (not counted)"]
    assert report_lines(_info(ignore_case=True, count_numbering=False))[4] == \
        "Options: ignore case on; count numbering changes off"


def test_report_info_from_a_comparison():
    cmp = Comparison([], {"total": 1, "insertions": 1, "deletions": 0, "amendments": 0, "numbering": 0,
                          "formatting": 0}, [], [], True, False)
    info = report_info(cmp, "x.docx", "y.docx", "Black and White", WHEN)
    assert (info.original, info.modified, info.when, info.render_set) == ("x.docx", "y.docx", WHEN, "Black and White")
    assert info.summary is not cmp.summary and info.summary["insertions"] == 1
    assert (info.ignore_case, info.count_numbering) == (True, False)
    assert isinstance(report_info(cmp, "x", "y", "Standard").when, datetime)


def test_height_and_drawing_geometry():
    reg, bold = FR.face(None), FR.face(None, bold=True)
    info = _info()
    # rule gap 6 + title line (1.2 * 11 = 13.2) + LINE_GAP + 6 lines of 1.2 * 9 = 10.8
    assert report_height(info, reg, bold) == pytest.approx(6 + 13.2 + LINE_GAP + 6 * 10.8)
    p = RecordingPainter()
    p.page(612, 792)
    y_end = draw_report(info, 72, 100, 468, reg, bold, p)
    assert p.ops[1] == ("rule", 72, 540, 100, 0.5, "000000", False)
    assert p.ops[2] == ("text", 72, 106 + 0.8 * TITLE_SIZE, TITLE, "<fake:Fake|B>", TITLE_SIZE, "000000", False, False)
    first_y = 106 + 13.2 + LINE_GAP
    assert p.ops[3] == ("text", 72, round(first_y + 0.8 * SIZE, 2), "Original: a.docx", "<fake:Fake|>", SIZE, "000000", False, False)
    assert len(p.of("text")) == 7 and y_end == pytest.approx(100 + report_height(info, reg, bold))
    assert (TITLE, GAP) == ("Comparison summary", 24.0)


def test_long_names_are_trimmed_to_the_width():
    reg, bold = FR.face(None), FR.face(None, bold=True)
    info = _info(original="x" * 300)
    p = RecordingPainter()
    p.page(612, 792)
    draw_report(info, 72, 100, 468, reg, bold, p)
    t = p.of("text")[1][3]
    assert t.startswith("Original: x") and t.endswith("...") and reg.width(t, SIZE) <= 468


def test_synthetic_bold_title_is_faked():
    from calandria.layout.pages import FontRef
    bold = FontRef("<f>", 0, "F", True, False, True)
    bold.width = lambda t, s: 0.5 * s * len(t)             # noqa: E731
    bold.line_height = lambda s: 1.2 * s                   # noqa: E731
    bold.ascent = lambda s: 0.8 * s                         # noqa: E731
    p = RecordingPainter()
    p.page(612, 792)
    draw_report(_info(), 72, 100, 468, FR.face(None), bold, p)
    assert p.ops[2][-2:] == (True, False)


def test_changed_only_adds_one_line_at_the_end():
    s = {"total": 1, "insertions": 1, "deletions": 0, "amendments": 0, "numbering": 0, "formatting": 0}
    base = ReportInfo("a.docx", "b.docx", datetime(2026, 9, 9, 14, 5), "Standard", s, False, True)
    on = ReportInfo("a.docx", "b.docx", datetime(2026, 9, 9, 14, 5), "Standard", s, False, True, changed_only=(2, 3))
    assert report_lines(on) == report_lines(base) + ["Changed pages only: 2 of 3 pages"]
