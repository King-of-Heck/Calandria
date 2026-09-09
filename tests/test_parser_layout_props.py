import io

from calandria.docx.parser import parse_docx
from calandria.testing.makedocx import DOC, NUMBERING, P, TBL, W_NS, make_docx


def _doc(body, **parts):
    parts = {"word/document.xml": DOC(body), **parts}
    return parse_docx(io.BytesIO(make_docx(parts)))


def test_section_break_flag_marks_the_closing_paragraph():
    d = _doc(P("cover", ppr='<w:sectPr><w:pgSz w:w="12240" w:h="15840"/></w:sectPr>') + P("body") + P("more"))
    flags = [p.props.section_break for p in d.paragraphs()]
    assert flags == [True, False, False]
    assert len(d.sections) == 2


def test_numbering_carries_suffix_and_justification():
    num = NUMBERING([("decimal", "%1.", 720, 360, "space")])
    d = _doc(P("Item", ppr='<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>'),
             **{"word/numbering.xml": num})
    p = next(d.paragraphs())
    assert p.num.marker == "1." and p.num.suff == "space" and p.num.jc == "left"


def test_numbering_suffix_defaults_to_tab():
    num = NUMBERING([("decimal", "%1.", 720, 360, None)])
    d = _doc(P("Item", ppr='<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>'),
             **{"word/numbering.xml": num})
    assert next(d.paragraphs()).num.suff == "tab"


def test_default_tab_stop_from_settings():
    settings = f'<w:settings xmlns:w="{W_NS}"><w:defaultTabStop w:val="360"/></w:settings>'
    assert _doc(P("x"), **{"word/settings.xml": settings}).default_tab_pt == 18.0
    assert _doc(P("x")).default_tab_pt == 36.0


def test_zero_default_tab_stop_is_kept():
    settings = f'<w:settings xmlns:w="{W_NS}"><w:defaultTabStop w:val="0"/></w:settings>'
    assert _doc(P("x"), **{"word/settings.xml": settings}).default_tab_pt == 0.0


def test_right_indent_is_read_from_both_spellings():
    props = _doc(P("x", ppr='<w:ind w:right="720"/>')).blocks[0].props
    assert props.ind_right_pt == 36.0
    assert _doc(P("x", ppr='<w:ind w:end="1440"/>')).blocks[0].props.ind_right_pt == 72.0
    assert _doc(P("x")).blocks[0].props.ind_right_pt == 0.0


def test_table_indent_grid_and_row_heights():
    tblpr = '<w:tblPr><w:tblInd w:w="288" w:type="dxa"/></w:tblPr>'
    body = ("<w:tbl>" + tblpr + '<w:tblGrid><w:gridCol w:w="2880"/><w:gridCol w:w="1440"/></w:tblGrid>'
            '<w:tr><w:trPr><w:trHeight w:val="600" w:hRule="exact"/></w:trPr><w:tc>' + P("a") + "</w:tc><w:tc>"
            + P("b") + "</w:tc></w:tr>"
            '<w:tr><w:trPr><w:trHeight w:val="400"/></w:trPr><w:tc>' + P("c") + "</w:tc><w:tc>" + P("d")
            + "</w:tc></w:tr>"
            "<w:tr><w:tc>" + P("e") + "</w:tc><w:tc>" + P("f") + "</w:tc></w:tr></w:tbl>")
    t = _doc(body).blocks[0]
    assert t.ind_pt == 14.4 and t.grid_pt == [144.0, 72.0]
    assert (t.rows[0].height_pt, t.rows[0].height_rule) == (30.0, "exact")
    assert (t.rows[1].height_pt, t.rows[1].height_rule) == (20.0, "atLeast")
    assert (t.rows[2].height_pt, t.rows[2].height_rule) == (None, None)


def test_makedocx_tbl_grid_helper():
    t = _doc(TBL([["a", "b"]], grid=[1440, 1440])).blocks[0]
    assert t.grid_pt == [72.0, 72.0] and t.ind_pt == 0.0
