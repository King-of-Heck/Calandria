from calandria.docx.parser import parse_docx
from calandria.model import Paragraph, Table
from calandria.testing.makedocx import make_docx, DOC, P, W_NS


def _doc(body, **parts):
    return parse_docx(make_docx({"word/document.xml": DOC(body), **parts}))


def test_paragraph_runs_and_props():
    d = _doc('<w:p><w:pPr><w:jc w:val="both"/><w:ind w:left="720" w:hanging="360"/><w:keepNext/>'
             '<w:spacing w:before="120" w:after="0" w:line="360" w:lineRule="auto"/></w:pPr>'
             '<w:r><w:rPr><w:b/><w:sz w:val="24"/></w:rPr><w:t xml:space="preserve">Bold </w:t></w:r>'
             '<w:r><w:t>plain</w:t><w:tab/><w:t>x</w:t></w:r></w:p>')
    p = d.blocks[0]
    assert isinstance(p, Paragraph) and p.text == "Bold plain x"
    assert [r.text for r in p.runs] == ["Bold ", "plain\tx"]
    assert p.runs[0].props.bold and p.runs[0].props.size_pt == 12.0 and not p.runs[1].props.bold
    pr = p.props
    assert pr.align == "justify" and pr.ind_left_pt == 36.0 and pr.ind_hanging_pt == 18.0
    assert pr.keep_next and pr.space_before_pt == 6.0 and pr.space_after_pt == 0.0
    assert pr.line_spacing == 1.5 and pr.line_rule == "auto"


def test_deleted_runs_skipped_and_hyperlink_transparent():
    d = _doc('<w:p><w:del><w:r><w:delText>gone</w:delText></w:r></w:del>'
             '<w:hyperlink r:id="rId1" xmlns:r="x"><w:r><w:t>link</w:t></w:r></w:hyperlink>'
             '<w:ins><w:r><w:t> new</w:t></w:r></w:ins></w:p>')
    assert d.blocks[0].text == "link new"


def test_page_break_carries_to_next_nonempty_paragraph():
    d = _doc(P("one") + '<w:p><w:r><w:br w:type="page"/></w:r></w:p>' + P("two") +
             '<w:p><w:r><w:t>three</w:t><w:br w:type="page"/></w:r></w:p>' + P("four"))
    paras = [b for b in d.blocks if isinstance(b, Paragraph)]
    flags = [(p.text, p.props.page_break_before) for p in paras if not p.is_empty]
    assert flags == [("one", False), ("two", True), ("three", False), ("four", True)]


def test_style_chain_and_numbering(tmp_path):
    styles = (f'<w:styles xmlns:w="{W_NS}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Georgia"/>'
              '<w:sz w:val="20"/></w:rPr></w:rPrDefault></w:docDefaults>'
              '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/>'
              '<w:pPr><w:keepNext/><w:numPr><w:numId w:val="1"/><w:ilvl w:val="1"/></w:numPr></w:pPr>'
              '<w:rPr><w:i/><w:sz w:val="28"/></w:rPr></w:style></w:styles>')
    numbering = (f'<w:numbering xmlns:w="{W_NS}"><w:abstractNum w:abstractNumId="0">'
                 '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/></w:lvl>'
                 '<w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1.%2"/>'
                 '<w:pPr><w:ind w:left="1440" w:hanging="720"/></w:pPr></w:lvl></w:abstractNum>'
                 '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>')
    body = (P("Top", ppr='<w:numPr><w:numId w:val="1"/><w:ilvl w:val="0"/></w:numPr>') +
            P("Sub", ppr='<w:pStyle w:val="Heading2"/>') + P("Sub2", ppr='<w:pStyle w:val="Heading2"/>'))
    d = _doc(body, **{"word/styles.xml": styles, "word/numbering.xml": numbering})
    top, sub, sub2 = d.blocks
    assert top.num.marker == "1." and sub.num.marker == "1.1" and sub2.num.marker == "1.2"
    assert sub.props.keep_next and sub.props.outline_level == 1 and sub.props.style_id == "Heading2"
    assert sub.props.ind_left_pt == 72.0 and sub.props.ind_hanging_pt == 36.0   # from the level
    assert sub.runs[0].props.italic and sub.runs[0].props.size_pt == 14.0 and sub.runs[0].props.font == "Georgia"
    assert top.runs[0].props.size_pt == 10.0 and d.default_font == "Georgia" and d.default_size_pt == 10.0


def test_table_with_span_and_vmerge():
    body = ('<w:tbl><w:tblGrid><w:gridCol w:w="2880"/><w:gridCol w:w="2880"/></w:tblGrid>'
            '<w:tr><w:tc><w:tcPr><w:gridSpan w:val="2"/></w:tcPr>' + P("head") + '</w:tc></w:tr>'
            '<w:tr><w:tc><w:tcPr><w:vMerge w:val="restart"/></w:tcPr>' + P("a1") + '</w:tc><w:tc>' + P("b1") + '</w:tc></w:tr>'
            '<w:tr><w:tc><w:tcPr><w:vMerge/></w:tcPr><w:p/></w:tc><w:tc>' + P("b2") + '</w:tc></w:tr></w:tbl>' + P("after"))
    d = _doc(body)
    t = d.blocks[0]
    assert isinstance(t, Table) and t.grid_pt == [144.0, 144.0]
    assert t.rows[0].cells[0].grid_span == 2 and t.rows[0].cells[0].blocks[0].text == "head"
    assert t.rows[1].cells[0].v_merge == "restart" and t.rows[2].cells[0].v_merge == "continue"
    assert [c.blocks[0].text for c in t.rows[2].cells] == ["", "b2"]
    assert d.blocks[1].text == "after"


def test_sections_geometry_and_titlepg_any_section():
    body = (P("cover", ppr='<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" '
              'w:bottom="1440" w:left="1440" w:header="720" w:footer="720"/><w:titlePg/></w:sectPr>') + P("body") +
            '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1000" w:right="1100" w:bottom="1200" '
            'w:left="1300" w:header="500" w:footer="600"/></w:sectPr>')
    d = _doc(body)
    assert len(d.sections) == 2
    last = d.sections[-1]
    assert (last.page_w_pt, last.page_h_pt) == (595.3, 841.9)
    assert (last.margin_top_pt, last.margin_right_pt, last.margin_bottom_pt, last.margin_left_pt) == (50.0, 55.0, 60.0, 65.0)
    assert (last.header_pt, last.footer_pt) == (25.0, 30.0)
    assert d.sections[0].title_pg is True and last.title_pg is False


def test_even_and_odd_from_settings():
    settings = f'<w:settings xmlns:w="{W_NS}"><w:evenAndOddHeaders/></w:settings>'
    assert _doc(P("x"), **{"word/settings.xml": settings}).even_and_odd is True
    assert _doc(P("x")).even_and_odd is False


def test_gridspan_without_val_defaults_to_one():
    body = '<w:tbl><w:tr><w:tc><w:tcPr><w:gridSpan/></w:tcPr>' + P("a") + '</w:tc></w:tr></w:tbl>'
    d = _doc(body)
    t = d.blocks[0]
    assert t.rows[0].cells[0].grid_span == 1


def test_deleted_page_break_does_not_travel():
    d = _doc(P("one") + '<w:p><w:del><w:r><w:br w:type="page"/></w:r></w:del></w:p>' + P("two"))
    paras = [b for b in d.blocks if isinstance(b, Paragraph)]
    flags = [(p.text, p.props.page_break_before) for p in paras if not p.is_empty]
    assert flags == [("one", False), ("two", False)]


def test_page_break_before_text_applies_to_own_paragraph():
    d = _doc(P("one") + '<w:p><w:r><w:br w:type="page"/><w:t>two</w:t></w:r></w:p>' + P("three"))
    paras = [b for b in d.blocks if isinstance(b, Paragraph)]
    flags = [(p.text, p.props.page_break_before) for p in paras if not p.is_empty]
    assert flags == [("one", False), ("two", True), ("three", False)]


def test_spacing_and_line_falls_back_to_doc_defaults_per_attribute():
    # Reference behavior (SorkWhare's extractStructured): spaceBefore/spaceAfter/line each
    # resolve independently -- paragraph, then style chain, then docDefaults' pPrDefault.
    # A paragraph that sets only spaceBefore still inherits the document's default
    # spaceAfter/line rather than leaving them unset.
    styles = (f'<w:styles xmlns:w="{W_NS}"><w:docDefaults><w:pPrDefault><w:pPr>'
              '<w:spacing w:after="200" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
              '</w:styles>')
    d = _doc(P("x", ppr='<w:spacing w:before="100"/>'), **{"word/styles.xml": styles})
    pr = d.blocks[0].props
    assert pr.space_before_pt == 5.0
    assert pr.space_after_pt == 10.0        # from docDefaults, not left None
    assert pr.line_spacing == 276 / 240     # from docDefaults, not left None


def test_exact_line_rule_does_not_set_line_spacing():
    # SorkWhare only computes a lineSpacing MULTIPLIER for rule "auto"; "exact"/"atLeast"
    # is a fixed line height (a different unit/concept) and lineSpacing stays null there.
    d = _doc(P("x", ppr='<w:spacing w:line="480" w:lineRule="exact"/>'))
    pr = d.blocks[0].props
    assert pr.line_spacing is None
    assert pr.line_rule == "exact" and pr.line_exact_pt == 24.0


def test_own_exact_line_rule_replaces_style_chain_auto_line_spacing():
    # A style's own auto line_spacing must not survive alongside a paragraph's own
    # override to an exact line rule -- line_spacing and line_exact_pt are mutually
    # exclusive concepts and must never both be set at once.
    styles = (f'<w:styles xmlns:w="{W_NS}"><w:style w:type="paragraph" w:styleId="Body">'
              '<w:pPr><w:spacing w:line="276" w:lineRule="auto"/></w:pPr></w:style></w:styles>')
    d = _doc(P("x", ppr='<w:pStyle w:val="Body"/><w:spacing w:line="480" w:lineRule="exact"/>'),
             **{"word/styles.xml": styles})
    pr = d.blocks[0].props
    assert pr.line_spacing is None and pr.line_rule == "exact" and pr.line_exact_pt == 24.0


def test_own_exact_line_rule_is_not_overridden_by_doc_defaults_auto_line():
    # The docDefaults fallback for "line" must apply as a whole GROUP, not per computed
    # field: a paragraph that sets its own w:line (here an exact rule) must not also pick
    # up docDefaults' unrelated auto lineSpacing multiplier into line_spacing.
    styles = (f'<w:styles xmlns:w="{W_NS}"><w:docDefaults><w:pPrDefault><w:pPr>'
              '<w:spacing w:line="240" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults></w:styles>')
    d = _doc(P("x", ppr='<w:spacing w:line="480" w:lineRule="exact"/>'), **{"word/styles.xml": styles})
    pr = d.blocks[0].props
    assert pr.line_spacing is None and pr.line_rule == "exact" and pr.line_exact_pt == 24.0


def test_heading_from_title_style_id():
    # SorkWhare hardcodes styleId "Title" (Word's built-in Title style) as heading 1,
    # regardless of the style's declared name.
    styles = (f'<w:styles xmlns:w="{W_NS}"><w:style w:type="paragraph" w:styleId="Title">'
              '<w:name w:val="Title"/></w:style></w:styles>')
    d = _doc(P("Contract Name", ppr='<w:pStyle w:val="Title"/>'), **{"word/styles.xml": styles})
    assert d.blocks[0].props.outline_level == 0   # heading == outline_level + 1 == 1


def test_heading_from_style_id_when_style_undefined():
    # SorkWhare falls back to matching "HeadingN" against the styleId itself even when the
    # style isn't found in styles.xml at all (no styles part supplied here).
    d = _doc(P("Section", ppr='<w:pStyle w:val="Heading3"/>'))
    assert d.blocks[0].props.outline_level == 2


def test_outline_lvl_alone_is_not_a_heading():
    # A raw <w:outlineLvl> with no Heading/Title style attached is NOT a heading in the
    # reference -- it derives `heading` purely from styleId/style-name, never from
    # outlineLvl. (outlineLvl is still read into ParaProps for other consumers.)
    d = _doc(P("plain", ppr='<w:outlineLvl w:val="1"/>'))
    assert d.blocks[0].props.outline_level is None
