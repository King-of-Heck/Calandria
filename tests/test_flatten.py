from calandria.docx.parser import parse_docx
from calandria.harness.flatten import flatten
from calandria.testing.makedocx import make_docx, DOC, P, W_NS


def test_flatten_shape_and_empty_paragraphs_dropped():
    # Heading comes from an explicit style ("Heading2" here, via the styleId fallback --
    # see the heading tests below), never from a raw <w:outlineLvl>.
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
                            "lineExactPt", "keepNext", "keepLines", "pageBreakBefore", "contextualSpacing",
                            "heading", "boldRuns", "tbl"}
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


def test_heading_from_title_style_id():
    # SorkWhare hardcodes styleId "Title" (Word's built-in Title style) as heading 1,
    # regardless of the style's declared name.
    styles = (f'<w:styles xmlns:w="{W_NS}"><w:style w:type="paragraph" w:styleId="Title">'
              '<w:name w:val="Title"/></w:style></w:styles>')
    recs = flatten(parse_docx(make_docx({"word/document.xml": DOC(P("Contract Name", ppr='<w:pStyle w:val="Title"/>')),
                                          "word/styles.xml": styles})))
    assert recs[0]["heading"] == 1


def test_heading_from_style_name():
    # A custom styleId that doesn't itself look like "HeadingN" still becomes a heading when
    # the style's declared NAME matches "heading \d" (checked before the styleId fallback).
    styles = (f'<w:styles xmlns:w="{W_NS}"><w:style w:type="paragraph" w:styleId="MySectionHead">'
              '<w:name w:val="Heading 3"/></w:style></w:styles>')
    recs = flatten(parse_docx(make_docx({"word/document.xml": DOC(P("Section", ppr='<w:pStyle w:val="MySectionHead"/>')),
                                          "word/styles.xml": styles})))
    assert recs[0]["heading"] == 3


def test_heading_from_style_id_when_style_undefined():
    # SorkWhare falls back to matching "HeadingN" against the styleId itself even when the
    # style isn't found in styles.xml at all (no styles part supplied here).
    recs = flatten(parse_docx(make_docx({"word/document.xml": DOC(P("Section", ppr='<w:pStyle w:val="Heading3"/>'))})))
    assert recs[0]["heading"] == 3


def test_outline_lvl_alone_is_not_a_heading():
    # A raw <w:outlineLvl> with no Heading/Title style attached is NOT a heading in the
    # reference -- `heading` derives purely from styleId/style-name, never from outlineLvl.
    # The model still keeps outline_level itself (Word semantics) for other consumers.
    d = parse_docx(make_docx({"word/document.xml": DOC(P("plain", ppr='<w:outlineLvl w:val="1"/>'))}))
    assert d.blocks[0].props.outline_level == 1
    recs = flatten(d)
    assert recs[0]["heading"] is None


def _one(body, **parts):
    return flatten(parse_docx(make_docx({"word/document.xml": DOC(body), **parts})))[0]


def test_bold_runs_over_collapsed_text():
    # Indices are character offsets into the COLLAPSED text: runs of whitespace become one
    # space, and leading/trailing whitespace is dropped, before the ranges are taken. A space
    # that swallows another space keeps bold if EITHER of them was bold -- so the space between
    # two bold words is bold and the two words form a single range. Values verified against the
    # reference engine on this same paragraph.
    rec = _one('<w:p><w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">  Bold  </w:t></w:r>'
               '<w:r><w:t xml:space="preserve"> plain </w:t></w:r>'
               '<w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve"> Two </w:t></w:r>'
               '<w:r><w:rPr><w:b/></w:rPr><w:t>Words</w:t></w:r>'
               '<w:r><w:t xml:space="preserve">   </w:t></w:r></w:p>')
    assert rec["text"] == "Bold plain Two Words"
    assert rec["boldRuns"] == [[0, 5], [10, 20]]
    assert rec["text"][0:5] == "Bold " and rec["text"][10:20] == " Two Words"


def test_bold_runs_empty_when_nothing_is_bold():
    assert _one(P("plain text"))["boldRuns"] == []


def test_bold_runs_are_run_level_only():
    # Bold from a paragraph style is deliberately not resolved (see parser._run_props), so a
    # paragraph whose style is bold still reports no bold ranges.
    styles = (f'<w:styles xmlns:w="{W_NS}"><w:style w:type="paragraph" w:styleId="Strong">'
              '<w:name w:val="Strong"/><w:rPr><w:b/></w:rPr></w:style></w:styles>')
    rec = _one(P("styled", ppr='<w:pStyle w:val="Strong"/>'), **{"word/styles.xml": styles})
    assert rec["boldRuns"] == []


def test_line_exact_pt_emitted():
    exact = _one('<w:p><w:pPr><w:spacing w:line="320" w:lineRule="exact"/></w:pPr>'
                 '<w:r><w:t>exact line</w:t></w:r></w:p>')
    assert exact["lineExactPt"] == 16.0 and exact["lineSpacing"] is None
    auto = _one('<w:p><w:pPr><w:spacing w:line="360" w:lineRule="auto"/></w:pPr>'
                '<w:r><w:t>auto line</w:t></w:r></w:p>')
    assert auto["lineExactPt"] is None and auto["lineSpacing"] == 1.5
