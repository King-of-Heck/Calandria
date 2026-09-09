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
    assert b.height == 12 and not b.changed and b.cid is None and b.row_index == 0 and b.section == 0
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
    assert b.first_dx == 36 and b.changed and b.cid == 2        # 25 pt marker ends at 43 -> stop 72


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
    assert b.changed and b.cid == 1 and b.lines[0].runs[0].piece.mode == "ins"


def test_container_width_override_wraps_narrower():
    c, items = _items(P("x"), P("aaaa bbbb cccc"))
    assert _texts(_block(items, 1, _ctx(c), avail_w=45)) == ["aaaa bbbb", "cccc"]


def test_justify_alignment_is_normalised():
    c, items = _items(P("x"), P("aaaa", ppr='<w:jc w:val="both"/>'))
    assert _block(items, 1, _ctx(c)).align == "justify"


def test_next_tab_stop():
    assert next_tab_stop(0, 36) == 36 and next_tab_stop(35.9, 36) == 36
    assert next_tab_stop(36, 36) == 72 and next_tab_stop(78, 36) == 108
