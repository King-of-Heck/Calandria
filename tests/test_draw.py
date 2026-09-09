import io

from calandria.diff.compare import compare
from calandria.docx.parser import parse_docx
from calandria.layout.engine import layout
from calandria.layout.pages import FontRef
from calandria.layout.pieces import LayoutOptions
from calandria.pdf.draw import BLACK, PdfOptions, cid_label, draw_runs
from calandria.pdf.rendersets import BLACK_AND_WHITE, STANDARD
from calandria.testing.fakefonts import FakeResolver
from calandria.testing.makedocx import DOC, P, PR, R, STYLES, make_docx
from calandria.testing.recpaint import RecordingPainter

FR = FakeResolver()                       # 5 pt per character at size 10, line height 12, ascent 8
STY = STYLES('<w:rFonts w:ascii="Fake"/><w:sz w:val="20"/>')


def _parse(body):
    return parse_docx(io.BytesIO(make_docx({"word/document.xml": DOC(body), "word/styles.xml": STY})))


def _lay(a, b, **opts):
    return layout(compare(_parse(a), _parse(b)), LayoutOptions(fonts=FR, **opts))


def _runs(L, rs=STANDARD, page=0, line=0):
    p = RecordingPainter()
    ln = L.pages[page].lines[line]
    draw_runs(ln, ln.runs, L.fonts, rs, p)
    return p


def test_options_defaults():
    o = PdfOptions()
    assert (o.render_set, o.change_bars, o.report, o.fonts, o.now) == ("Standard", True, "last", None, None)


def test_equal_run_is_black_text_without_rules():
    p = _runs(_lay(P("aaaa"), P("aaaa")))
    assert p.ops == [("text", 72, 80, "aaaa", "<fake:Fake|>", 10, BLACK, False, False)]


def test_inserted_run_is_blue_with_a_double_underline():
    p = _runs(_lay(P("aaaa"), P("aaaa bbbb")))
    # "aaaa" (eq, x 72-92), " " (ins, 92-97), "bbbb" (ins, 97-117): a space draws rules, no text
    assert p.of("text") == [("text", 72, 80, "aaaa", "<fake:Fake|>", 10, BLACK, False, False),
                            ("text", 97, 80, "bbbb", "<fake:Fake|>", 10, "0000ff", False, False)]
    assert p.of("rule") == [("rule", 92, 97, 80.8, 0.45, "0000ff", False), ("rule", 92, 97, 82.0, 0.45, "0000ff", False),
                            ("rule", 97, 117, 80.8, 0.45, "0000ff", False), ("rule", 97, 117, 82.0, 0.45, "0000ff", False)]


def test_deleted_run_is_red_and_struck():
    p = _runs(_lay(P("aaaa bbbb"), P("aaaa")))
    assert ("text", 97, 80, "bbbb", "<fake:Fake|>", 10, "ff0000", False, False) in p.ops
    assert ("rule", 97, 117, 77.4, 0.6, "ff0000", False) in p.ops


def test_black_and_white_set_keeps_effects_and_drops_colour():
    p = _runs(_lay(P("aaaa"), P("aaaa bbbb")), BLACK_AND_WHITE)
    assert {o[6] for o in p.of("text")} == {BLACK} and {o[5] for o in p.of("rule")} == {BLACK}
    assert len(p.of("rule")) == 4


def test_document_colour_and_underline_survive_on_equal_text():
    body = PR(R("aaaa", '<w:u w:val="single"/><w:color w:val="00AA00"/>'))
    p = _runs(_lay(body, body))
    assert p.ops == [("text", 72, 80, "aaaa", "<fake:Fake|>", 10, "00aa00", False, False),
                     ("rule", 72, 92, 81.1, 0.6, "00aa00", False)]


def test_document_underline_on_an_insertion_is_not_drawn_twice():
    a = P("aaaa")
    b = PR(R("aaaa") + R(" bbbb", '<w:u w:val="single"/>'))
    p = _runs(_lay(a, b))
    ys = sorted({o[3] for o in p.of("rule")})
    assert ys == [80.8, 82.0]                      # the double underline only


def test_formatting_change_draws_a_dotted_purple_underline():
    a = P("aaaa bbbb")
    b = PR(R("aaaa ") + R("bbbb", "<w:b/>"))
    p = _runs(_lay(a, b))
    assert ("text", 97, 80, "bbbb", "<fake:Fake|B>", 10, "7c3aed", False, False) in p.ops
    assert ("rule", 97, 117, 81.1, 0.6, "7c3aed", True) in p.ops
    assert ("text", 72, 80, "aaaa", "<fake:Fake|>", 10, BLACK, False, False) in p.ops


def test_formatting_hidden_draws_plain_text():
    a = P("aaaa bbbb")
    b = PR(R("aaaa ") + R("bbbb", "<w:b/>"))
    p = _runs(_lay(a, b, show_formatting=False))
    assert p.of("rule") == [] and {o[6] for o in p.of("text")} == {BLACK}


def test_synthetic_face_is_faked():
    L = _lay(P("aaaa"), P("aaaa"))
    key = L.pages[0].lines[0].runs[0].face
    L.fonts[key] = FontRef("<fake:Fake|>", 0, "Fake", True, True, True)
    p = _runs(L)
    assert p.ops[0][-2:] == (True, True)
    L.fonts[key] = FontRef("<fake:Fake|>", 0, "Fake", True, False, True)
    assert _runs(L).ops[0][-2:] == (True, False)
    L.fonts[key] = FontRef("<fake:Fake|B>", 0, "Fake", True, False, False)
    assert _runs(L).ops[0][-2:] == (False, False)


def test_bold_italic_effects_are_faked():
    from calandria.pdf.rendersets import CatStyle, RenderSet
    rs = RenderSet("X", insert=CatStyle("000000", frozenset({"bold", "italic", "underline"})),
                   delete=STANDARD.delete, formatting=STANDARD.formatting,
                   move_from=STANDARD.move_from, move_to=STANDARD.move_to)
    p = _runs(_lay(P("aaaa"), P("aaaa bbbb")), rs)
    assert ("text", 97, 80, "bbbb", "<fake:Fake|>", 10, BLACK, True, True) in p.ops
    assert ("rule", 97, 117, 81.1, 0.6, BLACK, False) in p.ops


def test_cid_label():
    assert cid_label([1]) == "1" and cid_label([2, 3]) == "2-3" and cid_label([3, 2]) == "2-3"
    assert cid_label([1, 2, 3, 5, 7, 8]) == "1-3, 5, 7-8" and cid_label([4, 4]) == "4"
