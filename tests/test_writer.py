import io
import os
from datetime import datetime

import pytest
from pypdf import PdfReader

from calandria.diff.compare import compare
from calandria.docx.parser import parse_docx
from calandria.layout.engine import layout
from calandria.layout.fonts import default_dirs, default_resolver
from calandria.pdf.draw import DrawResult, PdfOptions
from calandria.pdf.report import TITLE, report_info
from calandria.pdf.writer import render, write_pdf
from calandria.testing.makedocx import DOC, P, STYLES, TBL, make_docx

pytestmark = pytest.mark.skipif(not any(os.path.isdir(d) for d in default_dirs()),
                                reason="no system font directory on this machine")
WHEN = datetime(2026, 9, 9, 14, 5)


def _cmp(a, b, sty=None):
    parts = {"word/styles.xml": sty} if sty else {}
    docs = [parse_docx(io.BytesIO(make_docx({"word/document.xml": DOC(x), **parts}))) for x in (a, b)]
    return compare(*docs)


def _pages(data):
    r = PdfReader(io.BytesIO(data))
    return [pg.extract_text() for pg in r.pages]


def _base_fonts(data, page=0):
    res = PdfReader(io.BytesIO(data)).pages[page].get("/Resources", {})
    return [str(f.get_object()["/BaseFont"]) for f in res.get("/Font", {}).values()]


def test_redline_pdf_with_report_on_the_last_page():
    cmp = _cmp(P("Alpha stays"), P("Alpha stays") + P("Beta arrives"))
    L = layout(cmp)
    data, res = render(L, report_info(cmp, "a.docx", "b.docx", "Standard", WHEN), PdfOptions(now=WHEN))
    assert res == DrawResult(1, 1)
    (text,) = _pages(data)
    assert "Alpha stays" in text and "Beta arrives" in text
    assert TITLE in text and "Original: a.docx" in text and "Compared: 2026-09-09 14:05" in text
    assert "Changes: 1 (insertions 1, deletions 0, amendments 0, numbering 0)" in text
    assert "1" in text                                        # the gutter number


def test_write_pdf_without_report_and_black_and_white():
    cmp = _cmp(P("Alpha") + TBL([["x", "y"]], [4680, 4680]), P("Alpha") + TBL([["x", "z"]], [4680, 4680]))
    L = layout(cmp)
    data = write_pdf(L, None, PdfOptions(render_set="Black and White", now=WHEN))
    pages = _pages(data)
    assert len(pages) == L.page_count == 1 and TITLE not in pages[0]
    assert "Alpha" in pages[0] and "y" in pages[0] and "z" in pages[0]   # deleted and inserted cell text


def test_unknown_render_set_is_rejected_before_drawing():
    cmp = _cmp(P("a"), P("a"))
    with pytest.raises(KeyError):
        render(layout(cmp), None, PdfOptions(render_set="Sepia"))


def test_report_none_option_wins_over_a_supplied_report():
    cmp = _cmp(P("a"), P("a"))
    data, res = render(layout(cmp), report_info(cmp, "a", "b", "Standard", WHEN), PdfOptions(report="none"))
    assert res == DrawResult(1, None) and TITLE not in _pages(data)[0]


def test_gutter_numbers_do_not_pull_in_the_resolver_fallback():
    if default_resolver().resolve_family("Georgia") != "Georgia":
        pytest.skip("Georgia is not installed here")
    sty = STYLES('<w:rFonts w:ascii="Georgia"/><w:sz w:val="22"/>')
    cmp = _cmp(P("Alpha stays"), P("Alpha stays") + P("Beta arrives"), sty)
    data, _ = render(layout(cmp), None, PdfOptions(report="none", now=WHEN))
    names = _base_fonts(data)
    assert names and not any("Calibri" in n for n in names), names


def test_hundred_paragraph_document_pages_match_the_layout():
    body = "".join(P(f"Paragraph {i} " + "word " * 30) for i in range(120))
    cmp = _cmp(body, body)
    L = layout(cmp)
    data, res = render(L, None, PdfOptions(report="none"))
    assert res.pages == L.page_count == len(_pages(data)) and L.page_count > 1
