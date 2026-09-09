import io
import json

import pytest

from calandria.diff.compare import compare
from calandria.docx.parser import parse_docx
from calandria.layout.engine import layout, layout_document
from calandria.layout.pieces import LayoutOptions
from calandria.testing.makedocx import DOC, P, STYLES, TBL, make_docx
from calandria.testing.fakefonts import FakeResolver

FR = FakeResolver()                       # 5 pt per character at size 10, line height 12, ascent 8
STY = STYLES('<w:rFonts w:ascii="Fake"/><w:sz w:val="20"/>')
LETTER = '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/></w:sectPr>'


def _parse(body):
    return parse_docx(io.BytesIO(make_docx({"word/document.xml": DOC(body), "word/styles.xml": STY})))


def _lay(a, b, **opts):
    return layout(compare(_parse(a), _parse(b)), LayoutOptions(fonts=FR, **opts))


def test_single_paragraph_geometry():
    L = _lay(P("aaaa bbbb"), P("aaaa bbbb"))
    assert L.page_count == 1
    pg = L.pages[0]
    assert (pg.number, pg.w, pg.h, pg.margin_left, pg.margin_top, pg.section) == (1, 612, 792, 72, 72, 0)
    (ln,) = pg.lines
    assert (ln.x, ln.top, ln.height, ln.baseline, ln.changed, ln.row_index) == (72, 72, 12, 80, False, 0)
    assert [(r.text, r.x, r.w, r.mode) for r in ln.runs] == [("aaaa", 72, 20, "eq"), (" ", 92, 5, "eq"),
                                                             ("bbbb", 97, 20, "eq")]
    assert ln.runs[0].face == "Fake|" and L.fonts["Fake|"].path == "<fake:Fake|>"


def test_page_count_follows_line_heights():
    body = "".join(P(f"p{i}") for i in range(100))       # 648 pt of body / 12 pt = 54 lines per page
    L = _lay(body, body)
    assert L.page_count == 2 and len(L.pages[0].lines) == 54 and len(L.pages[1].lines) == 46
    assert L.pages[1].number == 2 and L.pages[1].lines[0].top == 72


def test_paragraph_spacing_stacks():
    body = P("a") + P("b", ppr='<w:spacing w:before="200"/>')
    L = _lay(body, body)
    assert [ln.top for ln in L.pages[0].lines] == [72, 94]


def test_justify_stretches_every_line_but_the_last():
    body = P(" ".join(["aaaa"] * 30), ppr='<w:jc w:val="both"/>')      # 18 words per 468 pt line
    L = _lay(body, body)
    l0, l1 = L.pages[0].lines
    assert l0.runs[-1].x + l0.runs[-1].w == pytest.approx(72 + 468)
    assert l1.runs[-1].x + l1.runs[-1].w < 72 + 468 - 1


def test_center_and_right_alignment():
    body = P("aaaa", ppr='<w:jc w:val="center"/>') + P("aaaa", ppr='<w:jc w:val="right"/>')
    L = _lay(body, body)
    assert [ln.x for ln in L.pages[0].lines] == [296, 520]


def test_right_indent_moves_the_alignment_box_in():
    body = P("aaaa", ppr='<w:jc w:val="right"/><w:ind w:right="800"/>')
    (ln,) = _lay(body, body).pages[0].lines
    assert ln.runs[-1].x + ln.runs[-1].w == pytest.approx(72 + 468 - 40)


def test_list_marker_is_placed_in_the_gutter():
    from calandria.testing.makedocx import NUMBERING
    num = NUMBERING([("decimal", "%1.", 720, 360, None)])
    parts = {"word/document.xml": DOC(P("Item", ppr='<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>')),
             "word/styles.xml": STY, "word/numbering.xml": num}
    d = parse_docx(io.BytesIO(make_docx(parts)))
    (ln,) = layout(compare(d, d), LayoutOptions(fonts=FR)).pages[0].lines
    assert [(r.text, r.x) for r in ln.marker] == [("1.", 90)] and ln.x == 108 and ln.runs[0].x == 108


def test_deleted_paragraph_is_laid_out_in_place():
    L = _lay(P("keep") + P("gone") + P("tail"), P("keep") + P("tail"))
    lines = L.pages[0].lines
    assert [ln.runs[0].mode for ln in lines] == ["eq", "del", "eq"]
    assert [ln.changed for ln in lines] == [False, True, False]
    assert [ln.cid_starts for ln in lines] == [[], [1], []]


def test_hide_unchanged_drops_equal_paragraphs_and_blank_lines():
    L = _lay(P("keep") + P("") + P("old"), P("keep") + P("") + P("new"), show_equal=False)
    assert [ln.runs[0].text for ln in L.pages[0].lines] == ["old", "new"]


def test_table_rows_are_boxed_and_cells_positioned():
    body = P("i") + TBL([["aaaa", "bb"], ["c", "d"]]) + P("o")
    L = _lay(body, body)
    pg = L.pages[0]
    assert len(pg.table_rows) == 2
    r0 = pg.table_rows[0]
    assert (r0.x, r0.y, r0.w, r0.h, r0.changed) == (72, 84, 468, 12, False)
    assert [(c.x, c.w, c.h) for c in r0.cells] == [(72, 234, 12), (306, 234, 12)]
    assert pg.lines[1].x == pytest.approx(77.4) and pg.lines[1].runs[0].text == "aaaa"
    assert pg.lines[-1].runs[0].text == "o" and pg.lines[-1].top == 108


def test_section_with_another_page_size_starts_a_new_page():
    body = P("cover", ppr='<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr>') + P("body") + LETTER
    L = _lay(body, body)
    assert L.page_count == 2
    assert (round(L.pages[0].w), round(L.pages[1].w)) == (595, 612)
    assert (L.pages[0].section, L.pages[1].section) == (0, 1)


def test_continuous_section_flows_on_the_same_page():
    body = (P("one", ppr='<w:sectPr><w:type w:val="continuous"/><w:pgSz w:w="11906" w:h="16838"/></w:sectPr>')
            + P("two") + LETTER)
    L = _lay(body, body)
    assert L.page_count == 1 and len(L.pages[0].lines) == 2 and round(L.pages[0].w) == 595


def test_layout_document_equals_a_self_comparison():
    body = "".join(P(f"p{i}") for i in range(60))
    d = _parse(body)
    assert layout_document(d, LayoutOptions(fonts=FR)).page_count == layout(compare(d, d), LayoutOptions(fonts=FR)).page_count == 2


def test_to_dict_is_json_serialisable():
    L = _lay(P("aaaa") + TBL([["x"]]), P("aaaa") + TBL([["x"]]))
    d = json.loads(json.dumps(L.to_dict()))
    assert d["page_count"] == 1 and d["pages"][0]["lines"][0]["runs"][0]["t"] == "aaaa"
    assert d["pages"][0]["table_rows"][0]["cells"][0]["w"] == 468
    assert d["fonts"]["Fake|"]["path"] == "<fake:Fake|>" and d["options"]["show_equal"] is True


def test_empty_document_gives_one_empty_page():
    L = _lay("", "")
    assert L.page_count == 1 and L.pages[0].lines == [] and L.pages[0].table_rows == []


def test_requires_documents_on_the_comparison():
    from calandria.diff.compare import compare_units
    from calandria.diff.units import units
    d = _parse(P("x"))
    with pytest.raises(ValueError):
        layout(compare_units(units(d), units(d)), LayoutOptions(fonts=FR))


def test_space_before_does_not_survive_onto_an_automatic_page():
    filler = "".join(P("p") for _ in range(51))
    spaced = P(" ".join(["aaaa"] * 40), ppr='<w:spacing w:before="120"/>')   # 3 lines of 18 words
    L = _lay(filler + spaced, filler + spaced)
    assert L.page_count == 2 and len(L.pages[0].lines) == 51
    assert L.pages[1].lines[0].top == 72
