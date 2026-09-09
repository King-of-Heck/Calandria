from calandria.docx.parser import parse_docx
from calandria.harness.flatten import flatten
from calandria.testing.makedocx import make_docx, DOC, P


def test_flatten_shape_and_empty_paragraphs_dropped():
    # Heading comes from an explicit style ("Heading2" here, via the styleId fallback --
    # see test_parser.py's heading tests), never from a raw <w:outlineLvl>.
    body = (P("Intro", ppr='<w:pStyle w:val="Heading2"/>') + "<w:p/>" +
            '<w:tbl><w:tr><w:tc>' + P("a") + '</w:tc><w:tc>' + P("b") + '</w:tc></w:tr>'
            '<w:tr><w:tc>' + P("c") + '</w:tc></w:tr></w:tbl>' + P("End"))
    recs = flatten(parse_docx(make_docx({"word/document.xml": DOC(body)})))
    assert [r["text"] for r in recs] == ["Intro", "a", "b", "c", "End"]
    assert recs[0]["heading"] == 2 and recs[0]["tbl"] is None
    assert recs[1]["tbl"] == {"ti": 0, "ri": 0, "ci": 0, "cols": 2}
    assert recs[3]["tbl"] == {"ti": 0, "ri": 1, "ci": 0, "cols": 2}
    assert set(recs[0]) == {"text", "marker", "isNumbered", "ilvl", "styleId", "align", "indLeftPt",
                            "indHangingPt", "indFirstLinePt", "spaceBeforePt", "spaceAfterPt", "lineSpacing",
                            "keepNext", "keepLines", "pageBreakBefore", "contextualSpacing", "heading", "tbl"}
    assert recs[0]["marker"] == "" and recs[0]["isNumbered"] is False


def test_nested_table_paragraphs_carry_outer_coordinates():
    body = ('<w:tbl><w:tr><w:tc>' + P("outer") +
            '<w:tbl><w:tr><w:tc>' + P("inner") + '</w:tc></w:tr></w:tbl>' +
            '</w:tc></w:tr></w:tbl>' +
            '<w:tbl><w:tr><w:tc>' + P("second") + '</w:tc></w:tr></w:tbl>')
    recs = flatten(parse_docx(make_docx({"word/document.xml": DOC(body)})))
    by_text = {r["text"]: r["tbl"] for r in recs}
    assert by_text["outer"] == {"ti": 0, "ri": 0, "ci": 0, "cols": 1}
    assert by_text["inner"] == {"ti": 0, "ri": 0, "ci": 0, "cols": 1}
    assert by_text["second"] == {"ti": 1, "ri": 0, "ci": 0, "cols": 1}


def test_cols_from_grid():
    body = ('<w:tbl><w:tblGrid><w:gridCol w:w="1000"/><w:gridCol w:w="1000"/>'
            '<w:gridCol w:w="1000"/></w:tblGrid>'
            '<w:tr><w:tc>' + P("a") + '</w:tc><w:tc>' + P("b") + '</w:tc></w:tr></w:tbl>')
    recs = flatten(parse_docx(make_docx({"word/document.xml": DOC(body)})))
    assert recs[0]["tbl"]["cols"] == 3
