"""The layout pipeline: merged items -> blocks per section -> planned breaks -> placed pages."""
from __future__ import annotations

from collections import Counter

from ..diff.changes import Comparison
from ..diff.compare import compare
from ..model import Document, Section
from .blocks import Ctx, ParaBlock, para_block
from .fonts import default_resolver
from .lines import Line, Run
from .merged import Item, merged_items
from .pages import CellBox, FontRef, GlyphRun, Layout, Page, PlacedLine, TableRowBox
from .pieces import LayoutOptions, visible
from .planner import BlockSpec, Plan, plan_breaks
from .tables import MIN_CELL_W, PAD_X, PAD_Y, TableRowBlock, table_blocks, table_runs


def build_blocks(items: list[Item], ctx: Ctx) -> list:
    out: list = []
    ranges = table_runs(items, ctx.cmp)
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


def _spec(b) -> BlockSpec:
    return BlockSpec(b.line_heights, b.space_before, b.space_after, b.keep_next, b.keep_lines, b.page_break_before)


def _new_page(pages: list[Page], sec: Section, section_idx: int) -> Page:
    pg = Page(len(pages) + 1, sec.page_w_pt, sec.page_h_pt, sec.margin_left_pt, sec.margin_top_pt,
              sec.margin_right_pt, sec.margin_bottom_pt, section_idx)
    pages.append(pg)
    return pg


def _glyph(r: Run, x: float, ctx: Ctx) -> GlyphRun:
    ctx.faces.setdefault(r.face.key, r.face)
    p = r.piece
    return GlyphRun(r.text, x, r.w, r.face.key, r.size, p.bold, p.italic, p.underline, p.color, p.mode, p.fmt, p.cid)


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
        cx += r.w + (extra if r.is_space else 0.0)
    marker: list[GlyphRun] = []
    if first and blk.marker:
        mx = base_x + blk.marker_x
        for r in blk.marker:
            marker.append(_glyph(r, mx, ctx))
            mx += r.w
    return PlacedLine(x, y, line.height, y + line.ascent, runs, marker, blk.changed,
                      [blk.cid] if (first and blk.cid is not None) else [], blk.row_index)


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
    page.table_rows.append(TableRowBox(x, y, blk.w, blk.height, boxes, blk.changed))


def _place(blocks: list, plan: Plan, sec: Section, section_idx: int, pages: list[Page], ctx: Ctx):
    brk = Counter((b.block, b.line) for b in plan.breaks)
    ml, mt = sec.margin_left_pt, sec.margin_top_pt
    bottom = sec.page_h_pt - sec.margin_bottom_pt
    # Pages are created lazily: a planned break before the very first block (a page-tall space
    # before, say) must not leave a blank leading page behind.
    st = {"page": None, "y": mt, "top": True}

    def page() -> Page:
        if st["page"] is None:
            st["page"] = _new_page(pages, sec, section_idx)
        return st["page"]

    def new_page():
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
            if st["y"] + blk.height > bottom + 1e-6 and not st["top"]:
                new_page()
            _place_row(blk, page(), ml + blk.x, st["y"], ctx)
            st["y"] += blk.height
            st["top"] = False
        else:
            for li, line in enumerate(blk.lines):
                if li > 0:
                    new_pages(brk[(bi, li)])
                if st["y"] + line.height > bottom + 1e-6 and not st["top"]:
                    new_page()          # safety net; the planner should have broken earlier
                page().lines.append(place_line(blk, li, line, ml, st["y"], ctx.content_w, ctx))
                st["y"] += line.height
                st["top"] = False
        st["y"] += blk.space_after


def layout(cmp: Comparison, opts: LayoutOptions | None = None) -> Layout:
    opts = opts or LayoutOptions()
    if cmp.b_doc is None or cmp.a_doc is None:
        raise ValueError("layout needs a Comparison from compare(a, b) (documents attached)")
    fonts = opts.fonts or default_resolver()
    doc = cmp.b_doc
    sections = doc.sections or [Section()]
    items = merged_items(cmp)
    pages: list[Page] = []
    faces: dict = {}
    for leader, group in _section_groups(items, sections):
        sec = sections[min(leader, len(sections) - 1)]
        ctx = Ctx(cmp, opts, fonts, sec.page_w_pt - sec.margin_left_pt - sec.margin_right_pt,
                  sec.page_h_pt - sec.margin_top_pt - sec.margin_bottom_pt,
                  doc.default_font, doc.default_size_pt, doc.default_tab_pt, faces)
        blocks = build_blocks(group, ctx)
        if not blocks:
            continue
        avail = ctx.avail_h
        plan = plan_breaks([_spec(b) for b in blocks], lambda p, a=avail: a)
        _place(blocks, plan, sec, leader, pages, ctx)
    if not pages:
        _new_page(pages, sections[0], 0)
    refs = {k: FontRef(f.path, f.font_number, f.family, f.bold, f.italic, f.synthetic) for k, f in faces.items()}
    return Layout(pages, refs, opts)


def layout_document(doc: Document, opts: LayoutOptions | None = None) -> Layout:
    return layout(compare(doc, doc), opts)
