import io

from calandria.diff.compare import compare
from calandria.docx.parser import parse_docx
from calandria.layout.blocks import Ctx, ParaBlock
from calandria.layout.merged import merged_items
from calandria.layout.pieces import LayoutOptions
from calandria.layout.tables import TableRowBlock, table_blocks, table_maps, table_runs
from calandria.testing.makedocx import DOC, P, STYLES, TBL, make_docx
from calandria.testing.fakefonts import FakeResolver

FR = FakeResolver()                       # 5 pt per character at size 10, line height 12
STY = STYLES('<w:rFonts w:ascii="Fake"/><w:sz w:val="20"/>')


def _parse(body):
    return parse_docx(io.BytesIO(make_docx({"word/document.xml": DOC(body), "word/styles.xml": STY})))


def _items(body_a, body_b):
    c = compare(_parse(body_a), _parse(body_b))
    return c, merged_items(c)


def _ctx(c, content_w=200.0, avail_h=600.0, **opts):
    d = c.b_doc
    return Ctx(c, LayoutOptions(fonts=FR, **opts), FR, content_w, avail_h, d.default_font, d.default_size_pt,
               d.default_tab_pt)


def _blocks(c, items, **kw):
    (s, e), = table_runs(items, table_maps(c))
    return table_blocks(items[s:e], _ctx(c, **kw))


def _tbl(rows, grid=None, tblpr=""):
    return P("intro") + TBL(rows, grid, tblpr) + P("outro")


def test_table_runs_split_adjacent_tables_and_stop_at_body_text():
    body = P("i") + TBL([["a"]]) + TBL([["b"]]) + P("o") + TBL([["c", "d"]])
    c, items = _items(body, body)
    assert table_runs(items, table_maps(c)) == [(1, 2), (2, 3), (4, 6)]


def test_two_column_row_geometry():
    body = _tbl([["aaaa", "bb"]])
    c, items = _items(body, body)
    (blk,) = _blocks(c, items)
    assert isinstance(blk, TableRowBlock)
    assert (blk.x, blk.w, blk.height, blk.line_heights, blk.changed) == (0, 200, 12, [12], False)
    assert [(cell.x, cell.w) for cell in blk.cells] == [(0, 100), (100, 100)]
    assert [len(cell.paras) for cell in blk.cells] == [1, 1]


def test_row_height_is_the_tallest_cell():
    body = _tbl([["aaaa bbbb cccc dddd eeee ffff gggg hhhh", "x"]])   # cell text width 89.2 -> 3 lines
    c, items = _items(body, body)
    (blk,) = _blocks(c, items)
    assert blk.height == 36 and len(blk.cells[0].paras[0].lines) == 3


def test_grid_widths_scale_down_to_the_content_width():
    body = _tbl([["a", "b"]], grid=[6000, 2000])                         # 300 + 100 pt into 200 pt
    c, items = _items(body, body)
    (blk,) = _blocks(c, items)
    assert [(cell.x, cell.w) for cell in blk.cells] == [(0, 150), (150, 50)] and blk.w == 200


def test_grid_widths_are_kept_when_they_fit():
    body = _tbl([["a", "b"]], grid=[1440, 1440])
    c, items = _items(body, body)
    (blk,) = _blocks(c, items)
    assert [(cell.x, cell.w) for cell in blk.cells] == [(0, 72), (72, 72)] and blk.w == 144


def test_table_indent_shifts_the_row_and_narrows_it():
    body = _tbl([["a", "b"]], tblpr='<w:tblPr><w:tblInd w:w="720" w:type="dxa"/></w:tblPr>')
    c, items = _items(body, body)
    (blk,) = _blocks(c, items)
    assert blk.x == 36 and blk.w == 164 and [cell.w for cell in blk.cells] == [82, 82]


def test_grid_span_cell_covers_two_columns():
    body = (P("i") + '<w:tbl><w:tr><w:tc><w:tcPr><w:gridSpan w:val="2"/></w:tcPr>' + P("wide") + "</w:tc></w:tr>"
            "<w:tr><w:tc>" + P("a") + "</w:tc><w:tc>" + P("b") + "</w:tc></w:tr></w:tbl>" + P("o"))
    c, items = _items(body, body)
    r1, r2 = _blocks(c, items)
    assert [(cell.x, cell.w) for cell in r1.cells] == [(0, 200)]
    assert [(cell.x, cell.w) for cell in r2.cells] == [(0, 100), (100, 100)]


def test_row_heights_exact_and_at_least():
    body = (P("i") + '<w:tbl><w:tr><w:trPr><w:trHeight w:val="600" w:hRule="exact"/></w:trPr><w:tc>' + P("a")
            + "</w:tc></w:tr><w:tr><w:trPr><w:trHeight w:val=\"400\"/></w:trPr><w:tc>" + P("b")
            + "</w:tc></w:tr><w:tr><w:trPr><w:trHeight w:val=\"100\"/></w:trPr><w:tc>" + P("c")
            + "</w:tc></w:tr></w:tbl>" + P("o"))
    c, items = _items(body, body)
    assert [b.height for b in _blocks(c, items)] == [30, 20, 12]


def test_changed_cell_flags_the_row_and_collects_change_numbers():
    a = _tbl([["h", "x"], ["old value", "y"]])
    b = _tbl([["h", "x"], ["new value", "y"]])
    c, items = _items(a, b)
    r1, r2 = _blocks(c, items)
    assert (r1.changed, r1.cids) == (False, []) and (r2.changed, r2.cids) == (True, [1])


def test_deleted_row_comes_from_the_original_table():
    a = _tbl([["h"], ["gone"]])
    b = _tbl([["h"]])
    c, items = _items(a, b)
    r1, r2 = _blocks(c, items)
    assert r2.changed and r2.cells[0].paras[0].lines[0].runs[0].piece.mode == "del"
    assert (r2.cells[0].x, r2.cells[0].w) == (0, 200)


def test_hidden_deleted_row_is_dropped_but_equal_rows_stay_under_hide_unchanged():
    a = _tbl([["h", "x"], ["gone", "y"]])
    b = _tbl([["h", "x"]])
    c, items = _items(a, b)
    assert len(_blocks(c, items, show_deletions=False)) == 1
    assert len(_blocks(c, items, show_equal=False)) == 2


def test_page_tall_row_degrades_to_stacked_paragraphs():
    body = _tbl([["aaaa", "bb"]])
    c, items = _items(body, body)
    blocks = _blocks(c, items, avail_h=20)          # any row taller than 8 pt is "page-tall"
    assert [type(b) for b in blocks] == [ParaBlock, ParaBlock]
    assert [(b.x, b.space_after) for b in blocks] == [(0, 2), (0, 2)]


def test_empty_cell_paragraph_still_gives_the_row_a_line():
    body = _tbl([["", "x"]])
    c, items = _items(body, body)
    (blk,) = _blocks(c, items)
    assert blk.height == 12 and blk.cells[0].paras[0].lines[0].runs == []


def test_first_row_inherits_a_page_break_before():
    body = P("i") + "<w:p><w:r><w:br w:type=\"page\"/></w:r></w:p>" + TBL([["a"]]) + P("o")
    c, items = _items(body, body)
    (blk,) = _blocks(c, items)
    assert blk.page_break_before


def test_deleted_paragraph_inside_a_cell_stays_in_its_row():
    a = (P("i") + "<w:tbl><w:tr><w:tc>" + P("keep me") + P("drop me") + "</w:tc><w:tc>" + P("second")
         + "</w:tc></w:tr></w:tbl>" + P("o"))
    b = _tbl([["keep me", "second"]])
    c, items = _items(a, b)
    (blk,) = _blocks(c, items)
    assert [len(cell.paras) for cell in blk.cells] == [2, 1] and blk.changed
    assert blk.cells[0].paras[1].lines[0].runs[0].piece.mode == "del"


def test_deleted_paragraph_in_the_last_cell_stays_in_its_row():
    a = (P("i") + "<w:tbl><w:tr><w:tc>" + P("first") + "</w:tc><w:tc>" + P("keep me") + P("drop me")
         + "</w:tc></w:tr></w:tbl>" + P("o"))
    b = _tbl([["first", "keep me"]])
    c, items = _items(a, b)
    (blk,) = _blocks(c, items)
    assert [len(cell.paras) for cell in blk.cells] == [1, 2] and blk.changed


def test_deleted_table_before_a_kept_table_keeps_its_own_geometry():
    a = P("i") + TBL([["gone"]]) + TBL([["k1", "k2"]]) + P("o")
    b = P("i") + TBL([["k1", "k2"]]) + P("o")
    c, items = _items(a, b)
    runs = table_runs(items, table_maps(c))
    assert len(runs) == 2
    (d,) = table_blocks(items[runs[0][0]:runs[0][1]], _ctx(c))
    assert [(cell.x, cell.w) for cell in d.cells] == [(0, 200)] and d.changed
    (k,) = table_blocks(items[runs[1][0]:runs[1][1]], _ctx(c))
    assert [(cell.x, cell.w) for cell in k.cells] == [(0, 100), (100, 100)] and not k.changed


def test_whole_deleted_row_stays_in_the_surviving_table():
    a = _tbl([["h", "x"], ["gone", "y"]])
    b = _tbl([["h", "x"]])
    c, items = _items(a, b)
    assert len(table_runs(items, table_maps(c))) == 1
    r1, r2 = _blocks(c, items)
    assert [(cell.x, cell.w) for cell in r2.cells] == [(0, 100), (100, 100)] and r2.changed


def test_overflow_cell_beyond_the_grid_gets_no_width():
    body = (P("i") + '<w:tbl><w:tblGrid><w:gridCol w:w="1440"/><w:gridCol w:w="1440"/></w:tblGrid><w:tr><w:tc>'
            + P("a") + "</w:tc><w:tc>" + P("b") + "</w:tc><w:tc>" + P("c") + "</w:tc></w:tr></w:tbl>" + P("o"))
    c, items = _items(body, body)
    (blk,) = _blocks(c, items)
    assert [(cell.x, cell.w) for cell in blk.cells] == [(0, 72), (72, 72), (144, 0)]
