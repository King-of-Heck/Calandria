"""The comment column: bubbles built at the column width, resolved to the page of their anchor, and
packed top-to-bottom so they do not overlap. A document with no comments reserves no column, so its
body geometry is unchanged. Overflow past the page bottom spills to the next page's column (a known
limit); a thread taller than a page is truncated (Task 5 draws the truncation)."""
from __future__ import annotations

from .blocks import Ctx
from .lines import Line, Spacing, break_lines, measure
from .pages import Bubble, GlyphRun, PlacedComment, PlacedLine
from .pieces import Piece

COLUMN_W = 150.0
COLUMN_GAP = 12.0
BUBBLE_PAD = 4.0
BUBBLE_MARGIN = 6.0        # vertical gap between packed bubbles


def reserved_width(cmp) -> float:
    return COLUMN_W + COLUMN_GAP if cmp.comments else 0.0


def _header(c) -> str:
    who = c.initials or c.author
    date = (c.date or "")[:10]        # ISO date, day precision
    head = f"{who} - {date}" if date else who
    return ("\u2713 " + head) if c.done else head


def _face(ctx: Ctx):
    return ctx.fonts.face(ctx.default_font, False, False)


def _lay_pieces(pieces: list[Piece], ctx: Ctx, inner: float) -> list[Line]:
    runs = measure(pieces, ctx.fonts, ctx.default_font, ctx.default_size)
    return break_lines(runs, inner, inner, Spacing(), _face(ctx), ctx.default_size)


def _placed_line(line: Line, ctx: Ctx, x: float, top: float) -> PlacedLine:
    runs: list[GlyphRun] = []
    cx = x
    for r in line.runs:
        ctx.faces.setdefault(r.face.key, r.face)
        p = r.piece
        runs.append(GlyphRun(r.text, cx, r.w, r.face.key, r.size, p.bold, p.italic, p.underline,
                             p.color, p.mode, p.fmt, p.cid, r.rise, p.field))
        cx += r.w
    return PlacedLine(x, top, line.height, top + line.ascent, runs, [], False, [], None, [], "comment")


def _stack(lines: list[Line], ctx: Ctx, start_y: float) -> list[PlacedLine]:
    """Lay the bubble's lines top-to-bottom from `start_y`, x at the bubble's inner left."""
    out: list[PlacedLine] = []
    y = start_y
    for line in lines:
        out.append(_placed_line(line, ctx, BUBBLE_PAD, y))
        y += line.height
    return out


def build_bubbles(cmp, ctx: Ctx, col_w: float) -> list:
    """One bubble per comment change: a bold header line, then the change's text laid out at the
    column's inner width (the same line breaking the body uses). Reuses ctx's document-wide fonts
    and defaults; the lines are display-only (stream "comment", never a diff stream)."""
    inner = col_w - 2 * BUBBLE_PAD
    out: list = []
    for c in cmp.comments:
        header = _header(c)
        lines = _lay_pieces([Piece(header, "eq", bold=True)], ctx, inner)
        seg_pieces = [Piece(s.t, s.m) for s in c.segments if s.t] or [Piece("", "eq")]
        lines += _lay_pieces(seg_pieces, ctx, inner)
        placed = _stack(lines, ctx, BUBBLE_PAD)
        height = 2 * BUBBLE_PAD + sum(line.height for line in lines)
        out.append((c, Bubble(c.cid, c.state, header, placed, c.depth, height)))
    return out


def _anchor_positions(layout, cmp) -> dict:
    """Anchor paragraph identity -> (page, baseline y, right end x) of the first body line that
    lays that paragraph out. Keyed by BOTH the a-side and b-side paragraph of each row (mirroring
    diff/comments.py::_body_order), so a removed comment -- whose anchor.para is the ORIGINAL-side
    Paragraph -- still resolves when that row survives as equal/changed (the common case)."""
    out: dict = {}
    for page in layout.pages:
        for ln in page.lines:
            if ln.stream != "body" or ln.row_index is None:
                continue
            if not 0 <= ln.row_index < len(cmp.rows):
                continue
            row = cmp.rows[ln.row_index]
            keys = []
            if row.ni is not None:
                keys.append(id(cmp.b_units[row.ni].para))
            if row.oi is not None:
                keys.append(id(cmp.a_units[row.oi].para))
            if not keys:
                continue
            pos = None
            for key in keys:
                if key not in out:
                    if pos is None:
                        anchor_x = max((g.x + g.w for g in ln.runs), default=ln.x)
                        pos = (page, ln.baseline, anchor_x)
                    out[key] = pos
    return out


def place_bubbles(layout, cmp, bubbles) -> None:
    """Resolve each bubble to the page + baseline of its anchor paragraph, then pack the bubbles of
    a page top-to-bottom (monotonic y, no overlap) and append the PlacedComments to page.comments.
    A comment with an unresolved anchor (no anchor paragraph, e.g. a threaded reply, or an anchor
    that isn't a body paragraph at all) inherits the most recently resolved position instead of
    falling back to page 0 -- comments arrive in reading order with replies right after their
    parent, so that position is the parent's."""
    if not layout.pages:
        return
    anchor_pos = _anchor_positions(layout, cmp)
    default = (layout.pages[0], layout.pages[0].margin_top, 0.0)
    by_page: dict = {}
    last_resolved = None
    for c, bubble in bubbles:
        para = c.anchor.para if c.anchor is not None else None
        resolved = anchor_pos.get(id(para)) if para is not None else None
        if resolved is not None:
            page, base_y, ax = resolved
            last_resolved = resolved
        elif last_resolved is not None:
            page, base_y, ax = last_resolved
        else:
            page, base_y, ax = default
        by_page.setdefault(page.number, []).append((bubble, base_y, ax, page))
    for _num, items in by_page.items():
        items.sort(key=lambda t: t[1])              # by anchor baseline
        page = items[0][3]
        col_x = page.w - page.margin_right - COLUMN_W
        y = page.margin_top
        for bubble, base_y, ax, _pg in items:
            y = max(y, base_y - bubble.height / 2)      # start near the anchor
            page.comments.append(PlacedComment(col_x, y, COLUMN_W, bubble, ax, base_y))
            y += bubble.height + BUBBLE_MARGIN
