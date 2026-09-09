"""Viewer gate: for every corpus pair the session's payload has one well-formed SVG per layout
page, every numbered change has an anchor and every mark points at a numbered change, and the
payload is JSON. Not compared with the reference engine (which has no page model)."""
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime

import pytest

from calandria.layout.fonts import default_dirs
from calandria.server.session import Options, Session
from calandria.viewer.svg import SVG_NS

from .common import CORPUS, pairs

pytestmark = pytest.mark.skipif(not any(os.path.isdir(d) for d in default_dirs()),
                                reason="no system font directory on this machine")
WHEN = datetime(2026, 9, 9, 12, 0)


def _session(pair) -> Session:
    s = Session(clock=lambda: WHEN)
    s.load(pair["a"], (CORPUS / pair["a"]).read_bytes(), pair["b"], (CORPUS / pair["b"]).read_bytes())
    return s


@pytest.mark.parametrize("pair", pairs(), ids=lambda p: p["alias"])
def test_payload_pages_anchors_and_marks_agree_with_the_layout_and_the_changes(pair):
    s = _session(pair)
    d = s.payload()
    assert d["page_count"] == s.layout.page_count == len(d["pages"]), pair["alias"]
    for i, svg in enumerate(d["pages"]):
        root = ET.fromstring(svg)
        page = s.layout.pages[i]
        assert root.get("viewBox") == f"0 0 {page.w:.2f} {page.h:.2f}", (pair["alias"], i)
    cids = {r["cid"] for r in d["changes"] if r["cid"] is not None}
    assert set(d["anchors"]) == cids, (pair["alias"], sorted(set(d["anchors"]) ^ cids))
    for page, top, height, mcids in d["marks"]:
        assert 1 <= page <= d["page_count"] and height > 0 and set(mcids) <= cids, (pair["alias"], page, mcids)
    for cid, a in d["anchors"].items():
        assert 1 <= a["page"] <= d["page_count"], (pair["alias"], cid)
    json.dumps(d)


def test_hidden_unchanged_keeps_every_anchor():
    pair = pairs()[0]
    s = _session(pair)
    s.relayout(Options(show_equal=False))
    d = s.payload()
    cids = {r["cid"] for r in d["changes"] if r["cid"] is not None}
    assert set(d["anchors"]) == cids and d["page_count"] <= s.layout.page_count


def test_texts_carry_the_resolved_family():
    pair = pairs()[0]
    d = _session(pair).payload()
    families = {t.get("font-family") for svg in d["pages"] for t in ET.fromstring(svg).iter(f"{{{SVG_NS}}}text")}
    assert families and all(f for f in families)
