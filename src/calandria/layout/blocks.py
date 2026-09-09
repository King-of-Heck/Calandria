"""Paragraph blocks: indents, list markers with tab stops, contextual spacing, line breaking.

Geometry (all relative to the container's left edge): the body starts at the left indent `x`;
the first line starts at `x + first_dx` (a hanging indent makes it negative, a first-line indent
positive). A list marker sits at the first-line position (its own alignment, w:lvlJc, may hang it
left of that point) and the text of the first line begins at the next tab stop after the marker:
the left indent when the marker ends before it, else the next default stop (Word), or one space
/ nothing for the other suffixes. A renumbered item carries both markers (old struck, new
inserted); an item that lost its numbering leads with the struck old marker inline.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..diff.changes import Comparison
from .lines import Line, Run, Spacing, break_lines, measure
from .merged import Item
from .pieces import LayoutOptions, Piece, row_pieces

MIN_LINE_PT = 40.0    # never wrap into a column narrower than this


@dataclass
class Ctx:
    cmp: Comparison
    opts: LayoutOptions
    fonts: object
    content_w: float           # page width minus left and right margins
    avail_h: float             # page height minus top and bottom margins
    default_font: str | None
    default_size: float
    default_tab: float
    faces: dict = field(default_factory=dict)   # face key -> face object, filled by the placer


@dataclass
class ParaBlock:
    lines: list[Line]
    x: float
    first_dx: float
    align: str                 # left | center | right | justify
    marker: list[Run]
    marker_x: float
    space_before: float
    space_after: float
    keep_next: bool
    keep_lines: bool
    page_break_before: bool
    section: int
    changed: bool
    cid: int | None
    row_index: int | None

    @property
    def line_heights(self) -> list[float]:
        return [ln.height for ln in self.lines]

    @property
    def height(self) -> float:
        return sum(ln.height for ln in self.lines)


def next_tab_stop(x: float, tab: float) -> float:
    return (math.floor(x / tab + 1e-9) + 1) * tab


def _base_style(pieces: list[Piece], ctx: Ctx):
    p = next((p for p in pieces if p.text.strip()), pieces[0] if pieces else None)
    if p is None:
        return ctx.default_font, ctx.default_size, False, False
    return p.font or ctx.default_font, p.size or ctx.default_size, p.bold, p.italic


def para_block(item: Item, prev: Item | None, nxt: Item | None, ctx: Ctx, avail_w: float | None = None) -> ParaBlock:
    para, row, props = item.para, item.row, item.para.props
    pieces = row_pieces(ctx.cmp, row, ctx.opts) if row is not None else []
    content_w = ctx.content_w if avail_w is None else avail_w
    fonts = ctx.fonts
    font, size, bold, italic = _base_style(pieces, ctx)
    cid = row.cid if row is not None else None
    renumbered = row is not None and row.num_changed and bool(row.old_marker)

    x = props.ind_left_pt
    first_x = x - props.ind_hanging_pt + props.ind_first_line_pt
    marker: list[Run] = []
    marker_x = first_x
    if para.num is not None:
        mk: list[Piece] = []
        if renumbered:
            mk.append(Piece(row.old_marker, "del", bold, italic, font=font, size=size, cid=cid))
            mk.append(Piece(" ", "eq", bold, italic, font=font, size=size, cid=cid))
        mk.append(Piece(para.num.marker, "ins" if renumbered else "eq", bold, italic, font=font, size=size, cid=cid))
        marker = measure(mk, fonts, ctx.default_font, ctx.default_size)
        mw = sum(r.w for r in marker)
        if para.num.jc == "right":
            marker_x = first_x - mw
        elif para.num.jc == "center":
            marker_x = first_x - mw / 2
        end = marker_x + mw
        if para.num.suff == "space":
            text_x = end + fonts.face(font, bold, italic).width(" ", size)
        elif para.num.suff == "nothing":
            text_x = end
        else:
            # No default tab stops (w:defaultTabStop 0): there is nothing to advance to, so the
            # text starts where the marker ends.
            text_x = (x if end <= x + 1e-9 else
                      next_tab_stop(end, ctx.default_tab) if ctx.default_tab > 0 else max(end, x))
        first_dx = text_x - x
    else:
        first_dx = first_x - x
        if renumbered:
            pieces = [Piece(row.old_marker + " ", "del", bold, italic, font=font, size=size, cid=cid)] + pieces

    runs = measure(pieces, fonts, ctx.default_font, ctx.default_size)
    spacing = Spacing(props.line_rule, props.line_spacing, props.line_exact_pt)
    lines = break_lines(runs, max(MIN_LINE_PT, content_w - x - first_dx), max(MIN_LINE_PT, content_w - x),
                        spacing, fonts.face(font, bold, italic), size)

    sb = props.space_before_pt or 0.0
    sa = props.space_after_pt or 0.0
    if props.contextual_spacing:
        if prev is not None and prev.para.props.style_id == props.style_id:
            sb = 0.0
        if nxt is not None and nxt.para.props.style_id == props.style_id:
            sa = 0.0
    changed = row is not None and (row.type != "equal" or (row.fmt_changed and ctx.opts.show_formatting)
                                   or row.num_changed)
    align = "justify" if props.align in ("justify", "distribute") else props.align
    return ParaBlock(lines, x, first_dx, align, marker, marker_x, sb, sa, props.keep_next, props.keep_lines,
                     props.page_break_before, item.section, changed, cid, item.row_index)
