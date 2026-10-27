"""Borderless tables: body lines split by tabs into pieces that start at the same places, line after
line (a list of schedules, an index of forms), are a table drawn without borders. Each such line is
a row and each piece a cell line, under a Grid made up from the text, so the ruled-table path reads
them from there. Geometry only: every row has the same number of pieces and each starts where the
first row's does."""
from __future__ import annotations

import re
from dataclasses import replace

from .grid import Grid, GridCell
from .paras import LEADER, MARKER
from .types import Line, Span

MIN_ROWS = 3        # fewer aligned lines are a tabbed paragraph or two, not a table
ALIGN = 0.3         # of the font size: piece starts this close are the same column
ROW_GAP = 2.5       # of the font size, baseline to baseline: rows of one table lie closer (a header
                    # over an empty row: 2.3 on a 198-page contract's schedule list; its rows 1.1-1.2)
WRAP_GAP = 1.5      # of the font size: a line wrapped inside a cell follows the line above this closely
PAD = 5.4           # pt: Word's default cell padding, from a column's edge to its text
# LABEL: a list item's number with no punctuation at all ("G", "12", "iv"), which MARKER leaves to
# the hanging indent; a lettered clause list in a 198-page contract's appendix numbers this way.
LABEL = re.compile(r"^(\d{1,3}(\.\d{1,3})*|[A-Za-z]|[ivxlcdm]{1,7})$")


def _is_row(ln: Line) -> bool:
    """A line that can be a table row: split by tabs, not a list item, not a contents line."""
    lead = ln.text.split("\t", 1)[0]
    return len(ln.cols) > 1 and not LEADER.search(ln.text) and not MARKER.match(lead + " ") and not LABEL.match(lead)


def _same_columns(ln: Line, first: Line) -> bool:
    return (len(ln.cols) == len(first.cols)
            and all(abs(a[0] - b[0]) <= ALIGN * first.size for a, b in zip(ln.cols, first.cols)))


def _wrap_column(ln: Line, first: Line) -> int | None:
    """The column (never the first) a line without tabs carries on, or None."""
    if ln.cols:
        return None
    for k, (x0, _x1) in enumerate(first.cols[1:], 1):
        if abs(ln.x0 - x0) <= ALIGN * first.size:
            return k
    return None


def _pieces(ln: Line) -> list[Line]:
    """The line cut at its tabs, one Line per piece, each spanning its own ink."""
    out: list[list[Span]] = [[]]
    for s in ln.spans:
        parts = s.text.split("\t")
        for i, part in enumerate(parts):
            if i:
                out.append([])
            if part:
                out[-1].append(replace(s, text=part))
    lines = []
    for spans, (x0, x1) in zip(out, ln.cols):
        spans[0] = replace(spans[0], text=spans[0].text.lstrip())
        spans[-1] = replace(spans[-1], text=spans[-1].text.rstrip())
        lines.append(Line(ln.page, x0, x1, ln.y, ln.size, [s for s in spans if s.text]))
    return lines


def _grid(rows: list[list[Line]]) -> Grid:
    first = rows[0][0]
    n = len(first.cols)
    starts = [sum(r[0].cols[k][0] for r in rows) / len(rows) for k in range(n)]
    last_ends = [r[0].cols[-1][1] for r in rows] + [ln.x1 for r in rows for ln in r[1:]
                                                    if _wrap_column(ln, first) == n - 1]
    xs = [x - PAD for x in starts] + [max(last_ends) + PAD]
    tops = [min(ln.y - ln.size for ln in r) for r in rows]
    bottoms = [max(ln.y + 0.3 * ln.size for ln in r) for r in rows]
    ys = [tops[0]] + [(b + t) / 2 for b, t in zip(bottoms, tops[1:])] + [bottoms[-1]]
    cells = [GridCell(i, k, 1, 1, xs[k], ys[i], xs[k + 1], ys[i + 1]) for i in range(len(rows)) for k in range(n)]
    return Grid(xs, ys, cells)


def find_borderless(lines: list[Line], first: int) -> tuple[list[Grid], list[Line]]:
    """(the borderless tables among a page's body lines, the lines with each table's turned into its
    cell lines). `first` is the index the first new grid takes on the page, after the ruled ones."""
    groups: list[list[list[Line]]] = []
    cur: list[list[Line]] = []
    for ln in sorted(lines, key=lambda l: (l.y, l.x0)):
        if cur:
            head, last = cur[0][0], cur[-1][-1]
            if _is_row(ln) and _same_columns(ln, head) and ln.y - last.y <= ROW_GAP * head.size:
                cur.append([ln])
                continue
            if _wrap_column(ln, head) is not None and ln.y - last.y <= WRAP_GAP * head.size:
                cur[-1].append(ln)
                continue
            groups.append(cur)
            cur = []
        if _is_row(ln):
            cur = [[ln]]
    if cur:
        groups.append(cur)
    grids, taken, out = [], set(), []
    for rows in groups:
        if len(rows) < MIN_ROWS:
            continue
        g = _grid(rows)
        gi, head, n = first + len(grids), rows[0][0], len(rows[0][0].cols)
        grids.append(g)
        for i, row in enumerate(rows):
            for k, piece in enumerate(_pieces(row[0])):
                out.append(replace(piece, cell=(gi, i * n + k)))
            for ln in row[1:]:
                out.append(replace(ln, cell=(gi, i * n + _wrap_column(ln, head))))
            taken.update(id(ln) for ln in row)
    out += [ln for ln in lines if id(ln) not in taken]
    return grids, sorted(out, key=lambda l: (l.y, l.x0))
