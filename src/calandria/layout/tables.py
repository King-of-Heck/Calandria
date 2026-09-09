"""Table rows as atomic layout blocks.

A table is a run of consecutive merged items carrying a table location, grouped into visual rows
by (side, table index, row index) in item order -- so a deleted row from the original sits where
it stood among the revised rows. Column geometry comes from the revised-side table (the original
side only when the whole table was deleted): grid widths, scaled down when wider than the content
width, equal columns when there is no grid; a cell's x/width follow the model row's grid spans.
Row height is the tallest cell (Word's default cell margins: 5.4 pt left/right, none top/bottom),
raised to trHeight for atLeast, fixed for exact. Rows never split across pages; a row taller than
the page degrades to stacked paragraphs so line-level breaking applies (never off-page).
Equal rows stay in the table under hide-unchanged; hidden inserted/deleted rows are dropped.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..diff.units import table_by_ti
from .blocks import Ctx, ParaBlock, para_block
from .merged import Item
from .pieces import visible

PAD_X = 5.4        # Word default cell margins: 108 twips left and right
PAD_Y = 0.0        # none top/bottom
MIN_CELL_W = 20.0


@dataclass
class CellLayout:
    x: float
    w: float
    paras: list[ParaBlock]
    v_merge_continue: bool

    @property
    def height(self) -> float:
        return sum(p.space_before + p.height + p.space_after for p in self.paras)


@dataclass
class TableRowBlock:
    cells: list[CellLayout]
    x: float
    w: float
    height: float
    section: int
    changed: bool
    cids: list[int]
    space_before: float = 0.0
    space_after: float = 0.0
    keep_next: bool = False
    keep_lines: bool = False
    page_break_before: bool = False

    @property
    def line_heights(self) -> list[float]:
        return [self.height]


def table_runs(items: list[Item]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    i, n = 0, len(items)
    while i < n:
        if items[i].loc is None:
            i += 1
            continue
        j, seen = i, {}
        while j < n and items[j].loc is not None:
            side, ti = items[j].side, items[j].loc.ti
            if seen.get(side, ti) != ti:
                break
            seen[side] = ti
            j += 1
        out.append((i, j))
        i = j
    return out


def table_blocks(group: list[Item], ctx: Ctx) -> list:
    docs = {"a": ctx.cmp.a_doc, "b": ctx.cmp.b_doc}
    lead = next((it for it in group if it.side == "b"), group[0])
    table = table_by_ti(docs[lead.side], lead.loc.ti)
    cols = max(1, lead.loc.cols)
    tx = table.ind_pt
    avail_w = max(MIN_CELL_W, ctx.content_w - tx)
    if len(table.grid_pt) == cols and sum(table.grid_pt) > 0:
        grid = list(table.grid_pt)
    else:
        grid = [avail_w / cols] * cols
    total = sum(grid)
    if total > avail_w:
        grid = [g * avail_w / total for g in grid]
    col_x = [0.0]
    for g in grid:
        col_x.append(col_x[-1] + g)

    row_groups: list[tuple[tuple, list[Item]]] = []
    for it in group:
        if it.row is not None and not (visible(it.row, ctx.opts) or it.row.type == "equal"):
            continue
        k = (it.side, it.loc.ti, it.loc.ri)
        if not row_groups or row_groups[-1][0] != k:
            row_groups.append((k, []))
        row_groups[-1][1].append(it)

    out: list = []
    for gi, (k, its) in enumerate(row_groups):
        side, ti, ri = k
        mrow = table_by_ti(docs[side], ti).rows[ri]
        by_ci: dict[int, list[Item]] = {}
        for it in its:
            by_ci.setdefault(it.loc.ci, []).append(it)
        cells: list[CellLayout] = []
        gc = 0
        for ci, cell in enumerate(mrow.cells):
            span = max(1, cell.grid_span)
            c0, c1 = min(gc, cols - 1), min(gc + span, cols)
            cx, cw = col_x[c0], max(0.0, col_x[c1] - col_x[c0])
            gc += span
            cell_items = by_ci.get(ci, [])
            paras = [para_block(it, cell_items[j - 1] if j else None,
                                cell_items[j + 1] if j + 1 < len(cell_items) else None,
                                ctx, avail_w=max(MIN_CELL_W, cw - 2 * PAD_X))
                     for j, it in enumerate(cell_items)]
            cells.append(CellLayout(cx, cw, paras, cell.v_merge == "continue"))
        h = max((c.height for c in cells), default=0.0) + 2 * PAD_Y
        if mrow.height_rule == "exact" and mrow.height_pt:
            h = mrow.height_pt
        elif mrow.height_pt:
            h = max(h, mrow.height_pt)
        paras_all = [p for c in cells for p in c.paras]
        changed = any(p.changed for p in paras_all)
        cids = [p.cid for p in paras_all if p.cid is not None]
        pbb = gi == 0 and bool(its[0].para.props.page_break_before)
        if h > ctx.avail_h - 12:
            # Page-tall: an unsplittable row cannot render; degrade to stacked paragraphs.
            for n, it in enumerate(its):
                pb = para_block(it, None, None, ctx, avail_w=avail_w)
                pb.x += tx
                pb.space_before, pb.space_after = 0.0, 2.0
                pb.page_break_before = pbb and n == 0
                out.append(pb)
            continue
        out.append(TableRowBlock(cells, tx, col_x[-1], h, its[0].section, changed, cids, page_break_before=pbb))
    return out
