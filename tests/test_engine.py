import io
import json
import re

import pytest

from calandria.diff.compare import compare
from calandria.diff.units import units
from calandria.docx.parser import parse_docx
from calandria.layout.engine import layout, layout_document
from calandria.layout.pieces import LayoutOptions
from calandria.layout.sides import SIDES, side_items, side_options
from calandria.testing.makedocx import DOC, P, PR, R, STYLES, TBL, make_docx
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


def test_a_page_tall_space_before_does_not_leave_a_blank_leading_page():
    # 620 pt of space before leaves too little room for the paragraph, so the planner retries it
    # on a fresh page and drops the space there: one page, starting at the top margin.
    body = P(" ".join(["aaaa"] * 40), ppr='<w:spacing w:before="12400"/>')
    L = _lay(body, body)
    assert L.page_count == 1 and L.pages[0].lines[0].top == 72


def test_table_rows_carry_their_change_numbers():
    L = _lay(P("i") + TBL([["old value"]]), P("i") + TBL([["new value"]]))
    d = json.loads(json.dumps(L.to_dict()))
    assert L.pages[0].table_rows[0].cids == [1, 2]        # "old" -> del 1, "new" -> ins 2 (per passage)
    assert d["pages"][0]["table_rows"][0]["cids"] == [1, 2]


def test_hidden_deletions_leave_no_deleted_runs():
    L = _lay(P("keep") + P("gone") + P("tail"), P("keep") + P("tail"), show_deletions=False)
    assert L.page_count == 1
    assert [ln.runs[0].text for ln in L.pages[0].lines] == ["keep", "tail"]
    assert not any(r.mode == "del" for ln in L.pages[0].lines for r in ln.runs)


def test_a_page_tall_table_row_degrades_to_stacked_paragraphs_across_pages():
    body = P("i") + TBL([[" ".join(["aaaa"] * 1200)]]) + P("o")     # ~67 lines: taller than a page
    L = _lay(body, body)
    assert L.page_count == 2
    assert all(pg.table_rows == [] for pg in L.pages)
    assert L.pages[0].lines and L.pages[1].lines


def test_empty_layout_falls_back_to_the_body_section():
    # Nothing is placed (every paragraph is empty and hidden), so the fallback page must take the
    # body (last) section's geometry, not the cover section's.
    body = P("", ppr='<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr>') + P("") + LETTER
    L = _lay(body, body, show_equal=False)
    assert L.page_count == 1 and L.pages[0].lines == [] and round(L.pages[0].w) == 612


# v2.4.0: side layouts (spec §12.1).


def _row_texts(L):
    """The text of every comparison row on the layout, in row order, whitespace collapsed."""
    by_row = {}
    for pg in L.pages:
        for ln in pg.lines:
            if ln.row_index is None:
                continue
            by_row.setdefault(ln.row_index, []).append("".join(r.text for r in ln.runs))
    return [re.sub(r"\s+", " ", " ".join(v)).strip() for _, v in sorted(by_row.items())]


def _unit_texts(doc):
    return [re.sub(r"\s+", " ", u.text).strip() for u in units(doc)]


A_SIDE = P("aaaa bbbb cccc") + P("gone gone gone") + P("dddd eeee")
B_SIDE = P("aaaa xxxx cccc") + P("dddd eeee") + P("new new new")


def test_side_layouts_carry_each_documents_own_text():
    a, b = _parse(A_SIDE), _parse(B_SIDE)
    cmp = compare(a, b)
    orig = layout(cmp, LayoutOptions(fonts=FR, side="original"))
    mod = layout(cmp, LayoutOptions(fonts=FR, side="modified"))
    assert _row_texts(orig) == _unit_texts(a)
    assert _row_texts(mod) == _unit_texts(b)


def test_side_layouts_carry_no_runs_of_the_other_side_and_no_formatting_marks():
    cmp = compare(_parse(A_SIDE), _parse(B_SIDE))
    orig = layout(cmp, LayoutOptions(fonts=FR, side="original"))
    mod = layout(cmp, LayoutOptions(fonts=FR, side="modified"))
    orig_modes = {r.mode for pg in orig.pages for ln in pg.lines for r in ln.runs}
    mod_modes = {r.mode for pg in mod.pages for ln in pg.lines for r in ln.runs}
    assert "ins" not in orig_modes and "del" in orig_modes        # the deleted text is there, plain
    assert "del" not in mod_modes and "ins" in mod_modes
    assert not any(r.fmt for pg in orig.pages for ln in pg.lines for r in ln.runs)
    assert orig.options.side == "original" and orig.to_dict()["options"]["side"] == "original"


def test_the_blackline_side_is_the_default_and_unchanged():
    cmp = compare(_parse(A_SIDE), _parse(B_SIDE))
    plain = layout(cmp, LayoutOptions(fonts=FR))
    named = layout(cmp, LayoutOptions(fonts=FR, side="blackline"))
    assert plain.options.side == "blackline"
    assert plain.to_dict()["pages"] == named.to_dict()["pages"]
    assert SIDES == ("blackline", "original", "modified")


def test_the_original_side_uses_the_original_paragraphs_properties():
    a = P("x") + P("y", ppr='<w:spacing w:before="200"/>')
    b = P("x") + P("y")
    cmp = compare(_parse(a), _parse(b))
    assert [ln.top for ln in layout(cmp, LayoutOptions(fonts=FR)).pages[0].lines] == [72, 84]
    assert [ln.top for ln in layout(cmp, LayoutOptions(fonts=FR, side="original")).pages[0].lines] == [72, 94]


def test_side_options_and_side_items():
    o = LayoutOptions(fonts=FR, show_formatting=True)
    assert side_options(o) is o
    so = side_options(LayoutOptions(fonts=FR, side="original"))
    assert (so.show_insertions, so.show_deletions, so.show_formatting) == (False, True, False)
    sm = side_options(LayoutOptions(fonts=FR, side="modified"))
    assert (sm.show_insertions, sm.show_deletions, sm.show_formatting) == (True, False, False)
    from calandria.layout.merged import merged_items
    cmp = compare(_parse(P("keep") + P("old")), _parse(P("keep") + "<w:p/>" + P("brand new")))
    items = merged_items(cmp)
    orig = side_items(items, cmp, "original")
    mod = side_items(items, cmp, "modified")
    assert [it.row.oi for it in orig] == [0, 1] and orig[1].para is cmp.a_units[1].para   # the original's own paragraph
    assert [it.row is None for it in mod] == [False, True, False]        # keep, the empty paragraph, brand new
    assert mod[0].row.ni == 0 and mod[-1].row.ni == 1 and all(it.row is None or it.row.ni is not None for it in mod)
    assert side_items(items, cmp, "blackline") is items
    with pytest.raises(ValueError, match="side"):
        layout(cmp, LayoutOptions(fonts=FR, side="sideways"))
    with pytest.raises(ValueError, match="sideways"):
        side_items(items, cmp, "sideways")


def test_side_layouts_lay_out_tables_with_the_side_s_own_text():
    a = P("Intro") + TBL([["one", "two"], ["three", "old cell"]])
    b = P("Intro") + TBL([["one", "two"], ["three", "new cell"]])
    cmp = compare(_parse(a), _parse(b))
    orig = layout(cmp, LayoutOptions(fonts=FR, side="original"))
    mod = layout(cmp, LayoutOptions(fonts=FR, side="modified"))
    assert _row_texts(orig) == _unit_texts(_parse(a))
    assert _row_texts(mod) == _unit_texts(_parse(b))
    assert orig.pages[0].table_rows and mod.pages[0].table_rows          # the table survives as a table on both sides
    assert len(orig.pages[0].table_rows) == len(mod.pages[0].table_rows) == 2


def test_the_original_side_keeps_the_original_documents_character_formatting():
    # the shared text "bbbb" is bold in the original paragraph, plain in the revised one; the
    # blackline and the modified side draw the revised formatting, but Original must draw its own
    a = PR(R("aaaa ") + R("bbbb", "<w:b/>"))
    b = P("aaaa bbbb")
    cmp = compare(_parse(a), _parse(b))
    black = layout(cmp, LayoutOptions(fonts=FR))
    orig = layout(cmp, LayoutOptions(fonts=FR, side="original"))
    mod = layout(cmp, LayoutOptions(fonts=FR, side="modified"))

    def bold_of(L, text):
        return [r.bold for pg in L.pages for ln in pg.lines for r in ln.runs if text in r.text]

    assert not any(bold_of(black, "bbbb"))
    assert bold_of(orig, "bbbb") and all(bold_of(orig, "bbbb"))
    assert not any(bold_of(mod, "bbbb"))


def test_a_passage_starting_on_a_later_line_puts_its_number_on_that_line():
    words = " ".join(["aaaa"] * 30)                        # wraps well past one line at 5 pt a character
    L = _lay(P(words + " bbbb cccc"), P(words + " bbbb dddd cccc"))
    lines = L.pages[0].lines
    at = next(i for i, ln in enumerate(lines) if any(g.mode == "ins" for g in ln.runs))
    assert at > 0
    assert [ln.cid_starts for ln in lines] == [[1] if i == at else [] for i in range(len(lines))]
    # the inserted "dddd " is one passage but measure() still splits it into a word run and a
    # trailing space run (both carry the same cid); filter to the non-whitespace run
    assert [g.cid for ln in lines for g in ln.runs if g.mode == "ins" and g.text.strip()] == [1]


def test_two_replacements_on_one_line_number_deletion_then_insertion():
    # "value" and "now" are shared, so this pairs as one changed row (PAIR_THRESHOLD 0.5) instead
    # of a whole-paragraph delete+insert
    L = _lay(P("old value here now"), P("new value there now"))
    (ln,) = L.pages[0].lines
    assert ln.cid_starts == [1, 2, 3, 4]
    assert [(g.text, g.mode, g.cid) for g in ln.runs if g.cid is not None] == \
        [("old", "del", 1), ("new", "ins", 2), ("here", "del", 3), ("there", "ins", 4)]
    assert all(g.cid is None for g in ln.runs if g.mode == "eq")     # the equal text is several runs


def test_leader_dots_are_placed_to_end_at_the_stop():
    sty = STYLES('<w:rFonts w:ascii="Fake"/><w:sz w:val="20"/>',
                 '<w:style w:type="paragraph" w:styleId="TOC1"><w:pPr><w:tabs>'
                 '<w:tab w:val="right" w:leader="dot" w:pos="2000"/></w:tabs></w:pPr></w:style>')
    body = ('<w:p><w:pPr><w:pStyle w:val="TOC1"/></w:pPr><w:r><w:t>Intro</w:t><w:tab/><w:t>3</w:t></w:r></w:p>')
    d = parse_docx(io.BytesIO(make_docx({"word/document.xml": DOC(body), "word/styles.xml": sty})))
    L = layout(compare(d, d), LayoutOptions(fonts=FR))
    (ln,) = L.pages[0].lines
    # "Intro" 25 pt from 72; the tab spans 97 -> 167 (the stop at 172 minus the 5 pt "3"); 14 dots of 5 pt
    assert [(r.text, r.x, r.w) for r in ln.runs] == [("Intro", 72, 25), ("\t", 97, 70), ("." * 14, 97, 70), ("3", 167, 5)]


BOX = ('<w:pBdr><w:top w:val="single" w:sz="8" w:space="4"/><w:bottom w:val="single" w:sz="8" w:space="4"/>'
       '<w:left w:val="single" w:sz="8" w:space="4" w:color="FF0000"/></w:pBdr>')


def test_paragraph_borders_are_rules_on_the_placed_lines():
    from calandria.layout.pages import Rule
    body = P(" ".join(["aaaa"] * 100), ppr=BOX) + P("after")      # 18 words per 468 pt line: 6 lines
    L = _lay(body, body)
    lines = L.pages[0].lines
    assert len(lines) == 7 and lines[0].top == 72 and lines[0].height == 17 and lines[0].baseline == 85
    assert lines[5].height == 17 and lines[1].height == 12
    # the top rule's centre sits half its width below the paragraph's top edge, spanning the indents
    assert lines[0].rules[0] == Rule(72, 72.5, 540, 72.5, 1.0, "000000")
    # every line of the paragraph carries the left rule over its own height, outside the space
    for ln in lines[:6]:
        assert Rule(67.5, ln.top, 67.5, ln.top + ln.height, 1.0, "ff0000") in ln.rules
    assert lines[5].rules[-1] == Rule(72, lines[5].top + 17 - 0.5, 540, lines[5].top + 17 - 0.5, 1.0, "000000")
    assert lines[6].rules == [] and lines[6].top == lines[5].top + 17
    d = L.to_dict()["pages"][0]["lines"]
    assert d[0]["rules"][0] == {"x1": 72, "y1": 72.5, "x2": 540, "y2": 72.5, "w": 1.0, "clr": "000000"}
    assert "rules" not in d[6]                                   # emitted only when there is one


def test_joined_paragraphs_draw_no_rule_between_them():
    body = P("one", ppr=BOX) + P("two", ppr=BOX)
    L = _lay(body, body)
    a, b = L.pages[0].lines
    assert [r.y1 for r in a.rules if r.y1 == r.y2] == [72.5]                      # top only
    assert [r.y1 for r in b.rules if r.y1 == r.y2] == [b.top + 17 - 0.5]          # bottom only
    assert (a.height, b.height, b.top) == (17, 17, 89)


def test_right_border_inside_a_table_cell_uses_the_cell_edge():
    from calandria.layout.pages import Rule
    ppr = '<w:pBdr><w:right w:val="single" w:sz="4" w:space="0"/></w:pBdr>'
    body = ('<w:tbl><w:tblGrid><w:gridCol w:w="4000"/></w:tblGrid><w:tr><w:tc>'
            + P("cell", ppr=ppr) + '</w:tc></w:tr></w:tbl>')
    L = _lay(body, body)
    (ln,) = L.pages[0].lines
    (cell,) = L.pages[0].table_rows[0].cells
    (r,) = ln.rules
    assert r.x1 == r.x2 and r.x1 < cell.x + cell.w and r.x1 > ln.x and (r.y1, r.y2) == (ln.top, ln.top + ln.height)


def _lay_notes(body, notes=None, endnotes=None, **opts):
    from calandria.testing.makedocx import ENDNOTES, FOOTNOTES
    parts = {"word/document.xml": DOC(body), "word/styles.xml": STY}
    if notes:
        parts["word/footnotes.xml"] = FOOTNOTES(notes)
    if endnotes:
        parts["word/endnotes.xml"] = ENDNOTES(endnotes)
    d = parse_docx(io.BytesIO(make_docx(parts)))
    return layout(compare(d, d), LayoutOptions(fonts=FR, **opts))


def test_a_footnote_sits_at_the_foot_of_the_page_under_a_separator():
    from calandria.layout.pages import Rule
    from calandria.testing.makedocx import FNREF, PR, R
    L = _lay_notes(PR(R("aaaa") + FNREF(1)) + P("bbbb"), {1: "Note one."})
    lines = L.pages[0].lines
    assert [(ln.stream, ln.top, ln.height) for ln in lines] == [("body", 72, 12), ("body", 84, 12),
                                                                ("footnote", 699, 9), ("footnote", 708, 12)]
    sep, note = lines[2], lines[3]
    assert sep.runs == [] and sep.rules == [Rule(72, 703.5, 216, 703.5, 0.75, "000000")]
    assert [(r.text, r.rise) for r in note.runs][:3] == [("1", 3.5), (" ", 0.0), ("Note", 0.0)]
    assert [(r.text, r.rise, r.size) for r in lines[0].runs] == [("aaaa", 0.0, 10), ("1", 3.5, 6.5)]
    d = L.to_dict()["pages"][0]["lines"]
    assert "stream" not in d[0] and d[2]["stream"] == "footnote" and d[3]["runs"][0]["rise"] == 3.5


def test_a_line_moves_to_the_next_page_together_with_its_footnote():
    from calandria.testing.makedocx import FNREF, PR, R
    body = "".join(P(f"p{i}") for i in range(53)) + PR(R("last") + FNREF(1))     # 636 pt used of 648
    L = _lay_notes(body, {1: "Note."})
    assert L.page_count == 2 and len(L.pages[0].lines) == 53
    assert [(ln.stream, ln.top) for ln in L.pages[1].lines] == [("body", 72), ("footnote", 699), ("footnote", 708)]


def test_endnotes_follow_the_body_under_a_separator():
    from calandria.testing.makedocx import ENREF, PR, R
    L = _lay_notes(PR(R("aaaa") + ENREF(1)) + P("bbbb"), endnotes={1: "The end."})
    lines = L.pages[0].lines
    assert [(ln.stream, ln.top, ln.height) for ln in lines] == [("body", 72, 12), ("body", 84, 12),
                                                                ("endnote", 96, 9), ("endnote", 105, 12)]
    assert lines[2].rules and lines[3].runs[0].text == "1"


def test_a_footnote_inside_a_table_cell_floats_and_keeps_the_table_whole():
    from calandria.testing.makedocx import FNREF, PR, R
    body = ('<w:tbl><w:tblGrid><w:gridCol w:w="4000"/><w:gridCol w:w="4000"/></w:tblGrid><w:tr><w:tc>'
            + PR(R("cell") + FNREF(1)) + '</w:tc><w:tc>' + P("two") + '</w:tc></w:tr></w:tbl>')
    L = _lay_notes(body, {1: "Cell note."})
    pg = L.pages[0]
    assert len(pg.table_rows) == 1 and len(pg.table_rows[0].cells) == 2
    assert [ln.stream for ln in pg.lines] == ["body", "body", "footnote", "footnote"]
    assert pg.lines[-1].top == 708


def test_a_deleted_note_floats_on_the_original_side_only():
    from calandria.testing.makedocx import FNREF, FOOTNOTES, PR, R
    a = parse_docx(io.BytesIO(make_docx({"word/document.xml": DOC(PR(R("aaaa") + FNREF(1))), "word/styles.xml": STY,
                                         "word/footnotes.xml": FOOTNOTES({1: "Gone."})})))
    b = _parse(P("aaaa"))
    c = compare(a, b)
    black = layout(c, LayoutOptions(fonts=FR))
    assert [ln.stream for ln in black.pages[0].lines] == ["body", "footnote", "footnote"]
    assert [g.mode for g in black.pages[0].lines[0].runs] == ["eq", "del"]           # the dropped mark
    orig = layout(c, LayoutOptions(fonts=FR, side="original"))
    assert [ln.stream for ln in orig.pages[0].lines] == ["body", "footnote", "footnote"]
    mod = layout(c, LayoutOptions(fonts=FR, side="modified"))
    assert [ln.stream for ln in mod.pages[0].lines] == ["body"]


def test_the_larger_of_space_after_and_space_before_separates_paragraphs():
    from calandria.testing.makedocx import W_NS
    body = (P("a", ppr='<w:spacing w:after="240"/>') + P("b", ppr='<w:spacing w:before="720"/>')
            + P("c", ppr='<w:spacing w:before="100"/>') + "<w:p/>" + P("d", ppr='<w:spacing w:before="600"/>'))
    L = _lay(body, body)
    # a(12 after) b(36 before): 36 not 48; b(0 after) c(5 before): 5; c(0 after) empty(0): 0; empty(0) d(30): 30
    assert [ln.top for ln in L.pages[0].lines] == [72, 120, 137, 149, 191]
    off = '<w:settings xmlns:w="{}"><w:compat><w:doNotUseHTMLParagraphAutoSpacing/></w:compat></w:settings>'.format(W_NS)
    d = parse_docx(io.BytesIO(make_docx({"word/document.xml": DOC(body), "word/styles.xml": STY, "word/settings.xml": off})))
    L2 = layout(compare(d, d), LayoutOptions(fonts=FR))
    assert [ln.top for ln in L2.pages[0].lines] == [72, 132, 149, 161, 203]     # the sum, as before


def test_spacing_collapses_inside_table_cells_too():
    body = ('<w:tbl><w:tblGrid><w:gridCol w:w="9000"/></w:tblGrid><w:tr><w:tc>'
            + P("a", ppr='<w:spacing w:after="240"/>') + P("b", ppr='<w:spacing w:before="240"/>')
            + '</w:tc></w:tr></w:tbl>')
    L = _lay(body, body)
    a, b = L.pages[0].lines
    assert b.top - (a.top + a.height) == 12


def test_empty_paragraphs_at_the_top_of_a_section_do_not_push_its_first_text_a_page_further():
    sect = '<w:sectPr><w:type w:val="nextPage"/><w:pgSz w:w="12240" w:h="15840"/></w:sectPr>'
    body = P("toc end") + f'<w:p><w:pPr>{sect}</w:pPr></w:p>' + "<w:p/>" + P("Schedule") + LETTER
    L = _lay(body, body)
    assert L.page_count == 2
    assert [(ln.top, "".join(g.text for g in ln.runs)) for ln in L.pages[1].lines] == [(72, ""), (84, "Schedule")]
    real = P("toc end") + '<w:p><w:r><w:br w:type="page"/></w:r></w:p>' + "<w:p/>" + P("Schedule")
    L2 = _lay(real, real)
    assert L2.page_count == 2 and "".join(g.text for g in L2.pages[1].lines[-1].runs) == "Schedule"
