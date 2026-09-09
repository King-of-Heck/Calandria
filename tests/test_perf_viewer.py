"""Viewer performance: the hundred-page pair through the session (parse, compare, layout, SVG
pages, payload) must stay under the 30 s bar; a restyle (new rendering set) well under it."""
import json
import os
import time

import pytest

from calandria.layout.fonts import default_dirs
from calandria.server.session import Session
from calandria.testing.makedocx import DOC, make_docx
from calandria.testing.perfdoc import hundred_page_pair

pytestmark = pytest.mark.skipif(not any(os.path.isdir(d) for d in default_dirs()),
                                reason="no system font directory on this machine")


def test_hundred_page_pair_through_the_session_under_budget():
    a, b = hundred_page_pair()
    s = Session()
    t0 = time.perf_counter()
    s.load("a.docx", make_docx({"word/document.xml": DOC(a)}), "b.docx", make_docx({"word/document.xml": DOC(b)}))
    d = s.payload()
    body = json.dumps(d)
    t1 = time.perf_counter()
    s.pages("Black and White")
    t2 = time.perf_counter()
    assert d["page_count"] >= 60 and len(d["pages"]) == d["page_count"]
    assert t1 - t0 < 30, f"load + payload {t1 - t0:.1f}s"
    assert t2 - t1 < 10, f"restyle {t2 - t1:.1f}s"
    assert len(body) < 64 * 1024 * 1024, f"payload {len(body) / 1e6:.1f} MB"
