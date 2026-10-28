"""Turning one broken line of a block into a placed line of glyph runs.

Shared by the body placer (engine) and the header/footer placer (chrome), which is why it lives
on its own: both put lines on a page, only the box they put them in differs.
"""
from __future__ import annotations

from .blocks import Ctx, ParaBlock
from .lines import Line, Run
from .pages import GlyphRun, PlacedLine, Rule
from .planner import NOTE_SEP_PT

BLACK = "000000"        # a border whose colour is auto

SEP_LEN = 144.0        # the note separator rule: 2 inches from the left margin (Word)
SEP_WIDTH = 0.75


def _glyph(r: Run, x: float, ctx: Ctx) -> GlyphRun:
    ctx.faces.setdefault(r.face.key, r.face)
    p = r.piece
    return GlyphRun(r.text, x, r.w, r.face.key, r.size, p.bold, p.italic, p.underline, p.color, p.mode, p.fmt, p.cid,
                    r.rise, p.field)


def place_line(blk: ParaBlock, li: int, line: Line, base_x: float, y: float, container_w: float, ctx: Ctx) -> PlacedLine:
    first = li == 0
    x0 = base_x + blk.x + (blk.first_dx if first else 0.0)
    avail = container_w - blk.x - blk.right - (blk.first_dx if first else 0.0)
    last = li == len(blk.lines) - 1
    x, extra = x0, 0.0
    if blk.align == "center":
        x = x0 + max(0.0, (avail - line.width) / 2)
    elif blk.align == "right":
        x = x0 + max(0.0, avail - line.width)
    elif blk.align == "justify" and not last and line.gaps > 0:
        extra = max(0.0, (avail - line.width) / line.gaps)
    runs: list[GlyphRun] = []
    cx = x
    for r in line.runs:
        runs.append(_glyph(r, cx, ctx))
        if r.tab and r.leader and r.w > 0:
            # the leader: as many of its character as fit, ending at the stop (Word's dot leader)
            dw = r.face.width(r.leader, r.size)
            n = int(r.w / dw + 1e-6) if dw > 0 else 0
            if n:
                runs.append(_glyph(Run(r.leader * n, n * dw, r.piece, r.face, r.size), cx + r.w - n * dw, ctx))
        cx += r.w + (extra if r.is_space else 0.0)
    marker: list[GlyphRun] = []
    if first and blk.marker:
        mx = base_x + blk.marker_x
        for r in blk.marker:
            marker.append(_glyph(r, mx, ctx))
            mx += r.w
    rules = _rules(blk, first, last, base_x + blk.x, base_x + container_w - blk.right, y, line.height)
    if blk.note_sep:
        rules.append(Rule(base_x, y + NOTE_SEP_PT / 2, base_x + SEP_LEN, y + NOTE_SEP_PT / 2, SEP_WIDTH, BLACK))
    return PlacedLine(x, y, line.height, y + line.ascent, runs, marker, blk.changed,
                      list(blk.cid_starts[li]) if li < len(blk.cid_starts) else [], blk.row_index,
                      rules, blk.stream)


def _rules(blk: ParaBlock, first: bool, last: bool, x1: float, x2: float, y: float, h: float) -> list[Rule]:
    """The paragraph's border segments on one line: the top rule on the first line and the bottom
    on the last (each centred half its width inside the line's edge, spanning the indents), the
    left and right rules on every line over the line's height, `space` outside the text edge."""
    top, bottom, left, right = blk.borders
    out: list[Rule] = []
    if first and blk.draw_top:
        out.append(Rule(x1, y + top.width_pt / 2, x2, y + top.width_pt / 2, top.width_pt, top.color or BLACK))
    if left is not None:
        lx = x1 - left.space_pt - left.width_pt / 2
        out.append(Rule(lx, y, lx, y + h, left.width_pt, left.color or BLACK))
    if right is not None:
        rx = x2 + right.space_pt + right.width_pt / 2
        out.append(Rule(rx, y, rx, y + h, right.width_pt, right.color or BLACK))
    if last and blk.draw_bottom:
        yb = y + h - bottom.width_pt / 2
        out.append(Rule(x1, yb, x2, yb, bottom.width_pt, bottom.color or BLACK))
    return out
