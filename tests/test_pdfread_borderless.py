from delta.model import Paragraph, Table
from delta.pdfread.borderless import find_borderless
from delta.pdfread.build import build_document
from delta.pdfread.lines import build_lines
from delta.pdfread.types import PageLines, TextRun

SCHEDULES = [("Schedule A", "Site and Designated Areas"), ("Schedule B", "Specifications"),
             ("Schedule 2.1(d)", "Reliance Information"), ("Schedule 2.2(a)", "Organizational Chart")]


def R(text, x0, y, size=10.0):
    return TextRun(text, x0, x0 + 5.0 * len(text), y, size, "Arial")


def rows(pairs, y=100.0, pitch=12.0, xs=(77.0, 209.0)):
    return [R(t, x, y + i * pitch) for i, cells in enumerate(pairs) for t, x in zip(cells, xs)]


def find(runs):
    return find_borderless(build_lines(runs), first=0)


def test_a_tab_records_where_each_piece_of_the_line_starts_and_ends():
    (ln,) = build_lines([R("Schedule A", 77, 100), R("Site", 209, 100)])
    assert ln.text == "Schedule A\tSite"
    assert ln.cols == ((77, 127), (209, 229))


def test_aligned_tabbed_lines_become_a_grid_and_each_piece_a_cell_line():
    grids, lines = find(rows(SCHEDULES))
    (g,) = grids
    assert len(g.cells) == 8 and len(g.xs) == 3 and len(g.ys) == 5
    assert [(ln.text, ln.cell) for ln in lines[:2]] == [("Schedule A", (0, 0)), ("Site and Designated Areas", (0, 1))]
    assert all(ln.cell is not None for ln in lines)
    assert lines[1].x0 == 209 and lines[1].x1 == 209 + 5.0 * 25


def test_a_line_wrapped_in_a_later_column_stays_in_its_cell():
    runs = rows(SCHEDULES[:2]) + [R("and Access Roads", 209, 124)] + rows(SCHEDULES[2:], y=136)
    (g,), lines = find(runs)
    assert len(g.ys) == 5
    cell = [ln.text for ln in lines if ln.cell == (0, 3)]
    assert cell == ["Specifications", "and Access Roads"]


def test_the_header_row_counts_even_after_a_blank_row():
    runs = rows([("Schedule", "Description")], y=76) + rows(SCHEDULES)
    (g,), _lines = find(runs)
    assert len(g.ys) == 6


def test_two_rows_lists_contents_lines_and_misaligned_tabs_stay_paragraphs():
    assert find(rows(SCHEDULES[:2]))[0] == []
    markers = [("(a)", "the Work"), ("(b)", "the Site"), ("(c)", "the Price")]
    assert find(rows(markers))[0] == []
    bare = [("G", "Any Company"), ("H", "Each Company"), ("J", "If any Company")]
    assert find(rows(bare))[0] == []
    toc = [("16.16 Publicity", "......... 65"), ("Pricing", "......... 66"), ("Notice", "......... 67")]
    assert find(rows(toc))[0] == []
    ragged = [R(t, x, 100 + 12 * i) for i, (a, b) in enumerate(SCHEDULES) for t, x in ((a, 77), (b, 209 + 9 * i))]
    assert find(ragged)[0] == []


def test_a_far_gap_ends_the_table():
    runs = rows(SCHEDULES) + rows(SCHEDULES, y=300)
    grids, _lines = find(runs)
    assert len(grids) == 2


def test_cell_lines_point_past_the_ruled_grids_already_on_the_page():
    (g,), lines = find_borderless(build_lines(rows(SCHEDULES)), first=2)
    assert {ln.cell[0] for ln in lines} == {2}


def test_the_document_reads_the_list_as_a_two_column_table():
    grids, lines = find(rows([("Schedule", "Description")], y=76) + rows(SCHEDULES))
    pg = PageLines(0, 612.0, 792.0, sorted(lines, key=lambda l: (l.y, l.x0)), grids, [])
    doc = build_document([pg], set(), {}, 1, ())
    (t,) = [b for b in doc.blocks if isinstance(b, Table)]
    assert [[c.blocks[0].text for c in r.cells] for r in t.rows][:2] == [["Schedule", "Description"],
                                                                        ["Schedule A", "Site and Designated Areas"]]
    assert len(t.grid_pt) == 2 and not [b for b in doc.blocks if isinstance(b, Paragraph)]
