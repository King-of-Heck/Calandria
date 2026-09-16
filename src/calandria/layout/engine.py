"""The layout pipeline: merged items -> blocks per section -> planned breaks -> placed pages."""
from __future__ import annotations

from collections import Counter

from ..diff.changes import Comparison
from ..diff.compare import compare
from ..model import Document, Section
from .blocks import Ctx, ParaBlock, collapse_spacing, note_height, para_block, sep_block
from .fonts import default_resolver
from .lines import Line, Run
from .merged import Item, merged_items
from .pages import CellBox, FontRef, GlyphRun, Layout, Page, PlacedLine, Rule, TableRowBox
from .pieces import LayoutOptions, visible
from .planner import NOTE_SEP_PT, BlockSpec, Plan, plan_breaks
from .sides import side_items, side_options
from .tables import (MIN_CELL_W, PAD_X, PAD_Y, TableRowBlock, ctx_maps, table_blocks, table_maps,
                     table_runs)


def build_blocks(items: list[Item], ctx: Ctx) -> list:
    """The blocks of one section group in placement order: the body (paragraphs and table rows),
    then, under a separator, the endnotes. Footnotes are built here too but kept aside in
    ctx.notes by note key; the placer floats them to the foot of the page that references them.
    Every block's line_notes says which footnotes each of its lines brings to the page."""
    body = [it for it in items if it.stream == "body"]
    tail: list = []
    for stream, key, its in _note_groups(items):
        blocks = [para_block(it, its[j - 1] if j else None, its[j + 1] if j + 1 < len(its) else None, ctx)
                  for j, it in enumerate(its) if (ctx.opts.show_equal if it.row is None else visible(it.row, ctx.opts))]
        if stream == "footnote":
            ctx.notes[key] = collapse_spacing(blocks, ctx)
        else:
            tail.extend(blocks)
    out = _body_blocks(body, ctx)
    if tail:
        out.append(sep_block(tail[0].section, "endnote"))
        out.extend(tail)
    collapse_spacing(out, ctx)
    _annotate_notes(out, ctx)
    return out


def _body_blocks(items: list[Item], ctx: Ctx) -> list:
    out: list = []
    ranges = table_runs(items, ctx_maps(ctx))
    ri, i, n = 0, 0, len(items)
    while i < n:
        if ri < len(ranges) and ranges[ri][0] == i:
            s, e = ranges[ri]
            ri += 1
            out.extend(table_blocks(items[s:e], ctx))
            i = e
            continue
        it = items[i]
        show = ctx.opts.show_equal if it.row is None else visible(it.row, ctx.opts)
        if show:
            out.append(para_block(it, items[i - 1] if i else None, items[i + 1] if i + 1 < n else None, ctx))
        i += 1
    return out


def _note_groups(items: list[Item]) -> list[tuple[str, int, list[Item]]]:
    """(stream, key, items) per note: consecutive items of one note; the key is the index of the
    note's first comparison row (what its reference marks carry). A note of empty paragraphs
    only has no row and is dropped."""
    out: list[tuple[str, int, list[Item]]] = []
    run: list[Item] = []

    def flush():
        if run:
            key = next((it.row_index for it in run if it.row_index is not None), None)
            if key is not None:
                out.append((run[0].stream, key, list(run)))
            run.clear()

    for it in items:
        if it.stream == "body":
            flush()
            continue
        if it.stream in ("header", "footer"):
            # drawn on the page's own header/footer area, not in the body flow (a later stream);
            # dropped here so it never rides along as a stray endnote block.
            flush()
            continue
        if run and (run[-1].stream, run[-1].note, run[-1].side) != (it.stream, it.note, it.side):
            flush()
        run.append(it)
    flush()
    return out


def _line_keys(runs: list[Run], seen: set, ctx: Ctx) -> list[int]:
    keys: list[int] = []
    for r in runs:
        k = r.piece.note
        if k is not None and k in ctx.notes and k not in seen:
            seen.add(k)
            keys.append(k)
    return keys


def _annotate_notes(blocks: list, ctx: Ctx) -> None:
    """Fill line_notes: the footnote keys each line (each table row) brings to its page, first
    reference only."""
    seen: set = set()
    for blk in blocks:
        if isinstance(blk, TableRowBlock):
            keys: list[int] = []
            for c in blk.cells:
                for pb in c.paras:
                    for line in pb.lines:
                        keys += _line_keys(line.runs, seen, ctx)
            blk.line_notes = [keys]
        else:
            blk.line_notes = [_line_keys(line.runs, seen, ctx) for line in blk.lines]


def _section_groups(items: list[Item], sections: list[Section]) -> list[tuple[int, list[Item]]]:
    """Consecutive items by section. A section whose predecessor closed with a continuous break
    flows on in the previous group (same page, same geometry)."""
    groups: list[tuple[int, list[Item]]] = []
    for it in items:
        if groups and groups[-1][1][-1].section == it.section:
            groups[-1][1].append(it)
            continue
        prev = sections[min(it.section - 1, len(sections) - 1)] if it.section > 0 else None
        if groups and prev is not None and prev.type in ("continuous", "nextColumn"):
            groups[-1][1].append(it)
            continue
        groups.append((it.section, [it]))
    return groups


BLACK = "000000"        # a border whose colour is auto


def _spec(b, ctx: Ctx) -> BlockSpec:
    notes = None
    if b.line_notes and any(b.line_notes):
        notes = [sum(note_height(ctx.notes[k]) for k in keys) for keys in b.line_notes]
    return BlockSpec(b.line_heights, b.space_before, b.space_after, b.keep_next, b.keep_lines, b.page_break_before,
                     notes)


SEP_LEN = 144.0        # the note separator rule: 2 inches from the left margin (Word)
SEP_WIDTH = 0.75


def _new_page(pages: list[Page], sec: Section, section_idx: int) -> Page:
    pg = Page(len(pages) + 1, sec.page_w_pt, sec.page_h_pt, sec.margin_left_pt, sec.margin_top_pt,
              sec.margin_right_pt, sec.margin_bottom_pt, section_idx)
    pages.append(pg)
    return pg


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


def _place_row(blk: TableRowBlock, page: Page, x: float, y: float, ctx: Ctx):
    boxes: list[CellBox] = []
    for c in blk.cells:
        boxes.append(CellBox(x + c.x, y, c.w, blk.height, c.v_merge_continue))
        cy = y + PAD_Y
        for pb in c.paras:
            cy += pb.space_before
            for li, line in enumerate(pb.lines):
                page.lines.append(place_line(pb, li, line, x + c.x + PAD_X, cy, max(MIN_CELL_W, c.w - 2 * PAD_X), ctx))
                cy += line.height
            cy += pb.space_after
    page.table_rows.append(TableRowBox(x, y, blk.w, blk.height, boxes, blk.changed, list(blk.cids)))


def _place(blocks: list, plan: Plan, sec: Section, section_idx: int, pages: list[Page], ctx: Ctx):
    brk = Counter((b.block, b.line) for b in plan.breaks)
    ml, mt = sec.margin_left_pt, sec.margin_top_pt
    bottom = sec.page_h_pt - sec.margin_bottom_pt
    # Pages are created lazily: a planned break before the very first block (a page-tall space
    # before, say) must not leave a blank leading page behind.
    st = {"page": None, "y": mt, "top": True}

    def page() -> Page:
        # Lazy materialisation (see above) means a planned break that lands before any content is
        # placed never creates a page here, so the placer's running page index can end up one
        # behind the planner's own count for this section. Harmless while avail_of is a constant
        # (every page the planner assumed is the same height as every page this creates), but it
        # will need reconciling before a per-page avail_of lands (footnote reserve, header/footer
        # chrome) and the two indices must agree on which page a given break actually falls on.
        if st["page"] is None:
            st["page"] = _new_page(pages, sec, section_idx)
        return st["page"]

    pending: list[int] = []          # footnote keys to set at the foot of the current page

    def reserve() -> float:
        return NOTE_SEP_PT + sum(note_height(ctx.notes[k]) for k in pending) if pending else 0.0

    def brings(keys: list[int]) -> float:
        """The foot-of-page height a line adds by referencing `keys` (the separator when the page
        has no notes yet)."""
        if not keys:
            return 0.0
        return sum(note_height(ctx.notes[k]) for k in keys) + (0.0 if pending else NOTE_SEP_PT)

    def close_page():
        """Set the page's footnotes bottom-up: the separator, then the notes in reference order."""
        if not pending:
            return
        pg = page()
        y = bottom - reserve()
        sep = sep_block(section_idx, "footnote")
        pg.lines.append(place_line(sep, 0, sep.lines[0], ml, y, ctx.content_w, ctx))
        y += NOTE_SEP_PT
        for k in pending:
            for pb in ctx.notes[k]:
                y += pb.space_before
                for li, line in enumerate(pb.lines):
                    pg.lines.append(place_line(pb, li, line, ml, y, ctx.content_w, ctx))
                    y += line.height
                y += pb.space_after
        pending.clear()

    def new_page():
        close_page()
        st["page"], st["y"], st["top"] = None, mt, True

    def new_pages(n: int):
        # The planner can break more than once at the same point; each break starts its own page,
        # so every break after the first leaves a blank page behind (materialised here, since a
        # page nothing is placed on is otherwise never created).
        for k in range(n):
            if k:
                page()
            new_page()

    for bi, blk in enumerate(blocks):
        new_pages(brk[(bi, 0)])
        if plan.before[bi]:
            st["y"] += blk.space_before
        if isinstance(blk, TableRowBlock):
            keys = blk.line_notes[0] if blk.line_notes else []
            if st["y"] + blk.height + brings(keys) > bottom - reserve() + 1e-6 and not st["top"]:
                new_page()
            _place_row(blk, page(), ml + blk.x, st["y"], ctx)
            pending.extend(keys)
            st["y"] += blk.height
            st["top"] = False
        else:
            for li, line in enumerate(blk.lines):
                if li > 0:
                    new_pages(brk[(bi, li)])
                keys = blk.line_notes[li] if blk.line_notes else []
                if st["y"] + line.height + brings(keys) > bottom - reserve() + 1e-6 and not st["top"]:
                    new_page()          # safety net; the planner should have broken earlier
                page().lines.append(place_line(blk, li, line, ml, st["y"], ctx.content_w, ctx))
                pending.extend(keys)
                st["y"] += line.height
                st["top"] = False
        st["y"] += blk.space_after
    close_page()


def layout(cmp: Comparison, opts: LayoutOptions | None = None) -> Layout:
    opts = opts or LayoutOptions()
    if cmp.b_doc is None or cmp.a_doc is None:
        raise ValueError("layout needs a Comparison from compare(a, b) (documents attached)")
    run_opts = side_options(opts)               # raises on an unknown side
    fonts = opts.fonts or default_resolver()
    doc = cmp.b_doc
    sections = doc.sections or [Section()]
    items = side_items(merged_items(cmp), cmp, opts.side)
    pages: list[Page] = []
    faces: dict = {}
    maps = table_maps(cmp)      # one correspondence build for the whole layout
    for leader, group in _section_groups(items, sections):
        sec = sections[min(leader, len(sections) - 1)]
        ctx = Ctx(cmp, run_opts, fonts, sec.page_w_pt - sec.margin_left_pt - sec.margin_right_pt,
                  sec.page_h_pt - sec.margin_top_pt - sec.margin_bottom_pt,
                  doc.default_font, doc.default_size_pt, doc.default_tab_pt, faces, maps,
                  html_spacing=doc.html_spacing)
        blocks = build_blocks(group, ctx)
        if not blocks:
            continue
        avail = ctx.avail_h
        plan = plan_breaks([_spec(b, ctx) for b in blocks], lambda p, a=avail: a)
        _place(blocks, plan, sec, leader, pages, ctx)
    if not pages:
        # Nothing was placed: the one empty page takes the body (last) section's geometry, which is
        # the page a reader of an empty document sees in Word.
        _new_page(pages, sections[-1], len(sections) - 1)
    refs = {k: FontRef(f.path, f.font_number, f.family, f.bold, f.italic, f.synthetic, getattr(f, "symbol", False))
            for k, f in faces.items()}
    # the options as requested (opts.side names the side); the narrowed run options are not stored
    return Layout(pages, refs, opts)


def layout_document(doc: Document, opts: LayoutOptions | None = None) -> Layout:
    return layout(compare(doc, doc), opts)
