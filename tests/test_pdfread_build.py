import pytest

from calandria.model import NoteRef, Paragraph, Table
from calandria.pdfread.build import body_metrics, build_document, split_font
from calandria.pdfread.grid import find_grids
from calandria.pdfread.types import Line, PageLines, Seg, Span

FULL = "The Supplier shall deliver the Goods to the Buyer at the Delivery Point on the agreed date"


def L(text, y, page=0, x0=72.0, x1=540.0, size=12.0, cell=None, font="Arial", spans=None):
    return Line(page, x0, x1, y, size, spans or [Span(text, font, size)], cell)


def page(i, lines, segs=()):
    return PageLines(i, 612.0, 792.0, sorted(lines, key=lambda l: (l.y, l.x0)), find_grids(list(segs)), list(segs))


def lattice(xs, ys):
    return [Seg(xs[0], y, xs[-1], y) for y in ys] + [Seg(x, ys[0], x, ys[-1]) for x in xs]


@pytest.mark.parametrize("name, want", [
    ("ABCDEF+TimesNewRomanPS-BoldItalicMT", ("Times New Roman", True, True)),
    ("Arial,Bold", ("Arial", True, False)),
    ("ArialMT", ("Arial", False, False)),
    ("Arial-ItalicMT", ("Arial", False, True)),
    ("Calibri-Light", ("Calibri Light", False, False)),
    ("MPDFAA+TimesNewRomanBold", ("Times New Roman", True, False)),
    ("Helvetica-Oblique", ("Helvetica", False, True)),
    ("CourierNewPSMT", ("Courier New", False, False)),
    ("Verdana,BoldItalic", ("Verdana", True, True)),
    ("BCDFEE+Cambria", ("Cambria", False, False)),
    ("Wingdings-Regular", ("Wingdings", False, False)),
    ("SegoeUI-Semibold", ("Segoe UI Semibold", False, False)),
])
def test_split_font(name, want):
    assert split_font(name) == want


def test_the_margin_floor_is_a_share_of_the_page_not_an_absolute_number():
    pg = page(0, [L(FULL, 100, x0=5, x1=200)])
    (sec,) = build_document([pg], set(), {}, 1, ()).sections
    assert sec.margin_left_pt == 18.5                      # 0.03 * 612 = 18.36 -> _half -> 18.5
    wide = PageLines(0, 1224.0, 792.0, list(pg.lines), pg.grids, pg.segs)
    (sec_wide,) = build_document([wide], set(), {}, 1, ()).sections
    assert sec_wide.margin_left_pt == 36.5                  # 0.03 * 1224 = 36.72 -> _half -> 36.5
    assert sec_wide.margin_left_pt > 2 * sec.margin_left_pt - 1


def test_a_stripped_header_grid_does_not_pull_the_top_margin():
    segs = lattice([72, 272, 472], [20, 60])
    pg = page(0, [L("Left", 40, x0=78, x1=110, cell=(0, 0)), L("Right", 40, x0=278, x1=310, cell=(0, 1)),
                  L("Body", 300, x1=200)], segs)
    skip = {(0, 0), (0, 1)}
    (sec,) = build_document([pg], skip, {}, 1, ()).sections
    assert sec.margin_top_pt == 288.0                       # 300 - 12, not pulled up to 20 by the stripped grid


def test_body_metrics_take_the_margin_not_an_outlier_and_the_commonest_size():
    lines = [L(FULL, 100 + 14 * i) for i in range(10)] + [L("x", 300, x0=60, x1=80), L("Big", 60, size=20, x1=120)]
    assert body_metrics([page(0, lines)], set()) == (72.0, 540.0, 12.0)
    assert body_metrics([page(0, [])], set()) == (72.0, 540.0, 11.0)


def test_paragraphs_runs_and_the_section():
    bold = [Span("Term. ", "Arial,Bold", 12.0), Span(FULL[:70], "Arial", 12.0)]
    doc = build_document([page(0, [L("", 100, spans=bold), L(FULL, 113.8), L("The end.", 160, x1=120)])], set(), {}, 1, ())
    first, second = doc.blocks
    assert [(r.text[:6], r.props.bold, r.props.font, r.props.size_pt) for r in first.runs][0] == ("Term. ", True, "Arial", 12.0)
    assert first.runs[1].props.bold is False and second.text == "The end."
    assert first.props.space_after_pt == 32.5 and second.props.space_after_pt == 32.5      # the last one takes the commonest
    (sec,) = doc.sections
    assert (sec.page_w_pt, sec.page_h_pt, sec.margin_left_pt, sec.margin_right_pt) == (612.0, 792.0, 72.0, 72.0)
    assert (sec.margin_top_pt, sec.margin_bottom_pt) == (88.0, 317.0)      # top: 100-12; bottom: 792-(160+0.3*12)
    assert (doc.source_kind, doc.source_pages, doc.skipped_pages, doc.default_font, doc.default_size_pt) == (
        "pdf", 1, (), "Arial", 12.0)


def test_a_hanging_marker_gets_a_tab_and_a_tab_stop():
    lines = [L("(a) " + FULL, 100), L(FULL, 113.8, x0=108), L(FULL, 127.6, x0=108)]
    (p,) = build_document([page(0, lines)], set(), {}, 1, ()).blocks
    assert p.runs[0].text.startswith("(a)\tThe Supplier")
    assert (p.props.ind_left_pt, p.props.ind_hanging_pt) == (36.0, 36.0)
    assert [t.pos_pt for t in p.props.tabs] == [36.0]


def test_a_ruled_grid_becomes_a_table_between_paragraphs_with_merged_cells():
    segs = [Seg(72, 200, 472, 200), Seg(72, 220, 472, 220), Seg(72, 240, 472, 240),
            Seg(72, 200, 72, 240), Seg(472, 200, 472, 240), Seg(272, 220, 272, 240)]     # top row spans both columns
    pg = page(0, [L("Before", 100), L("Prices", 214, x0=78, x1=120, cell=(0, 0)),
                  L("Widget", 234, x0=78, x1=120, cell=(0, 1)), L("10.00", 234, x0=278, x1=310, cell=(0, 2)),
                  L("After", 300, x1=110)], segs)
    before, table, after = build_document([pg], set(), {}, 1, ()).blocks
    assert isinstance(table, Table) and (before.text, after.text) == ("Before", "After")
    assert table.grid_pt == [200.0, 200.0] and table.ind_pt == 0.0
    assert [[(c.grid_span, c.blocks[0].text) for c in r.cells] for r in table.rows] == [
        [(2, "Prices")], [(1, "Widget"), (1, "10.00")]]


def test_vertical_merges_restart_and_continue_and_empty_cells_hold_a_paragraph():
    segs = [Seg(72, 200, 472, 200), Seg(72, 240, 472, 240), Seg(72, 200, 72, 240), Seg(272, 200, 272, 240),
            Seg(472, 200, 472, 240), Seg(272, 220, 472, 220)]                            # the left column spans both rows
    pg = page(0, [L("Both", 224, x0=78, x1=110, cell=(0, 0))], segs)
    (table,) = build_document([pg], set(), {}, 1, ()).blocks
    assert [[c.v_merge for c in r.cells] for r in table.rows] == [["restart", None], ["continue", None]]
    assert all(isinstance(c.blocks[0], Paragraph) for r in table.rows for c in r.cells)


def two_page_table(header_again: bool):
    p0 = page(0, [L("Intro", 100, x1=110), L("Item", 714, x0=78, x1=110, cell=(0, 0)), L("Price", 714, x0=278, x1=310, cell=(0, 1)),
                  L("Bolt", 734, x0=78, x1=110, cell=(0, 2)), L("1.00", 734, x0=278, x1=310, cell=(0, 3))],
              lattice([72, 272, 472], [700, 720, 740]))
    top = [L("Item", 94, 1, x0=78, x1=110, cell=(0, 0)), L("Price", 94, 1, x0=278, x1=310, cell=(0, 1))] if header_again else \
          [L("Nut", 94, 1, x0=78, x1=110, cell=(0, 0)), L("0.50", 94, 1, x0=278, x1=310, cell=(0, 1))]
    p1 = page(1, top + [L("Washer", 114, 1, x0=78, x1=120, cell=(0, 2)), L("0.10", 114, 1, x0=278, x1=310, cell=(0, 3)),
                        L("Outro", 300, 1, x1=110)], lattice([72, 272, 472], [80, 100, 120]))
    return build_document([p0, p1], set(), {}, 2, ()).blocks


def test_a_table_continuing_on_the_next_page_is_stitched_and_a_repeated_header_row_dropped():
    intro, table, outro = two_page_table(header_again=True)
    assert [r.cells[0].blocks[0].text for r in table.rows] == ["Item", "Bolt", "Washer"]
    intro, table, outro = two_page_table(header_again=False)
    assert [r.cells[0].blocks[0].text for r in table.rows] == ["Item", "Bolt", "Nut", "Washer"]


def test_tables_with_different_columns_or_text_between_them_stay_apart():
    p0 = page(0, [L("A", 714, x0=78, x1=90, cell=(0, 0)), L("B", 714, x0=278, x1=290, cell=(0, 1))],
              lattice([72, 272, 472], [700, 720]))
    other = page(1, [L("C", 94, 1, x0=78, x1=90, cell=(0, 0)), L("D", 94, 1, x0=378, x1=390, cell=(0, 1))],
                 lattice([72, 372, 472], [80, 100]))
    assert sum(isinstance(b, Table) for b in build_document([p0, other], set(), {}, 2, ()).blocks) == 2
    same = page(1, [L("Continued overleaf", 60, 1), L("C", 94, 1, x0=78, x1=90, cell=(0, 0)),
                    L("D", 94, 1, x0=278, x1=290, cell=(0, 1))], lattice([72, 272, 472], [80, 100]))
    blocks = build_document([p0, same], set(), {}, 2, ()).blocks
    assert [type(b).__name__ for b in blocks] == ["Table", "Paragraph", "Table"]


def test_skipped_lines_are_left_out_and_a_grid_of_only_skipped_lines_disappears():
    segs = lattice([72, 272, 472], [20, 60])
    pg = page(0, [L("Logo", 45, x0=78, x1=110, cell=(0, 0)), L("Body", 300, x1=110), L("Page 1", 760, x1=110)], segs)
    skip = {(0, 0), (0, 2)}
    (only,) = build_document([pg], skip, {}, 1, ()).blocks
    assert only.text == "Body"


def test_a_superscript_number_with_a_note_becomes_a_reference_and_others_stay_text():
    spans = [Span("the Supplier", "Arial", 12.0), Span("1", "Arial", 8.0, True), Span(" and the 2", "Arial", 12.0),
             Span("nd", "Arial", 8.0, True), Span(" party", "Arial", 12.0)]
    notes = {1: [L("See clause 4.", 702, size=9.0, x1=160)]}
    doc = build_document([page(0, [L("", 100, spans=spans)])], set(), notes, 1, ())
    (p,) = doc.blocks
    ref = NoteRef("footnote", 1)
    assert [r.props.note for r in p.runs].count(ref) == 1 and "nd" in p.text
    assert doc.footnotes[1][0].text == "See clause 4." and doc.note_numbers == {ref: 1}


def test_a_note_nothing_refers_to_is_kept_as_body_text_at_the_end():
    doc = build_document([page(0, [L("Body", 100, x1=110)])], set(), {7: [L("Orphan note", 702, size=9.0, x1=150)]}, 1, ())
    assert [b.text for b in doc.blocks] == ["Body", "Orphan note"] and doc.footnotes == {}


def test_a_table_wider_than_the_text_is_scaled_to_fit():
    pg = page(0, [L(FULL, 100), L("Wide", 214, x0=40, x1=70, cell=(0, 0)), L("er", 214, x0=400, x1=420, cell=(0, 1))],
              lattice([36, 336, 636], [200, 220]))
    table = next(b for b in build_document([pg], set(), {}, 1, ()).blocks if isinstance(b, Table))
    assert sum(table.grid_pt) == pytest.approx(468.0) and table.ind_pt == 0.0
