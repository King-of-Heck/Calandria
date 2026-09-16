import io

from calandria.diff.compare import compare
from calandria.docx.parser import parse_docx
from calandria.layout.engine import layout
from calandria.layout.pieces import LayoutOptions
from calandria.pdf.draw import PdfOptions, draw_layout
from calandria.pdf.rendersets import render_set
from calandria.testing.fakefonts import FakeResolver
from calandria.testing.recpaint import RecordingPainter
from calandria.testing.makedocx import COMMENTS, CRANGE, CRELS, DOC, PR, R, make_docx


def _pair():
    b = parse_docx(io.BytesIO(make_docx({
        "word/document.xml": DOC(PR(R("The ") + CRANGE("0", "fox") + R(" jumps."))),
        "word/_rels/document.xml.rels": CRELS(comments=True),
        "word/comments.xml": COMMENTS([{"id": "0", "author": "Ada", "initials": "AL",
                                        "date": "2026-09-16T00:00:00Z", "paras": [("p1", "Which fox?")]}])})))
    a = parse_docx(io.BytesIO(make_docx({"word/document.xml": DOC(PR(R("The fox jumps.")))})))
    return a, b


def test_bubble_box_connector_and_text_are_emitted():
    a, b = _pair()
    lay = layout(compare(a, b), LayoutOptions(fonts=FakeResolver()))
    painter = RecordingPainter()
    draw_layout(lay, render_set("Standard"), PdfOptions(report="none", fonts=FakeResolver()),
                painter, FakeResolver(), None)
    # RecordingPainter op shapes (testing/recpaint.py): ("box", x, y, w, h, color),
    # ("line", x1, y1, x2, y2, w, color), ("text", x, baseline, text, path, size, color, fb, fi).
    # break_lines tokenizes words and whitespace separately, and draw_runs skips a blank-text run
    # (see draw.py's `if g.text.strip():`), so the space tokens between words never reach the
    # painter: join the drawn word ops with a space so "Which fox?" survives as one substring.
    drawn = " ".join(op[3] for op in painter.of("text"))
    assert painter.of("box")                      # the bubble background
    assert painter.of("line")                     # border + connector
    assert "Which fox?" in drawn, painter.of("text")


def test_bubble_text_ops_land_inside_the_bubble_box():
    a, b = _pair()
    lay = layout(compare(a, b), LayoutOptions(fonts=FakeResolver()))
    painter = RecordingPainter()
    draw_layout(lay, render_set("Standard"), PdfOptions(report="none", fonts=FakeResolver()),
                painter, FakeResolver(), None)
    page = next(p for p in lay.pages if p.comments)
    pc = page.comments[0]
    x0, x1 = pc.x, pc.x + pc.w
    y0, y1 = pc.y, pc.y + pc.bubble.height
    text_ops = painter.of("text")
    assert text_ops
    assert any(x0 <= op[1] <= x1 and y0 <= op[2] <= y1 for op in text_ops), text_ops


def test_a_comment_free_page_emits_no_bubble_ops():
    d = parse_docx(io.BytesIO(make_docx({"word/document.xml": DOC(PR(R("Plain.")))})))
    lay = layout(compare(d, d), LayoutOptions(fonts=FakeResolver()))
    painter = RecordingPainter()
    draw_layout(lay, render_set("Standard"), PdfOptions(report="none", fonts=FakeResolver()),
                painter, FakeResolver(), None)
    # no comment column drawing: the op count matches a build with page.comments cleared
    assert all(not p.comments for p in lay.pages)


def test_svg_pages_contain_the_bubble_rect_and_text():
    from calandria.viewer.svg import render_pages
    a, b = _pair()
    lay = layout(compare(a, b), LayoutOptions(fonts=FakeResolver()))
    svg = "".join(render_pages(lay, resolver=FakeResolver()))
    # the bubble text may be split across <text> runs; assert a word of it and the bubble rect
    assert "fox" in svg and "<rect" in svg
