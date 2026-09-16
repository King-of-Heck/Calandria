"""Paragraph blocks: indents, list markers with tab stops, contextual spacing, line breaking.

Geometry (all relative to the container's left edge): the body starts at the left indent `x`;
the first line starts at `x + first_dx` (a hanging indent makes it negative, a first-line indent
positive). A list marker sits at the first-line position (its own alignment, w:lvlJc, may hang it
left of that point) and the text of the first line begins at the next tab stop after the marker:
the left indent when the marker ends before it, else the next default stop (Word), or one space
/ nothing for the other suffixes. The right indent narrows both the wrap width and
the alignment box. A renumbered item carries both markers (old struck, new
inserted); an item that lost its numbering leads with the struck old marker inline.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from ..diff.changes import Comparison
from .lines import Line, Run, Spacing, break_lines, measure, next_tab_stop  # noqa: F401 (re-exported)
from .merged import Item
from .pieces import LayoutOptions, Piece, row_pieces
from .planner import NOTE_SEP_PT

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
    maps: tuple | None = None  # table correspondence maps, built once per layout (see tables.table_maps)
    notes: dict = field(default_factory=dict)   # footnote key (first row index) -> its ParaBlocks (engine.build_blocks)
    html_spacing: bool = True  # Document.html_spacing: the larger of space after / before between paragraphs
    hf_items: dict = field(default_factory=dict)  # (stream, part) -> header/footer Items (chrome.hf_groups)
    parts: dict = field(default_factory=dict)     # (stream, part) -> its ParaBlocks at this width (chrome.part_blocks)


@dataclass
class ParaBlock:
    lines: list[Line]
    x: float
    first_dx: float
    right: float               # right indent: the wrap and alignment box end this far short of the container
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
    cids: list[int]                # passage numbers in the block, reading order
    cid_starts: list[list[int]]    # per line: the numbers whose first glyph run is on it (gutter)
    row_index: int | None
    borders: tuple = (None, None, None, None)   # (top, bottom, left, right) Border | None, as resolved
    draw_top: bool = False         # the top border is drawn (and its height added to the first line);
    draw_bottom: bool = False      # False when joined to the paragraph before / after (see _joins)
    stream: str = "body"           # body | footnote | endnote
    note_sep: bool = False         # the note separator: one empty line carrying the rule
    line_notes: list | None = None # per line: the footnote keys first referenced on it (engine)

    @property
    def line_heights(self) -> list[float]:
        return [ln.height for ln in self.lines]

    @property
    def height(self) -> float:
        return sum(ln.height for ln in self.lines)


def _cid_starts(marker: list[Run], lines: list[Line]) -> tuple[list[int], list[list[int]]]:
    """(all passage numbers in reading order, per-line first appearances): the marker's number on
    the first line, then each text passage on the line where it begins (spec 14.4)."""
    seen: list[int] = []
    starts: list[list[int]] = []
    for li, ln in enumerate(lines):
        here: list[int] = []
        for r in (marker if li == 0 else []) + ln.runs:
            c = r.piece.cid
            if c is not None and c not in seen:
                seen.append(c)
                here.append(c)
        starts.append(here)
    if not lines:
        seen = [r.piece.cid for r in marker if r.piece.cid is not None]
    return seen, starts


def _base_style(pieces: list[Piece], ctx: Ctx, props=None):
    """(font, size, bold, italic) the paragraph's marker and its empty line take: the first text
    piece's, else the paragraph mark's (Word sizes an empty paragraph by its mark, which follows
    the paragraph style), else the document defaults."""
    p = next((p for p in pieces if p.text.strip()), pieces[0] if pieces else None)
    if p is None:
        if props is not None and (props.mark_font or props.mark_size_pt):
            return props.mark_font or ctx.default_font, props.mark_size_pt or ctx.default_size, False, False
        return ctx.default_font, ctx.default_size, False, False
    return p.font or ctx.default_font, p.size or ctx.default_size, p.bold, p.italic


def _borders(props) -> tuple:
    return (props.border_top, props.border_bottom, props.border_left, props.border_right)


def _joins(a, b) -> bool:
    """Word draws adjacent paragraphs with the same borders and the same left and right indents as
    one box: the border between them is not drawn (nor is its height taken)."""
    return (b is not None and _borders(a) == _borders(b.para.props)
            and a.ind_left_pt == b.para.props.ind_left_pt and a.ind_right_pt == b.para.props.ind_right_pt)


def _note_lead(item: Item, row, pieces: list[Piece], ctx: Ctx) -> list[Piece]:
    """The number that opens a note's first paragraph (Word's w:footnoteRef): the note's own
    number, raised, in the formatting of the note's first text, then a space; in the mode of the
    note as a whole."""
    doc = ctx.cmp.a_doc if item.side == "a" else ctx.cmp.b_doc
    number = str(doc.note_numbers.get(item.note, "?")) if doc is not None else "?"
    mode = {"inserted": "ins", "deleted": "del"}.get(row.type, "eq")
    p0 = next((p for p in pieces if p.text.strip()), None)
    if p0 is None:
        return [Piece(number, mode, rise=True), Piece(" ", mode)]
    return [Piece(number, mode, p0.bold, p0.italic, font=p0.font, size=p0.size, color=p0.color, rise=True),
            Piece(" ", mode, p0.bold, p0.italic, font=p0.font, size=p0.size, color=p0.color)]


def para_block(item: Item, prev: Item | None, nxt: Item | None, ctx: Ctx, avail_w: float | None = None,
               fields: dict[str, str] | None = None) -> ParaBlock:
    para, row, props = item.para, item.row, item.para.props
    pieces = row_pieces(ctx.cmp, row, ctx.opts) if row is not None else []
    if row is None:
        # an empty paragraph holding an inline image keeps the image's box (the logo headers)
        pieces = [Piece("", "eq", image_w=r.props.image_w_pt or 0.0, image_h=r.props.image_h_pt or 0.0)
                  for r in para.runs if r.props.image_w_pt]
    if row is not None and item.note is not None and (prev is None or prev.note != item.note):
        pieces = _note_lead(item, row, pieces, ctx) + pieces
    if fields:
        # A field's text before anything is measured, so the tab stops, leaders, alignment and the
        # line breaking all see the page number Word shows (chrome.part_blocks, one build per page).
        pieces = [replace(p, text=fields[p.field]) if p.field in fields else p for p in pieces]
    content_w = ctx.content_w if avail_w is None else avail_w
    fonts = ctx.fonts
    font, size, bold, italic = _base_style(pieces, ctx, props)
    num_cid = row.num_cid if row is not None else None
    renumbered = row is not None and row.num_changed and bool(row.old_marker) and ctx.opts.side == "blackline"

    x = props.ind_left_pt
    first_x = x - props.ind_hanging_pt + props.ind_first_line_pt
    marker: list[Run] = []
    marker_x = first_x
    if para.num is not None:
        mk: list[Piece] = []
        if renumbered:
            mk.append(Piece(row.old_marker, "del", bold, italic, font=font, size=size, cid=num_cid))
            mk.append(Piece(" ", "eq", bold, italic, font=font, size=size, cid=num_cid))
        mk.append(Piece(para.num.marker, "ins" if renumbered else "eq", bold, italic, font=font, size=size, cid=num_cid))
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
            # The next stop after the marker: a custom stop of the paragraph (a level's "num" stop
            # included), the hanging indent when the marker ends before it, else the next default
            # stop. No default tab stops (w:defaultTabStop 0): there is nothing to advance to, so
            # the text starts where the marker ends.
            cands = [s.pos_pt for s in props.tabs if s.kind in ("left", "num") and s.pos_pt > end + 1e-9][:1]
            if end <= x + 1e-9:
                cands.append(x)
            if cands:
                text_x = min(cands)
            else:
                text_x = next_tab_stop(end, ctx.default_tab) if ctx.default_tab > 0 else max(end, x)
        first_dx = text_x - x
    else:
        first_dx = first_x - x
        if renumbered:
            pieces = [Piece(row.old_marker + " ", "del", bold, italic, font=font, size=size, cid=num_cid)] + pieces

    runs = measure(pieces, fonts, ctx.default_font, ctx.default_size)
    spacing = Spacing(props.line_rule, props.line_spacing, props.line_exact_pt)
    right = props.ind_right_pt
    lines = break_lines(runs, max(MIN_LINE_PT, content_w - x - first_dx - right),
                        max(MIN_LINE_PT, content_w - x - right),
                        spacing, fonts.face(font, bold, italic), size,
                        first_x=x + first_dx, x=x, stops=props.tabs, default_tab=ctx.default_tab)
    cids, starts = _cid_starts(marker, lines)

    # Paragraph borders: the line and the space between it and the text sit inside the paragraph,
    # so a top border adds to the first line (and pushes its baseline down) and a bottom border to
    # the last; the planner sees only line heights and needs no other word.
    borders = _borders(props)
    draw_top = borders[0] is not None and not _joins(props, prev)
    draw_bottom = borders[1] is not None and not _joins(props, nxt)
    if lines and draw_top:
        ext = borders[0].width_pt + borders[0].space_pt
        lines[0].height += ext
        lines[0].ascent += ext
    if lines and draw_bottom:
        lines[-1].height += borders[1].width_pt + borders[1].space_pt

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
    return ParaBlock(lines, x, first_dx, right, align, marker, marker_x, sb, sa, props.keep_next, props.keep_lines,
                     props.page_break_before and not props.section_page_break, item.section, changed, cids, starts,
                     item.row_index,
                     borders, draw_top, draw_bottom, item.stream)


def collapse_spacing(blocks: list, ctx: Ctx) -> list:
    """Word's HTML paragraph auto spacing (Document.html_spacing, the default): the gap between
    two consecutive blocks is the larger of the first's space after and the second's space
    before. The first's space after is kept as it is and the second's space before is reduced by
    it, so the planner's own rules (space before dropped at an automatic page top, space after
    kept) still see one value each. Returns `blocks`."""
    if ctx.html_spacing:
        for prev, b in zip(blocks, blocks[1:]):
            b.space_before = max(0.0, b.space_before - prev.space_after)
    return blocks


def sep_block(section: int, stream: str) -> ParaBlock:
    """The note separator (Word's short rule above the footnotes, or above the endnotes): one
    empty line of NOTE_SEP_PT with the rule drawn by the placer; kept with what follows."""
    return ParaBlock([Line([], 0.0, 0, NOTE_SEP_PT, NOTE_SEP_PT / 2)], 0.0, 0.0, 0.0, "left", [], 0.0, 0.0, 0.0,
                     True, False, False, section, False, [], [[]], None, stream=stream, note_sep=True)


def note_height(blocks: list[ParaBlock]) -> float:
    return sum(pb.space_before + pb.height + pb.space_after for pb in blocks)
