"""PDF performance: the hundred-page pair of test_perf_layout, compared, laid out and written
to PDF, must stay under the 30 s bar end to end (the PDF alone well under half of it)."""
import io
import os
import time

import pytest

from calandria.diff.compare import compare
from calandria.docx.parser import parse_docx
from calandria.layout.engine import layout
from calandria.layout.fonts import default_dirs
from calandria.pdf.draw import PdfOptions
from calandria.pdf.report import report_info
from calandria.pdf.writer import render
from calandria.testing.makedocx import DOC, make_docx
from calandria.testing.perfdoc import hundred_page_pair

pytestmark = pytest.mark.skipif(not any(os.path.isdir(d) for d in default_dirs()),
                                reason="no system font directory on this machine")


def test_hundred_page_pair_writes_a_pdf_under_budget():
    a, b = hundred_page_pair()
    docs = [parse_docx(io.BytesIO(make_docx({"word/document.xml": DOC(x)}))) for x in (a, b)]
    t0 = time.perf_counter()
    cmp = compare(*docs)
    L = layout(cmp)
    t1 = time.perf_counter()
    data, res = render(L, report_info(cmp, "a.docx", "b.docx", "Standard"), PdfOptions())
    t2 = time.perf_counter()
    assert res.pages in (L.page_count, L.page_count + 1) and L.page_count >= 60
    assert data.startswith(b"%PDF")
    assert t2 - t0 < 30, f"end to end {t2 - t0:.1f}s"
    assert t2 - t1 < 15, f"pdf {t2 - t1:.1f}s"
