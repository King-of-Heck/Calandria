"""Layout performance: a revised document of about a hundred pages (1500 paragraphs of 40
words), compared and laid out with the system fonts, must stay well under the 30 s bar."""
import io
import os
import time

import pytest

from delta.diff.compare import compare
from delta.docx.parser import parse_docx
from delta.layout.engine import layout
from delta.layout.fonts import default_dirs
from delta.testing.makedocx import DOC, make_docx
from delta.testing.perfdoc import hundred_page_pair

pytestmark = pytest.mark.skipif(not any(os.path.isdir(d) for d in default_dirs()),
                                reason="no system font directory on this machine")


def test_hundred_page_pair_lays_out_under_budget():
    a, b = hundred_page_pair()
    docs = [parse_docx(io.BytesIO(make_docx({"word/document.xml": DOC(x)}))) for x in (a, b)]
    t0 = time.perf_counter()
    L = layout(compare(*docs))
    elapsed = time.perf_counter() - t0
    assert 60 <= L.page_count <= 200, L.page_count
    assert elapsed < 20, f"{elapsed:.1f}s"
