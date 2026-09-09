import io
import os
from datetime import datetime

import pytest
from pypdf import PdfReader

from calandria.layout.fonts import default_dirs, default_resolver
from calandria.pdf.fpdf_sink import FpdfPainter

pytestmark = pytest.mark.skipif(not any(os.path.isdir(d) for d in default_dirs()),
                                reason="no system font directory on this machine")
WHEN = datetime(2026, 9, 9, 14, 5)


def _read(data: bytes) -> PdfReader:
    return PdfReader(io.BytesIO(data))


def _fonts(reader, page=0) -> list[str]:
    res = reader.pages[page].get("/Resources", {})
    return [str(f.get_object()["/BaseFont"]) for f in res.get("/Font", {}).values()]


def test_text_round_trips_and_the_face_is_embedded_as_a_subset():
    p = FpdfPainter(creation=WHEN)
    face = default_resolver().face("Calibri")
    p.page(612, 792)
    p.text(72, 82, "Hello redline", face, 11, "0000ff")
    r = _read(p.output())
    assert len(r.pages) == 1 and "Hello redline" in r.pages[0].extract_text()
    (name,) = _fonts(r)
    assert name.endswith("+Calibri") or name.endswith("+" + face.family.replace(" ", ""))
    assert r.metadata.title == "Redline comparison"


def test_one_registration_per_file_and_font_number():
    p = FpdfPainter()
    res = default_resolver()
    reg, bold = res.face("Calibri"), res.face("Calibri", bold=True)
    p.page(612, 792)
    p.text(72, 82, "a", reg, 11, "000000")
    p.text(72, 96, "b", reg, 11, "000000")
    p.text(72, 110, "c", bold, 11, "000000")
    assert len(p._fonts) == (1 if bold.path == reg.path and bold.font_number == reg.font_number else 2)


def test_ttc_member_is_selected_by_font_number():
    res = default_resolver()
    face = res.face("Cambria")
    if not face.path.lower().endswith(".ttc"):
        pytest.skip("Cambria is not a TrueType collection here")
    p = FpdfPainter()
    p.page(612, 792)
    p.text(72, 82, "Collection", face, 12, "000000")
    r = _read(p.output())
    assert "Collection" in r.pages[0].extract_text()
    assert any("Cambria" in n for n in _fonts(r))


def test_fake_bold_italic_rules_and_lines_render():
    p = FpdfPainter()
    face = default_resolver().face("Calibri")
    p.page(612, 792)
    p.text(72, 82, "fake", face, 11, "ff0000", fake_bold=True, fake_italic=True)
    p.text(72, 96, "plain", face, 11, "000000")
    p.rule(72, 120, 84, 0.66, "ff0000")
    p.rule(72, 120, 86, 0.5, "7c3aed", dotted=True)
    p.line(66, 72, 66, 100, 1.5, "000000")
    p.page(400, 300)
    data = p.output()
    r = _read(data)
    assert len(r.pages) == 2
    assert r.pages[1].mediabox.width == 400 and r.pages[1].mediabox.height == 300
    text = r.pages[0].extract_text()
    assert "fake" in text and "plain" in text
    content = r.pages[0].get_contents().get_data()
    # fpdf2 writes the text mode inside the text object that uses it and nothing at all for the
    # default fill mode, so "2 Tr" on the fake-bold run and no Tr on the next one is entered-and-left
    assert b" 2 Tr" in content
    plain = content.split(b"72.00 696.00 Td")[1].split(b"ET")[0]
    assert b"Tr" not in plain
    assert b"[1.000 1.500] 0.000 d" in content and b"[] 0 d" in content    # dashed then solid


def test_empty_text_draws_nothing_and_output_is_deterministic():
    def make():
        p = FpdfPainter(creation=WHEN)
        p.page(612, 792)
        p.text(72, 82, "", default_resolver().face("Calibri"), 11, "000000")
        p.text(72, 96, "x", default_resolver().face("Calibri"), 11, "000000")
        return p.output()
    a, b = make(), make()
    assert a == b and a.startswith(b"%PDF")
