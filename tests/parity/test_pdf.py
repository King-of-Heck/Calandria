"""PDF gate: for every corpus pair the redline PDF has exactly the layout's page count and its
text reads back (the first real word of the first line is on page 1). Never compared with the
reference engine's PDF (a browser print), and not a golden digest: font subsets differ by
machine, so the file bytes are not pinned."""
import io
import os
from datetime import datetime

import pytest
from pypdf import PdfReader

from calandria.diff.compare import compare
from calandria.layout.engine import layout
from calandria.layout.fonts import default_dirs
from calandria.pdf.draw import PdfOptions
from calandria.pdf.report import TITLE, report_info
from calandria.pdf.writer import render

from .common import CORPUS, pairs, parse_cached

pytestmark = pytest.mark.skipif(not any(os.path.isdir(d) for d in default_dirs()),
                                reason="no system font directory on this machine")
WHEN = datetime(2026, 9, 9, 12, 0)


def _first_word(lay) -> str | None:
    # Scoped to page 1 only: the docstring's claim is that word is *on page 1*, so a hit
    # further into the document (e.g. gen-longcap's 2100-token stress paragraph, whose only
    # true alpha word lands on page 5 of 6) must not be checked against page 1's text.
    for ln in lay.pages[0].lines:
        for r in ln.runs:
            for w in r.text.split():
                if len(w) >= 3 and w.isalpha():
                    return w
    return None


@pytest.mark.parametrize("pair", pairs(), ids=lambda p: p["alias"])
def test_pdf_page_count_equals_the_layout_and_text_reads_back(pair):
    cmp = compare(parse_cached(CORPUS / pair["a"]), parse_cached(CORPUS / pair["b"]))
    lay = layout(cmp)
    data, res = render(lay, None, PdfOptions(report="none", now=WHEN))
    reader = PdfReader(io.BytesIO(data))
    assert len(reader.pages) == lay.page_count == res.pages, pair["alias"]
    word = _first_word(lay)
    if word is not None:
        assert word in reader.pages[0].extract_text(), (pair["alias"], word)


def test_report_lands_on_the_last_page_or_one_after():
    pair = pairs()[0]
    cmp = compare(parse_cached(CORPUS / pair["a"]), parse_cached(CORPUS / pair["b"]))
    lay = layout(cmp)
    data, res = render(lay, report_info(cmp, pair["a"], pair["b"], "Standard", WHEN), PdfOptions(now=WHEN))
    reader = PdfReader(io.BytesIO(data))
    assert res.pages in (lay.page_count, lay.page_count + 1) and res.report_page == res.pages
    assert len(reader.pages) == res.pages
    assert TITLE in reader.pages[-1].extract_text()
