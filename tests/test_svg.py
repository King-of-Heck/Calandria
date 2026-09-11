import io
import xml.etree.ElementTree as ET

import pytest

from calandria.diff.compare import compare
from calandria.docx.parser import parse_docx
from calandria.layout.engine import layout
from calandria.layout.pieces import LayoutOptions
from calandria.pdf.draw import PdfOptions, draw_layout
from calandria.pdf.rendersets import STANDARD
from calandria.testing.fakefonts import FakeFace, FakeResolver
from calandria.testing.makedocx import DOC, P, STYLES, TBL, make_docx
from calandria.testing.recpaint import RecordingPainter
from calandria.viewer.svg import SVG_NS, SvgPainter, render_pages

FR = FakeResolver()                       # 5 pt per character at size 10, line height 12, ascent 8
STY = STYLES('<w:rFonts w:ascii="Fake"/><w:sz w:val="20"/>')


def _parse(body):
    return parse_docx(io.BytesIO(make_docx({"word/document.xml": DOC(body), "word/styles.xml": STY})))


def _lay(a, b, **opts):
    return layout(compare(_parse(a), _parse(b)), LayoutOptions(fonts=FR, **opts))


def _texts(svg):
    return ET.fromstring(svg).findall(f"{{{SVG_NS}}}text")


def _lines(svg):
    return ET.fromstring(svg).findall(f"{{{SVG_NS}}}line")


def test_one_well_formed_svg_per_page_with_the_page_size():
    body = "".join(P(f"Paragraph {i} " + "word " * 30) for i in range(120))
    L = _lay(body, body)
    svgs = render_pages(L, resolver=FR)
    assert len(svgs) == L.page_count > 1
    for s in svgs:
        assert s.startswith(f'<svg xmlns="{SVG_NS}" viewBox="0 0 612.00 792.00" width="612.00pt" height="792.00pt">')
        assert s.endswith("</svg>")
        ET.fromstring(s)


def test_run_is_placed_at_x_and_baseline_with_family_size_colour_and_width():
    (svg,) = render_pages(_lay(P("aaaa"), P("aaaa")), resolver=FR)
    assert ('<text x="72.00" y="80.00" font-family="Fake" font-size="10.00" fill="#000000" '
            'textLength="20.00" lengthAdjust="spacing" xml:space="preserve">aaaa</text>') in svg
    (t,) = _texts(svg)
    assert t.text == "aaaa" and t.get("font-weight") is None and t.get("stroke") is None


def test_insertion_is_blue_with_two_underlines_at_the_decor_offsets():
    (svg,) = render_pages(_lay(P("aaaa"), P("aaaa bbbb")), change_bars=False, resolver=FR)
    ins = [t for t in _texts(svg) if t.text == "bbbb"]
    assert len(ins) == 1 and ins[0].get("fill") == "#0000ff" and ins[0].get("x") == "97.00"
    ys = sorted((ln.get("y1"), ln.get("stroke-width")) for ln in _lines(svg) if ln.get("x1") == "97.00")
    assert ys == [("80.80", "0.45"), ("82.00", "0.45")]
    assert all(ln.get("stroke") == "#0000ff" for ln in _lines(svg))


def test_black_and_white_without_change_bars():
    L = _lay(P("aaaa"), P("aaaa bbbb"))
    (svg,) = render_pages(L, "Black and White", change_bars=False, resolver=FR)
    assert "#0000ff" not in svg
    assert not [ln for ln in _lines(svg) if ln.get("stroke-width") == "1.50"]
    (bars,) = render_pages(L, "Standard", change_bars=True, resolver=FR)
    assert [ln for ln in _lines(bars) if ln.get("stroke-width") == "1.50" and ln.get("x1") == "66.00"]


def test_unknown_render_set_raises():
    with pytest.raises(KeyError):
        render_pages(_lay(P("a"), P("a")), "Sepia", resolver=FR)


def test_same_ops_as_the_recording_painter():
    L = _lay(P("aaaa") + TBL([["x", "y"]], [4680, 4680]), P("aaaa bbbb") + TBL([["x", "z"]], [4680, 4680]))
    rec, svgp = RecordingPainter(), SvgPainter()
    opts = PdfOptions(report="none")
    draw_layout(L, STANDARD, opts, rec, FR, None)
    draw_layout(L, STANDARD, opts, svgp, FR, None)
    svgs = svgp.pages()
    assert len(svgs) == rec.pages == 1
    assert len(_texts(svgs[0])) == len([o for o in rec.of("text") if o[3]])
    assert len(_lines(svgs[0])) == len(rec.of("rule")) + len(rec.of("line"))
    assert [ln for ln in _lines(svgs[0]) if ln.get("stroke-width") == "0.50"]        # the grid


def test_dotted_rule_has_the_dash_array():
    p = SvgPainter()
    p.page(100, 100)
    p.rule(10, 20, 30, 0.6, "7c3aed", dotted=True)
    p.rule(10, 20, 40, 0.6, "7c3aed")
    (svg,) = p.pages()
    assert '<line x1="10.00" y1="30.00" x2="20.00" y2="30.00" stroke="#7c3aed" stroke-width="0.60" stroke-dasharray="1.00 1.50"/>' in svg
    assert '<line x1="10.00" y1="40.00" x2="20.00" y2="40.00" stroke="#7c3aed" stroke-width="0.60"/>' in svg


def test_fake_bold_strokes_and_fake_italic_skews_about_the_baseline_origin():
    p = SvgPainter()
    p.page(100, 100)
    face = FakeFace("Fake", False, False, 0.5, 1.2, 0.8)
    p.text(10, 20, "ab", face, 10, "ff0000", fake_bold=True)
    p.text(10, 40, "ab", face, 10, "ff0000", fake_italic=True)
    (svg,) = p.pages()
    bold, italic = _texts(svg)
    assert bold.get("stroke") == "#ff0000" and bold.get("stroke-width") == "0.30" and bold.get("transform") is None
    assert italic.get("transform") == "translate(10.00 40.00) skewX(-12) translate(-10.00 -40.00)"
    assert italic.get("stroke") is None


def test_real_bold_face_uses_font_weight_but_a_synthetic_one_does_not():
    p = SvgPainter()
    p.page(100, 100)
    real = FakeFace("Fake", True, True, 0.5, 1.2, 0.8)
    synthetic = FakeFace("Fake", True, True, 0.5, 1.2, 0.8)
    synthetic.synthetic = True
    p.text(10, 20, "ab", real, 10, "000000")
    p.text(10, 40, "ab", synthetic, 10, "000000", fake_bold=True, fake_italic=True)
    (svg,) = p.pages()
    a, b = _texts(svg)
    assert (a.get("font-weight"), a.get("font-style")) == ("bold", "italic") and a.get("stroke") is None
    assert b.get("font-weight") is None and b.get("font-style") is None
    assert b.get("stroke") == "#000000" and "skewX" in b.get("transform")


def test_text_and_family_are_escaped_and_empty_text_is_skipped():
    p = SvgPainter()
    p.page(100, 100)
    face = FakeFace('Fa"ke <Sans>', False, False, 0.5, 1.2, 0.8)
    p.text(10, 20, 'a<b & "c"', face, 10, "000000")
    p.text(10, 30, "", face, 10, "000000")
    (svg,) = p.pages()
    (t,) = _texts(svg)
    assert t.text == 'a<b & "c"' and t.get("font-family") == 'Fa"ke <Sans>'


def test_zero_width_gets_no_text_length():
    p = SvgPainter()
    p.page(100, 100)
    face = FakeFace("Fake", False, False, 0.5, 1.2, 0.8)
    p.text(10, 20, "a", face, 10, "000000", width=0)
    p.text(10, 30, "a", face, 10, "000000")
    (svg,) = p.pages()
    assert "textLength" not in svg


def test_line_op_and_multiple_pages():
    p = SvgPainter()
    p.page(100, 100)
    p.line(1, 2, 3, 4, 0.5, "000000")
    p.page(200, 300)
    a, b = p.pages()
    assert '<line x1="1.00" y1="2.00" x2="3.00" y2="4.00" stroke="#000000" stroke-width="0.50"/>' in a
    assert b.startswith(f'<svg xmlns="{SVG_NS}" viewBox="0 0 200.00 300.00" width="200.00pt" height="300.00pt">')


def test_recording_painter_accepts_width_without_recording_it():
    p = RecordingPainter()
    face = FakeFace("Fake", False, False, 0.5, 1.2, 0.8)
    p.text(1, 2, "x", face, 10, "000000", width=5)
    assert p.ops == [("text", 1, 2, "x", "<fake:Fake|>", 10, "000000", False, False)]


def test_gutter_numerals_carry_the_class_and_anchor_at_their_right_edge():
    (svg,) = render_pages(_lay(P("aaaa"), P("aaaa") + P("bbbb")), change_bars=False, resolver=FR)
    (num,) = [t for t in _texts(svg) if t.get("class") == "gutter"]
    assert num.text == "1" and num.get("text-anchor") == "end" and num.get("textLength") is None
    assert num.get("x") == "62.00"          # margin_left 72 - NUMBER_GAP 10: the label's right edge
    assert num.get("font-size") == "7.00"
    assert all(t.get("class") is None for t in _texts(svg) if t.text != "1")


def test_side_pages_carry_tint_rects_only_with_marks():
    L = layout(compare(_parse(P("aaaa bbbb") + P("gone")), _parse(P("aaaa cccc") + P("new"))),
               LayoutOptions(fonts=FR, side="original"))
    plain = render_pages(L, resolver=FR)[0]
    marked = render_pages(L, resolver=FR, marks=True)[0]
    assert "<rect" not in plain and "<line" not in plain
    rects = ET.fromstring(marked).findall(f"{{{SVG_NS}}}rect")
    assert rects and all(r.get("fill") == "#ffd9d9" and r.get("class") == "tint" for r in rects)
    assert "<line" not in marked
