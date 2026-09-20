from calandria.pdfread.grid import find_grids
from calandria.pdfread.types import Seg


def H(y, x0, x1):
    return Seg(x0, y, x1, y)


def V(x, y0, y1):
    return Seg(x, y0, x, y1)


def lattice(xs, ys):
    return [H(y, xs[0], xs[-1]) for y in ys] + [V(x, ys[0], ys[-1]) for x in xs]


def test_a_three_by_three_lattice_is_nine_cells():
    (g,) = find_grids(lattice([72, 172, 272, 372], [100, 120, 140, 160]))
    assert (g.xs, g.ys) == ([72, 172, 272, 372], [100, 120, 140, 160])
    assert len(g.cells) == 9 and all(c.rowspan == c.colspan == 1 for c in g.cells)
    assert [(c.row, c.col) for c in g.cells[:4]] == [(0, 0), (0, 1), (0, 2), (1, 0)]
    assert (g.x0, g.y0, g.x1, g.y1) == (72, 100, 372, 160)
    assert g.cells[g.cell_at(200, 130)].row == 1 and g.cells[g.cell_at(200, 130)].col == 1
    assert g.cell_at(10, 10) is None


def test_borders_drawn_cell_by_cell_with_jitter_merge_into_one_grid():
    segs = []
    for r, (y0, y1) in enumerate([(100, 120), (120.4, 140)]):
        for x0, x1 in [(72, 172.3), (172, 272)]:
            segs += [H(y0, x0, x1), H(y1, x0, x1), V(x0, y0, y1), V(x1, y0, y1)]
    (g,) = find_grids(segs)
    assert len(g.xs) == 3 and len(g.ys) == 3 and len(g.cells) == 4


def test_a_missing_interior_segment_is_a_merged_cell():
    segs = [H(100, 72, 272), H(120, 72, 272), H(140, 72, 272), V(72, 100, 140), V(272, 100, 140),
            V(172, 120, 140)]                                   # the top row has no divider: it spans two columns
    (g,) = find_grids(segs)
    top = g.cells[0]
    assert (top.row, top.col, top.rowspan, top.colspan) == (0, 0, 1, 2) and len(g.cells) == 3
    segs = [H(100, 72, 272), H(140, 72, 272), V(72, 100, 140), V(172, 100, 140), V(272, 100, 140),
            H(120, 172, 272)]                                   # the left column has no divider: it spans two rows
    (g,) = find_grids(segs)
    left = g.cells[0]
    assert (left.rowspan, left.colspan, left.y1) == (2, 1, 140) and len(g.cells) == 3


def test_things_that_are_not_tables():
    assert find_grids([H(100, 72, 300)]) == []                                  # an underline
    assert find_grids([H(100, 72, 300), H(103, 72, 300)]) == []                 # a double rule
    assert find_grids(lattice([72, 300], [100, 140])) == []                     # a boxed paragraph: one cell
    assert find_grids([]) == []


def test_an_underline_inside_a_cell_does_not_split_it():
    segs = lattice([72, 172, 272], [100, 140]) + [H(125, 80, 150)]
    (g,) = find_grids(segs)
    assert len(g.cells) == 2 and g.ys == [100, 140]


def test_two_tables_are_two_grids_top_first_and_a_nested_grid_is_dropped():
    lower, upper = lattice([72, 172, 272], [400, 420, 440]), lattice([72, 272, 472], [100, 120, 140])
    a, b = find_grids(lower + upper)
    assert (a.y0, b.y0) == (100, 400)
    outer = lattice([72, 300, 540], [100, 300])
    inner = lattice([80, 150, 220], [120, 140, 160])
    (g,) = find_grids(outer + inner)
    assert g.x1 == 540
