import io

from calandria.diff.compare import compare
from calandria.docx.parser import parse_docx
from calandria.layout.blocks import Ctx, next_tab_stop, para_block
from calandria.layout.merged import merged_items
from calandria.layout.pieces import LayoutOptions
from calandria.testing.makedocx import DOC, NUMBERING, P, STYLES, W_NS, make_docx
from calandria.testing.fakefonts import FakeResolver

FR = FakeResolver()                       # 5 pt per character at size 10, line height 12
STY = STYLES('<w:rFonts w:ascii="Fake"/><w:sz w:val="20"/>')
NUM = NUMBERING([("decimal", "%1.", 720, 360, None)])             # left 36 pt, hanging 18 pt
NUMPR = '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>'


def _parse(body, numbering=None, styles=STY, settings=None):
    parts = {"word/document.xml": DOC(body), "word/styles.xml": styles}
    if numbering:
        parts["word/numbering.xml"] = numbering
    if settings:
        parts["word/settings.xml"] = settings
    return parse_docx(io.BytesIO(make_docx(parts)))


def _items(body_a, body_b, numbering=None, styles=STY, settings=None):
    c = compare(_parse(body_a, numbering, styles, settings), _parse(body_b, numbering, styles, settings))
    return c, merged_items(c)


def _ctx(c, content_w=200.0, avail_h=600.0):
    d = c.b_doc
    return Ctx(c, LayoutOptions(fonts=FR), FR, content_w, avail_h, d.default_font, d.default_size_pt, d.default_tab_pt)


def _block(items, i, ctx, **kw):
    return para_block(items[i], items[i - 1] if i else None, items[i + 1] if i + 1 < len(items) else None, ctx, **kw)


def _texts(block):
    return ["".join(r.text for r in ln.runs) for ln in block.lines]


def test_plain_paragraph():
    c, items = _items(P("aaaa bbbb"), P("aaaa bbbb"))
    b = _block(items, 0, _ctx(c))
    assert _texts(b) == ["aaaa bbbb"] and (b.x, b.first_dx, b.marker, b.marker_x) == (0, 0, [], 0)
    assert b.height == 12 and not b.changed and b.cids == [] and b.cid_starts == [[]] and b.row_index == 0 and b.section == 0
    assert (b.space_before, b.space_after, b.align) == (0, 0, "left")


def test_first_line_indent_narrows_the_first_line():
    c, items = _items(P("x"), P("aaaa bbbb cccc dddd", ppr='<w:ind w:firstLine="400"/>'))
    b = _block(items, 1, _ctx(c, content_w=60))
    assert b.first_dx == 20 and _texts(b) == ["aaaa", "bbbb cccc", "dddd"]


def test_hanging_indent_without_a_marker_pulls_the_first_line_left():
    c, items = _items(P("x"), P("aaaa", ppr='<w:ind w:left="720" w:hanging="360"/>'))
    b = _block(items, 1, _ctx(c))
    assert (b.x, b.first_dx) == (36, -18)


def test_list_marker_sits_at_the_hanging_position_and_text_starts_at_the_indent():
    c, items = _items(P("Item", ppr=NUMPR), P("Item", ppr=NUMPR), NUM)
    b = _block(items, 0, _ctx(c))
    assert [r.text for r in b.marker] == ["1."] and b.marker[0].piece.mode == "eq"
    assert (b.x, b.marker_x, b.first_dx) == (36, 18, 0)


def test_wide_marker_pushes_the_text_to_the_next_default_tab_stop():
    num = NUMBERING([("decimal", "Section %1 of", 720, 360, None)])     # "Section 1 of" = 60 pt
    c, items = _items(P("Item", ppr=NUMPR), P("Item", ppr=NUMPR), num)
    b = _block(items, 0, _ctx(c))
    assert b.marker_x == 18 and b.first_dx == 72          # marker ends at 78 -> next stop 108 -> 108 - 36


def test_zero_default_tab_stop_places_the_text_at_the_marker_end():
    num = NUMBERING([("decimal", "Section %1 of", 720, 360, None)])     # "Section 1 of" = 60 pt
    settings = f'<w:settings xmlns:w="{W_NS}"><w:defaultTabStop w:val="0"/></w:settings>'
    c, items = _items(P("Item", ppr=NUMPR), P("Item", ppr=NUMPR), num, settings=settings)
    b = _block(items, 0, _ctx(c))
    assert b.marker_x == 18 and b.first_dx == 42          # marker ends at 78, no tab stops -> 78 - 36


def test_marker_suffix_space_and_nothing():
    c, items = _items(P("Item", ppr=NUMPR), P("Item", ppr=NUMPR), NUMBERING([("decimal", "%1.", 720, 360, "space")]))
    assert _block(items, 0, _ctx(c)).first_dx == -3        # marker ends at 28, plus one 5 pt space, minus x 36
    c, items = _items(P("Item", ppr=NUMPR), P("Item", ppr=NUMPR), NUMBERING([("decimal", "%1.", 720, 360, "nothing")]))
    assert _block(items, 0, _ctx(c)).first_dx == -8


def test_renumbered_item_shows_old_and_new_markers():
    c, items = _items(P("Zero", ppr=NUMPR) + P("Alpha", ppr=NUMPR), P("Alpha", ppr=NUMPR) + P("Beta", ppr=NUMPR), NUM)
    alpha = next(it for it in items if it.para.text == "Alpha")
    b = para_block(alpha, None, None, _ctx(c))
    assert [(r.text, r.piece.mode) for r in b.marker] == [("2.", "del"), (" ", "eq"), ("1.", "ins")]
    assert b.first_dx == 36 and b.changed and b.cids == [2] and b.cid_starts == [[2]]        # 25 pt marker ends at 43 -> stop 72
    assert [r.piece.cid for r in b.marker] == [2, 2, 2]


def test_numbered_to_plain_leads_with_the_struck_old_marker():
    c, items = _items(P("Alpha", ppr=NUMPR), P("Alpha"), NUM)
    b = _block(items, 0, _ctx(c))
    assert b.marker == [] and [(r.text, r.piece.mode) for r in b.lines[0].runs][:3] == [
        ("1.", "del"), (" ", "del"), ("Alpha", "eq")]
    assert b.changed


def test_right_indent_narrows_the_wrap_width():
    text = "aaaa bbbb cccc dddd eeee ffff gggg"                  # 170 pt: one line in 200 pt
    c, items = _items(P("x"), P(text))
    assert _texts(_block(items, 1, _ctx(c))) == [text]
    c, items = _items(P("x"), P(text, ppr='<w:ind w:right="800"/>'))
    b = _block(items, 1, _ctx(c))
    assert b.right == 40 and _texts(b) == ["aaaa bbbb cccc dddd eeee ffff", "gggg"]


def test_contextual_spacing_zeroes_the_gap_between_same_style_neighbours():
    sty = STYLES('<w:rFonts w:ascii="Fake"/><w:sz w:val="20"/>',
                 '<w:style w:type="paragraph" w:styleId="Body"><w:pPr><w:spacing w:before="200" w:after="200"/>'
                 '<w:contextualSpacing/></w:pPr></w:style>')
    body = P("a", ppr='<w:pStyle w:val="Body"/>') + P("b", ppr='<w:pStyle w:val="Body"/>') + P("c")
    c, items = _items(body, body, styles=sty)
    ctx = _ctx(c)
    a, b = _block(items, 0, ctx), _block(items, 1, ctx)
    assert (a.space_before, a.space_after) == (10, 0)
    assert (b.space_before, b.space_after) == (0, 10)


def test_empty_paragraph_is_one_default_line():
    c, items = _items(P("x"), P("x") + P(""))
    b = _block(items, 1, _ctx(c))
    assert b.lines[0].runs == [] and b.height == 12 and not b.changed and b.row_index is None


def test_exact_line_rule_and_keep_flags():
    c, items = _items(P("x"), P("aaaa", ppr='<w:spacing w:line="600" w:lineRule="exact"/><w:keepNext/><w:keepLines/>'
                                        '<w:pageBreakBefore/>'))
    b = _block(items, 1, _ctx(c))
    assert b.lines[0].height == 30 and b.keep_next and b.keep_lines and b.page_break_before


def test_changed_rows_are_flagged_with_their_change_number():
    c, items = _items(P("same"), P("same") + P("added"))
    b = _block(items, 1, _ctx(c))
    assert b.changed and b.cids == [1] and b.cid_starts == [[1]] and b.lines[0].runs[0].piece.mode == "ins"


def test_container_width_override_wraps_narrower():
    c, items = _items(P("x"), P("aaaa bbbb cccc"))
    assert _texts(_block(items, 1, _ctx(c), avail_w=45)) == ["aaaa bbbb", "cccc"]


def test_justify_alignment_is_normalised():
    c, items = _items(P("x"), P("aaaa", ppr='<w:jc w:val="both"/>'))
    assert _block(items, 1, _ctx(c)).align == "justify"


def test_next_tab_stop():
    assert next_tab_stop(0, 36) == 36 and next_tab_stop(35.9, 36) == 36
    assert next_tab_stop(36, 36) == 72 and next_tab_stop(78, 36) == 108


def test_marker_text_starts_at_a_custom_stop_before_the_hanging_indent():
    styles = STYLES('<w:rFonts w:ascii="Fake"/><w:sz w:val="20"/>',
                    '<w:style w:type="paragraph" w:styleId="Tight"><w:pPr><w:tabs>'
                    '<w:tab w:val="left" w:pos="600"/></w:tabs></w:pPr></w:style>')
    body = P("item", NUMPR) + P("item", '<w:pStyle w:val="Tight"/>' + NUMPR)
    c, items = _items(body, body, NUM, styles)
    ctx = _ctx(c)
    plain, tight = _block(items, 0, ctx), _block(items, 1, ctx)
    assert (plain.x, plain.first_dx) == (36, 0)         # marker "1." ends at 28 < 36: the hanging indent
    assert (tight.x, tight.first_dx) == (36, -6)        # the custom stop at 30 pt comes first


def test_a_toc_line_lays_out_its_number_text_and_page_number():
    styles = STYLES('<w:rFonts w:ascii="Fake"/><w:sz w:val="20"/>',
                    '<w:style w:type="paragraph" w:styleId="TOC2"><w:pPr><w:tabs>'
                    '<w:tab w:val="left" w:pos="800"/><w:tab w:val="right" w:leader="dot" w:pos="3000"/>'
                    '</w:tabs><w:ind w:left="200"/></w:pPr></w:style>')
    body = ('<w:p><w:pPr><w:pStyle w:val="TOC2"/></w:pPr><w:r><w:t>1.1</w:t><w:tab/>'
            '<w:t>Definitions</w:t><w:tab/><w:t>12</w:t></w:r></w:p>')
    c, items = _items(body, body, styles=styles)
    blk = _block(items, 0, _ctx(c))
    (ln,) = blk.lines
    assert blk.x == 10 and [(r.text, r.w, r.leader) for r in ln.runs] == [
        ("1.1", 15, None), ("\t", 15, None), ("Definitions", 55, None), ("\t", 45, "."), ("12", 10, None)]
    assert blk.x + ln.width == 150                       # the page number ends at the right stop


BOX = ('<w:pBdr><w:top w:val="single" w:sz="8" w:space="4"/><w:bottom w:val="single" w:sz="8" w:space="4"/>'
       '<w:left w:val="single" w:sz="8" w:space="4"/></w:pBdr>')


def test_paragraph_borders_add_their_width_and_space_to_the_first_and_last_line():
    from calandria.model import Border
    body = P(" ".join(["aaaa"] * 20), ppr=BOX)                       # 8 words per 200 pt line: 3 lines
    c, items = _items(body, body)
    b = _block(items, 0, _ctx(c))
    assert len(b.lines) == 3
    assert b.borders == (Border(1.0, 4.0), Border(1.0, 4.0), Border(1.0, 4.0), None)
    assert (b.draw_top, b.draw_bottom) == (True, True)
    assert [ln.height for ln in b.lines] == [17, 12, 17]        # 1 pt line + 4 pt space on each end
    assert [ln.ascent for ln in b.lines] == [13, 8, 8]          # the top border pushes the first baseline down
    assert b.height == 46


def test_adjacent_paragraphs_with_the_same_borders_join_into_one_box():
    body = P("one", ppr=BOX) + P("two", ppr=BOX) + P("three", ppr=BOX + '<w:ind w:left="720"/>')
    c, items = _items(body, body)
    ctx = _ctx(c)
    one, two, three = (_block(items, i, ctx) for i in range(3))
    assert (one.draw_top, one.draw_bottom) == (True, False)     # its bottom is drawn by nobody: joined
    assert (two.draw_top, two.draw_bottom) == (False, True)     # "three" is indented: a new box starts there
    assert (three.draw_top, three.draw_bottom) == (True, True)
    assert [ln.height for ln in one.lines] == [17] and [ln.height for ln in two.lines] == [17]
    assert [ln.height for ln in three.lines] == [22]


def test_a_note_first_paragraph_opens_with_its_number():
    from calandria.testing.makedocx import FNREF, FOOTNOTES, PR, R
    fn = FOOTNOTES({1: "Note one.\nSecond para."})
    body = PR(R("Body") + FNREF(1))
    c, items = _items(body, body)
    # the fixture builder attaches footnotes.xml only via the parts map: rebuild with it
    a = _parse(body)
    from calandria.docx.parser import parse_docx
    import io
    from calandria.testing.makedocx import DOC, make_docx
    d = parse_docx(io.BytesIO(make_docx({"word/document.xml": DOC(body), "word/styles.xml": STY, "word/footnotes.xml": fn})))
    c = compare(d, d)
    items = merged_items(c)
    ctx = _ctx(c)
    assert [it.stream for it in items] == ["body", "footnote", "footnote"]
    first = _block(items, 1, ctx)
    second = _block(items, 2, ctx)
    assert _texts(first) == ["1 Note one."] and _texts(second) == ["Second para."]
    assert [(r.text, r.rise, r.size) for r in first.lines[0].runs][:2] == [("1", 3.5, 6.5), (" ", 0.0, 10)]


def test_an_empty_paragraph_is_as_tall_as_its_mark_says():
    sty = STYLES('<w:rFonts w:ascii="Fake"/><w:sz w:val="20"/>',
                 '<w:style w:type="paragraph" w:styleId="Small"><w:rPr><w:sz w:val="10"/></w:rPr></w:style>')
    body = P("text") + '<w:p><w:pPr><w:pStyle w:val="Small"/></w:pPr></w:p>' + '<w:p><w:pPr><w:rPr><w:sz w:val="40"/></w:rPr></w:pPr></w:p>' + "<w:p/>"
    c, items = _items(body, body, styles=sty)
    ctx = _ctx(c)
    heights = [_block(items, i, ctx).height for i in range(4)]
    assert heights == [12, 6, 24, 12]        # 10 pt text; a 5 pt mark; a 20 pt mark; the default 10 pt
