import io
from datetime import datetime

from calandria.diff.compare import compare
from calandria.docx.parser import parse_docx
from calandria.layout.engine import layout
from calandria.layout.pages import FontRef, Page, PlacedLine
from calandria.layout.pieces import LayoutOptions
from calandria.pdf.draw import (BAR_GAP, BAR_WIDTH, BLACK, GRID_WIDTH, NUMBER_GAP, NUMBER_SIZE,
                                DrawResult, PdfOptions, bar_intervals, changed_pages, cid_label, content_bottom,
                                draw_grid, draw_layout, draw_page, draw_runs, run_style)
from calandria.pdf.rendersets import BLACK_AND_WHITE, STANDARD
from calandria.pdf.report import GAP, TITLE, ReportInfo, report_height
from calandria.testing.fakefonts import FakeResolver
from calandria.testing.makedocx import DOC, P, PR, R, STYLES, TBL, make_docx
from calandria.testing.recpaint import RecordingPainter

FR = FakeResolver()                       # 5 pt per character at size 10, line height 12, ascent 8
STY = STYLES('<w:rFonts w:ascii="Fake"/><w:sz w:val="20"/>')
SERIF = STYLES('<w:rFonts w:ascii="Serif"/><w:sz w:val="20"/>')     # not the fake resolver's fallback
WHEN = datetime(2026, 9, 9, 14, 5)


def _parse(body, sty=STY):
    return parse_docx(io.BytesIO(make_docx({"word/document.xml": DOC(body), "word/styles.xml": sty})))


def _lay(a, b, sty=STY, **opts):
    return layout(compare(_parse(a, sty), _parse(b, sty)), LayoutOptions(fonts=FR, **opts))


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


def _one_run(L, page=0, line=0, idx=0):
    ln = L.pages[page].lines[line]
    g = ln.runs[idx]
    return g, L.fonts[g.face]


def test_run_style_of_an_equal_run_keeps_the_document_colour():
    body = PR(R("aaaa", '<w:u w:val="single"/><w:color w:val="00AA00"/>'))
    g, face = _one_run(_lay(body, body))
    assert run_style(g, face, STANDARD) == ("00aa00", frozenset({"underline"}), False, False)


def test_run_style_of_an_inserted_run_takes_the_category():
    L = _lay(P("aaaa"), P("aaaa bbbb"))
    g, face = _one_run(L, idx=2)
    assert g.text == "bbbb"
    assert run_style(g, face, STANDARD) == ("0000ff", frozenset({"double-underline"}), False, False)
    assert run_style(g, face, BLACK_AND_WHITE)[0] == BLACK


def test_run_style_fakes_a_synthetic_face():
    L = _lay(P("aaaa"), P("aaaa"))
    g, _ = _one_run(L)
    assert run_style(g, FontRef("<fake:Fake|>", 0, "Fake", True, True, True), STANDARD)[2:] == (True, True)
    assert run_style(g, FontRef("<fake:Fake|>", 0, "Fake", True, False, True), STANDARD)[2:] == (True, False)
    assert run_style(g, FontRef("<fake:Fake|BI>", 0, "Fake", True, True, False), STANDARD)[2:] == (False, False)


def test_cid_label():
    assert cid_label([1]) == "1" and cid_label([2, 3]) == "2-3" and cid_label([3, 2]) == "2-3"
    assert cid_label([1, 2, 3, 5, 7, 8]) == "1-3, 5, 7-8" and cid_label([4, 4]) == "4"


def _page(L, page=0, **kw):
    p = RecordingPainter()
    draw_page(L.pages[page], L.fonts, STANDARD, PdfOptions(**kw), p, FR.face(None))
    return p


def test_page_op_comes_first_with_the_page_size():
    p = _page(_lay(P("aaaa"), P("aaaa")))
    assert p.ops[0] == ("page", 612, 792)


def test_gutter_number_is_right_aligned_on_the_baseline():
    p = _page(_lay(P("aaaa"), P("aaaa") + P("bbbb")))
    # "bbbb" is change 1 on line 2 (top 84, baseline 92); "1" is 3.5 pt wide at 7 pt in the fake font
    assert ("text", 72 - NUMBER_GAP - 3.5, 92, "1", "<fake:Fake|>", NUMBER_SIZE, BLACK, False, False) in p.ops
    assert NUMBER_GAP == 10.0 and NUMBER_SIZE == 7.0


def test_change_bar_spans_contiguous_changed_lines_only():
    L = _lay(P("aaaa") + P("cccc"), P("aaaa") + P("bbbb") + P("dddd") + P("cccc") + P("eeee"))
    # lines: aaaa eq (72), bbbb ins (84), dddd ins (96), cccc eq (108), eeee ins (120)
    p = _page(L)
    bars = [o for o in p.of("line") if o[5] == BAR_WIDTH]
    x = 72 - BAR_GAP
    assert bars == [("line", x, 84, x, 108, BAR_WIDTH, BLACK), ("line", x, 120, x, 132, BAR_WIDTH, BLACK)]
    assert bar_intervals(L.pages[0]) == [(84, 108), (120, 132)]


def test_a_changed_row_and_the_changed_line_under_it_make_one_bar():
    a = TBL([["aaa"]], [9360]) + P("cccc")
    b = TBL([["aaa xxx"]], [9360]) + P("cccc yyy")
    L = _lay(a, b)
    (row,) = L.pages[0].table_rows
    below = L.pages[0].lines[1]
    assert row.changed and below.changed and below.top == row.y + row.h
    assert bar_intervals(L.pages[0]) == [(row.y, below.top + below.height)]


def _line(top, height=12.0, changed=True):
    return PlacedLine(72, top, height, top + 8, [], [], changed, [], None)


def test_change_bar_spans_merge_within_the_tolerance_gap():
    page = Page(0, 612, 792, 72, 72, 72, 72, 0,
                lines=[_line(72, 12), _line(84.3, 11.7)])
    assert bar_intervals(page) == [(72, 96)]


def test_change_bar_spans_do_not_merge_past_the_tolerance_gap():
    page = Page(0, 612, 792, 72, 72, 72, 72, 0,
                lines=[_line(72, 12), _line(85, 12)])
    assert bar_intervals(page) == [(72, 84), (85, 97)]


def test_change_bars_can_be_switched_off():
    p = _page(_lay(P("aaaa"), P("aaaa") + P("bbbb")), change_bars=False)
    assert [o for o in p.of("line") if o[5] == BAR_WIDTH] == []
    assert any(o[0] == "text" and o[3] == "1" for o in p.ops)      # the number stays


def test_grid_draws_four_rules_per_cell_and_skips_a_merged_top():
    body = TBL([["a", "b"]], [4680, 4680])
    L = _lay(body, body)
    p = RecordingPainter()
    draw_grid(L.pages[0], p)
    (row,) = L.pages[0].table_rows
    c0, c1 = row.cells
    assert len(p.of("line")) == 8 and {o[5] for o in p.of("line")} == {GRID_WIDTH}
    assert ("line", c0.x, c0.y, c0.x + c0.w, c0.y, GRID_WIDTH, BLACK) in p.ops       # top
    assert ("line", c1.x + c1.w, c1.y, c1.x + c1.w, c1.y + c1.h, GRID_WIDTH, BLACK) in p.ops   # right
    c1.v_merge_continue = True
    p2 = RecordingPainter()
    draw_grid(L.pages[0], p2)
    assert len(p2.of("line")) == 7 and ("line", c1.x, c1.y, c1.x + c1.w, c1.y, GRID_WIDTH, BLACK) not in p2.ops


def test_changed_table_row_gets_one_bar_for_the_whole_row():
    a = TBL([["a", "b"]], [4680, 4680])
    b = TBL([["a", "bbbb bbbb"]], [4680, 4680])
    L = _lay(a, b)
    (row,) = L.pages[0].table_rows
    assert row.changed
    assert bar_intervals(L.pages[0]) == [(row.y, row.y + row.h)]
    p = _page(L)
    x = 72 - BAR_GAP
    assert [o for o in p.of("line") if o[5] == BAR_WIDTH] == [("line", x, row.y, x, row.y + row.h, BAR_WIDTH, BLACK)]
    assert any(o[0] == "text" and o[3] == "1" and o[5] == NUMBER_SIZE for o in p.ops)


def test_changes_starting_on_one_baseline_share_one_gutter_label():
    # three cells of one row, each with its own change: one "1-3" label, not three overprinted digits
    a = TBL([["aaaa", "bbbb", "cccc"]], [3120, 3120, 3120])
    b = TBL([["aaaa x", "bbbb y", "cccc z"]], [3120, 3120, 3120])
    L = _lay(a, b)
    p = RecordingPainter()
    draw_page(L.pages[0], L.fonts, STANDARD, PdfOptions(), p, FR.face(None))
    labels = [o for o in p.of("text") if o[5] == NUMBER_SIZE]
    assert [o[3] for o in labels] == ["1-3"]
    assert labels[0][1] == 72 - NUMBER_GAP - FR.face(None).width("1-3", NUMBER_SIZE)


def test_page_draws_grid_then_text_then_gutter():
    body = TBL([["a"]], [9360])
    p = _page(_lay(body, body))
    kinds = [o[0] for o in p.ops]
    assert kinds[0] == "page" and kinds[1:5] == ["line"] * 4 and "text" in kinds[5:]


def test_content_bottom():
    L = _lay(P("aaaa"), P("aaaa") + P("bbbb"))
    assert content_bottom(L.pages[0]) == 96
    body = TBL([["a"]], [9360])
    L2 = _lay(body, body)
    (row,) = L2.pages[0].table_rows
    assert content_bottom(L2.pages[0]) == row.y + row.h
    empty = _lay("", "")
    assert content_bottom(empty.pages[0]) == 72


def _info():
    s = {"total": 1, "insertions": 1, "deletions": 0, "amendments": 0, "numbering": 0, "formatting": 0}
    return ReportInfo("a.docx", "b.docx", WHEN, "Standard", s, False, True)


def _layout(L, info, **kw):
    p = RecordingPainter()
    res = draw_layout(L, STANDARD, PdfOptions(**kw), p, FR, info)
    return p, res


def test_report_on_the_last_page_when_it_fits():
    p, res = _layout(_lay(P("aaaa"), P("aaaa") + P("bbbb")), _info())
    assert res == DrawResult(1, 1) and p.pages == 1
    title = next(o for o in p.of("text") if o[3] == TITLE)
    assert title[2] == 96 + GAP + 6 + 0.8 * 11          # content bottom 96, gap, rule gap, ascent
    assert title[4] == "<fake:Fake|B>"


def test_report_moves_to_an_extra_page_when_it_does_not_fit():
    body = "".join(P(f"p{i}") for i in range(54))       # exactly fills page 1 (54 x 12 = 648)
    p, res = _layout(_lay(body, body), _info())
    assert res == DrawResult(2, 2) and p.pages == 2
    assert p.of("page")[1] == ("page", 612, 792)
    title = next(o for o in p.of("text") if o[3] == TITLE)
    assert title[2] == 72 + 6 + 0.8 * 11


def test_report_first_and_none():
    L = _lay(P("aaaa"), P("aaaa"))
    p, res = _layout(L, _info(), report="first")
    assert res == DrawResult(2, 1) and p.page_ops(1)[1][3] == TITLE and p.page_ops(2)[0][3] == "aaaa"
    p, res = _layout(L, _info(), report="none")
    assert res == DrawResult(1, None) and not any(o[0] == "text" and o[3] == TITLE for o in p.ops)
    p, res = _layout(L, None)
    assert res == DrawResult(1, None)


def test_report_uses_the_document_family():
    L = _lay(P("aaaa"), P("aaaa"))
    p, _ = _layout(L, _info())
    faces = {o[4] for o in p.of("text") if o[3] != "aaaa"}
    assert faces == {"<fake:Fake|>", "<fake:Fake|B>"}


def test_gutter_numbers_use_the_document_face_not_the_resolver_fallback():
    L = _lay(P("aaaa"), P("aaaa") + P("bbbb"), sty=SERIF)
    p, _ = _layout(L, None, report="none")
    num = next(o for o in p.of("text") if o[3] == "1" and o[5] == NUMBER_SIZE)
    assert num[4] == "<fake:Serif|>" and FR.face(None).path == "<fake:Fake|>"


def test_every_page_is_drawn_in_order():
    body = "".join(P(f"p{i}") for i in range(100))
    p, res = _layout(_lay(body, body), None)
    assert p.pages == 2 and res.pages == 2
    assert p.page_ops(1)[0][3] == "p0" and p.page_ops(2)[0][3] == "p54"


def _three_pages(changed_last=True):
    """Page 1 changed on its first line, page 2 untouched, page 3 changed (or not)."""
    p1 = "".join(P(f"p{i}") for i in range(53))            # 53 + the first line = one page (54 x 12)
    p2 = "".join(P(f"q{i}") for i in range(54))
    a = P("aaaa") + p1 + p2 + P("zzzz")
    b = P("aaaa bbbb") + p1 + p2 + (P("zzzz yyyy") if changed_last else P("zzzz"))
    return _lay(a, b)


def test_changed_pages_are_the_pages_with_a_mark():
    L = _three_pages()
    assert L.page_count == 3 and changed_pages(L) == [1, 3]
    assert changed_pages(_three_pages(changed_last=False)) == [1]
    assert changed_pages(_lay(P("aaaa"), P("aaaa"))) == []
    tbl = TBL([["a"]], [9360])
    assert changed_pages(_lay(tbl, TBL([["ab"]], [9360]))) == [1]        # a changed row counts


def test_options_default_changed_only_off():
    assert PdfOptions().changed_only is False


def test_changed_only_emits_the_first_page_and_the_changed_pages():
    L = _three_pages()
    p, res = _layout(L, None, report="none", changed_only=True)
    assert res == DrawResult(2, None) and p.pages == 2
    assert p.page_ops(1)[0][3] == "aaaa" and p.page_ops(2)[0][3] == "zzzz"
    p, res = _layout(_three_pages(changed_last=False), None, report="none", changed_only=True)
    assert res == DrawResult(1, None)
    p, res = _layout(_lay(P("aaaa"), P("aaaa")), None, report="none", changed_only=True)
    assert res == DrawResult(1, None) and p.pages == 1                  # page 1 always


def test_changed_only_report_placement_and_line():
    L = _three_pages()
    p, res = _layout(L, _info(), report="last", changed_only=True)
    assert res == DrawResult(2, 2)
    texts = [o[3] for o in p.page_ops(2) if o[0] == "text"]
    assert TITLE in texts and "Changed pages only: 2 of 3 pages" in texts
    p, res = _layout(L, _info(), report="first", changed_only=True)
    assert res == DrawResult(3, 1) and p.page_ops(1)[1][3] == TITLE and p.page_ops(2)[0][3] == "aaaa"
    p, _ = _layout(L, _info(), report="last")
    assert "Changed pages only: 2 of 3 pages" not in [o[3] for o in p.of("text")]


# v2.4.0: drawing a side (spec §12.3).

from calandria.pdf.draw import NUMBER_SIZE, tint

SIDE_A = P("aaaa bbbb cccc") + P("gone gone")
SIDE_B = P("aaaa xxxx cccc") + P("new new")


def _side(side, **pdf):
    L = layout(compare(_parse(SIDE_A), _parse(SIDE_B)), LayoutOptions(fonts=FR, side=side))
    p = RecordingPainter()
    draw_layout(L, STANDARD, PdfOptions(report="none", **pdf), p, FR, None)
    return L, p


def test_tint_mixes_the_colour_fifteen_percent_into_white():
    assert tint("ff0000") == "ffd9d9" and tint("0000ff") == "d9d9ff" and tint("000000") == "d9d9d9"


def test_a_side_is_drawn_plain_without_bars_numerals_or_decorations():
    _, p = _side("original")
    assert p.of("rule") == [] and p.of("line") == []          # no strike, no underline, no change bar
    assert all(op[6] == "000000" for op in p.of("text"))       # every run black
    assert not any(op[5] == NUMBER_SIZE for op in p.of("text"))   # no gutter numerals (they are the only 7 pt text)
    assert p.of("box") == []


def test_marks_tint_the_side_s_own_changed_runs_only():
    L, p = _side("original", marks=True)
    dels = [(ln, g) for pg in L.pages for ln in pg.lines for g in ln.runs if g.mode == "del"]
    assert dels and p.of("box") == [("box", round(g.x, 2), round(ln.top, 2), round(g.w, 2), round(ln.height, 2), "ffd9d9")
                                    for ln, g in dels]
    L2, p2 = _side("modified", marks=True)
    inss = [g for pg in L2.pages for ln in pg.lines for g in ln.runs if g.mode == "ins"]
    assert inss and [op[5] for op in p2.of("box")] == ["d9d9ff"] * len(inss)


def test_marks_never_touch_the_blackline():
    _, p = _side("blackline", marks=True)
    assert p.of("box") == [] and p.of("rule")                  # the redline decorations are still drawn
