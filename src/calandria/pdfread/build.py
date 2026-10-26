"""Paragraphs, ruled grids and notes -> the Document the rest of Calandria reads. The walk is over
ONE stream of body items in reading order, page after page, so a paragraph or a table that
continues over a page break comes out whole."""
from __future__ import annotations

from collections import Counter
from dataclasses import replace

from ..model import (Cell, Document, NoteRef, Paragraph, ParaProps, Row, Run, RunProps, Section, Table,
                     TabStop, collapse_ws)
from .fontname import split_font
from .grid import TOL, Grid, GridCell
from .paras import (EDGE, LEADER, MARKER, TOC_END, PdfPara, build_paragraphs, justified_document,
                    nothing_wraps, prevailing_pitch)
from .types import Line, PageLines

MIN_MARGIN = 0.03      # of the page width or height: a measured margin is never less than this
OUTLIERS = 200         # one line in this many may end past the right margin without moving it (a "(SEAL)"
                       # set out in a signature block ran 4.4 pt past a 198-page contract's margin)
# BREAK_ROOM: of the text column's height. Measured on Word's PDF of a 198-page contract (room above
# the footnotes), a page the text flowed off left at most 0.118 of its column empty (a heading kept
# with its paragraph); every page followed by a new title (schedule, appendix, form, the table of
# contents) left 0.138 or more, up to 0.83.
BREAK_ROOM = 0.13


def _half(v: float) -> float:
    return round(v * 2) / 2


def _body(pages: list[PageLines], skip: set) -> list[Line]:
    return [ln for pi, pg in enumerate(pages) for li, ln in enumerate(pg.lines)
            if ln.cell is None and (pi, li) not in skip]


def body_metrics(pages: list[PageLines], skip: set) -> tuple[float, float, float]:
    """(left edge, right edge, body font size) of the text column. The left edge is the leftmost
    x that a fair number of lines start at, so one outdented line does not move the margin; the right
    edge is where all but one line in OUTLIERS end, for the same reason. Both
    edges come from pages of the commonest size only: one landscape page's wider lines would
    otherwise set the right edge for the whole document."""
    all_lines = _body(pages, skip)
    if not all_lines:
        width = pages[0].width if pages else 612.0
        return 72.0, width - 72.0, 11.0
    shape, _n = Counter((pg.width, pg.height) for pg in pages).most_common(1)[0]
    lines = [ln for ln in all_lines if (pages[ln.page].width, pages[ln.page].height) == shape] or all_lines
    starts = Counter(_half(ln.x0) for ln in lines)
    floor = max(2, len(lines) // 50) if len(lines) >= 10 else 1
    common = [x for x, n in starts.items() if n >= floor]
    left = min(common) if common else min(starts)
    ends = sorted((ln.x1 for ln in lines if ln.x0 >= left - 0.5), reverse=True) or [max(ln.x1 for ln in lines)]
    right = ends[min(len(ends) - 1, len(ends) // OUTLIERS)]
    sizes: Counter = Counter()
    for ln in all_lines:
        sizes[ln.size] += len(ln.text)
    top = max(sizes.values())
    return left, right, min(z for z, n in sizes.items() if n == top)


class _Builder:
    def __init__(self, left: float, right: float, pitch: float, no_wrap: bool, justified: bool,
                 known_notes: set[int]):
        self.left, self.right, self.pitch, self.no_wrap, self.justified = left, right, pitch, no_wrap, justified
        self.known_notes = known_notes
        self.note_numbers: dict[NoteRef, int] = {}
        self.blocks: list = []
        self.pending: list[Line] = []
        self.tail = None          # (table, column offsets, header texts) while the last block is that table
        self.fonts: Counter = Counter()

    # -- paragraphs ---------------------------------------------------------------------------
    def runs(self, p: PdfPara) -> list[Run]:
        out = []
        for s in p.spans:
            family, bold, italic = split_font(s.font)
            props = RunProps(bold=bold, italic=italic, font=family, size_pt=s.size)
            digits = s.text.strip()
            if s.sup and digits.isdigit() and int(digits) in self.known_notes:
                ref = NoteRef("footnote", int(digits))
                self.note_numbers.setdefault(ref, int(digits))
                lead = s.text[:len(s.text) - len(s.text.lstrip())]
                trail = s.text[len(s.text.rstrip()):]
                if lead:
                    out.append(Run(lead, props))
                out.append(Run("", replace(props, note=ref)))
                if trail:
                    out.append(Run(trail, props))
                continue
            self.fonts[family] += len(s.text)
            out.append(Run(s.text, props))
        return out

    @staticmethod
    def leader_to_tab(runs: list[Run]) -> bool:
        """A table of contents line's dot leader, drawn as so many dots, back to the tab it was:
        the dot count depends on the title's width, so two PDFs of one TOC would differ on every
        line. Only the last leader, and only before a short page number that ends the paragraph."""
        for i in range(len(runs) - 1, -1, -1):
            hits = list(LEADER.finditer(runs[i].text))
            if hits:
                m = hits[-1]
                tail = (runs[i].text[m.end():] + "".join(r.text for r in runs[i + 1:])).strip()
                if not (1 <= len(tail) <= 8 and " " not in tail):
                    return False
                runs[i] = Run(runs[i].text[:m.start()] + "\t" + runs[i].text[m.end():], runs[i].props)
                return True
        return False

    def paragraph(self, p: PdfPara) -> Paragraph:
        runs = self.runs(p)
        tabs = ()
        if p.ind_hanging > 0 and runs:
            m = MARKER.match(runs[0].text)
            if m:
                rest = runs[0].text[m.end():]
                runs[0] = Run(runs[0].text[:m.end()] + "\t" + rest.lstrip(" \t"), runs[0].props)
                tabs = (TabStop(pos_pt=p.ind_left),)
        if self.leader_to_tab(runs):
            tabs += (TabStop(pos_pt=_half(p.lines[-1].x1 - self.left), kind="right", leader="dot"),)
        props = ParaProps(align=p.align, ind_left_pt=p.ind_left, ind_hanging_pt=p.ind_hanging,
                          ind_first_line_pt=p.ind_first, space_before_pt=0.0, space_after_pt=p.space_after, tabs=tabs)
        return Paragraph(runs, props)

    def paragraphs(self, lines: list[Line], left: float, right: float, pitch: float) -> list[Paragraph]:
        # Body, table cells and notes all use the one document-level answers: the same call on both
        # PDFs cancels out, and a cell or a note is far too little text to measure wrapping on.
        return [self.paragraph(p) for p in build_paragraphs(lines, left, right, pitch, no_wrap=self.no_wrap,
                                                            justified=self.justified)]

    def flush(self) -> None:
        if self.pending:
            self.blocks.extend(self.paragraphs(self.pending, self.left, self.right, self.pitch))
            self.pending, self.tail = [], None

    # -- tables -------------------------------------------------------------------------------
    def cell_blocks(self, c: GridCell, lines: list[Line]) -> list:
        if not lines:
            return [Paragraph([], ParaProps())]
        left = min(ln.x0 for ln in lines)
        return self.paragraphs(lines, left, c.x1 - (left - c.x0), self.pitch)

    def rows(self, grid: Grid, cell_lines: dict[int, list[Line]]) -> list[Row]:
        cover: dict[tuple[int, int], int] = {}
        for ci, c in enumerate(grid.cells):
            for r in range(c.row, c.row + c.rowspan):
                for k in range(c.col, c.col + c.colspan):
                    cover[(r, k)] = ci
        rows = []
        for r in range(len(grid.ys) - 1):
            cells, k = [], 0
            while k < len(grid.xs) - 1:
                c = grid.cells[cover[(r, k)]]
                end = max(k + 1, c.col + c.colspan)
                if c.row == r:
                    blocks, merge = self.cell_blocks(c, cell_lines.get(cover[(r, k)], [])), ("restart" if c.rowspan > 1 else None)
                else:
                    blocks, merge = [Paragraph([], ParaProps())], "continue"
                cells.append(Cell(blocks, grid_span=end - k, v_merge=merge))
                k = end
            rows.append(Row(cells))
        return rows

    @staticmethod
    def row_texts(row: Row) -> list[str] | None:
        texts = [collapse_ws(" ".join(b.text for b in c.blocks if isinstance(b, Paragraph))) for c in row.cells]
        return texts if any(texts) else None

    def add_table(self, grid: Grid, cell_lines: dict[int, list[Line]], first_on_page: bool) -> None:
        rows = self.rows(grid, cell_lines)
        offsets = [x - grid.xs[0] for x in grid.xs]
        if first_on_page and not self.pending and self.tail is not None:
            table, prev, header = self.tail
            if len(prev) == len(offsets) and all(abs(a - b) <= 2 * TOL for a, b in zip(prev, offsets)):
                if header is not None and rows and self.row_texts(rows[0]) == header:
                    rows = rows[1:]
                table.rows.extend(rows)
                return
        self.flush()
        widths = [b - a for a, b in zip(grid.xs, grid.xs[1:])]
        ind = _half(grid.xs[0] - self.left)
        room = self.right - self.left
        if sum(widths) > room > 0:
            widths, ind = [w * room / sum(widths) for w in widths], 0.0
        table = Table(rows, grid_pt=widths, ind_pt=max(0.0, ind) if sum(widths) + ind <= room + TOL else 0.0)
        self.blocks.append(table)
        self.tail = (table, offsets, self.row_texts(rows[0]) if rows else None)


def _live_grids(pi: int, pg: PageLines, skip: set) -> list[int]:
    """The indices of `pg.grids` that stay: a grid with no text lines at all (a bare ruled box),
    or a grid with at least one of its text lines not skipped as furniture. A grid whose every
    text line was skipped is stripped along with them, so it must not pull a margin toward it."""
    had_text = {ln.cell[0] for ln in pg.lines if ln.cell is not None}
    alive = {ln.cell[0] for li, ln in enumerate(pg.lines) if ln.cell is not None and (pi, li) not in skip}
    return [gi for gi in range(len(pg.grids)) if gi in alive or gi not in had_text]


def _section(pages: list[PageLines], skip: set, left: float, right: float) -> Section:
    if not pages:
        return Section()
    (w, h), _n = Counter((pg.width, pg.height) for pg in pages).most_common(1)[0]
    tops, bottoms = [], []
    for pi, pg in enumerate(pages):
        live_grids = set(_live_grids(pi, pg, skip))
        ys = [(ln.y - ln.size, ln.y + 0.3 * ln.size) for li, ln in enumerate(pg.lines) if (pi, li) not in skip]
        ys += [(g.y0, g.y1) for gi, g in enumerate(pg.grids) if gi in live_grids]
        if ys and (pg.width, pg.height) == (w, h):
            tops.append(min(t for t, _b in ys))
            bottoms.append(max(b for _t, b in ys))

    def clamp(v: float, dim: float) -> float:
        return _half(min(max(v, MIN_MARGIN * dim), 0.4 * dim))
    return Section(page_w_pt=w, page_h_pt=h,
                   margin_top_pt=clamp(min(tops), h) if tops else 72.0,
                   margin_bottom_pt=clamp(h - max(bottoms), h) if bottoms else 72.0,
                   margin_left_pt=clamp(left, w), margin_right_pt=clamp(w - right, w))


def _hard_breaks(pages: list[PageLines], skip: set, notes: dict[int, list[Line]], sec: Section,
                 right: float) -> set[int]:
    """The pages (by position) that start after a page break rather than by text flowing on. Word
    fills a page to its bottom margin, give or take a kept-together heading or a widowed line, so a
    page that leaves more than BREAK_ROOM of its text column empty ended in a break. The room is
    measured to the top of the page's footnotes, which sit at the bottom whatever the body does. A
    page whose last line runs to the right edge is mid-paragraph and never ends in a break."""
    note_top: dict[int, float] = {}
    for lines in notes.values():
        for ln in lines:
            note_top[ln.page] = min(note_top.get(ln.page, ln.y), ln.y - ln.size)
    shape = (sec.page_w_pt, sec.page_h_pt)
    out = set()
    for pi, pg in enumerate(pages[:-1]):
        nxt = pages[pi + 1]
        if (pg.width, pg.height) != shape or (nxt.width, nxt.height) != shape:
            out.add(pi + 1)                 # a page of another shape stands on pages of its own
            continue
        live_grids = set(_live_grids(pi, pg, skip))
        ys = [ln.y + 0.3 * ln.size for li, ln in enumerate(pg.lines) if (pi, li) not in skip]
        ys += [g.y1 for gi, g in enumerate(pg.grids) if gi in live_grids]
        if not ys:
            continue
        body = [ln for li, ln in enumerate(pg.lines) if (pi, li) not in skip and ln.cell is None]
        last = max(body, key=lambda ln: ln.y) if body else None
        if (last is not None and last.y + 0.3 * last.size >= max(ys) and right - last.x1 <= EDGE * last.size
                and not TOC_END.search(last.text.rstrip())):
            continue                        # its last line runs on to the next page: a paragraph mid-flow
        floor = min(note_top.get(pi, pg.height), pg.height - sec.margin_bottom_pt)
        column = pg.height - sec.margin_top_pt - sec.margin_bottom_pt
        if floor - max(ys) > BREAK_ROOM * column:
            out.add(pi + 1)
    return out


def _first_paragraph(block) -> Paragraph | None:
    if isinstance(block, Paragraph):
        return block
    if isinstance(block, Table) and block.rows and block.rows[0].cells:
        return next(iter(_all_paragraphs(block.rows[0].cells[0].blocks)), None)
    return None


def _fill_space_after(blocks: list) -> None:
    paras = [p for p in _all_paragraphs(blocks)]
    known = Counter(p.props.space_after_pt for p in paras if p.props.space_after_pt is not None)
    fallback = 0.0
    if known:
        top = max(known.values())
        fallback = min(v for v, n in known.items() if n == top)
    for p in paras:
        if p.props.space_after_pt is None:
            p.props.space_after_pt = fallback


def _all_paragraphs(blocks):
    for b in blocks:
        if isinstance(b, Paragraph):
            yield b
        elif isinstance(b, Table):
            for row in b.rows:
                for cell in row.cells:
                    yield from _all_paragraphs(cell.blocks)


def build_document(pages: list[PageLines], skip: set, notes: dict[int, list[Line]], total_pages: int,
                   skipped: tuple) -> Document:
    left, right, body_size = body_metrics(pages, skip)
    body_lines = _body(pages, skip)
    pitch = prevailing_pitch(body_lines)
    no_wrap = nothing_wraps(body_lines, right)
    # A first reading of the whole body, page breaks ignored, only to ask whether it justifies.
    justified = justified_document(build_paragraphs(body_lines, left, right, pitch, no_wrap=no_wrap))
    b = _Builder(left, right, pitch, no_wrap, justified, set(notes))
    section = _section(pages, skip, left, right)
    breaks = _hard_breaks(pages, skip, notes, section, right)
    marks: list[int] = []
    for pi, pg in enumerate(pages):
        if pi in breaks:
            b.flush()
            b.tail = None           # a table after a page break is a new table, not the last one continued
            marks.append(len(b.blocks))
        live = [ln for li, ln in enumerate(pg.lines) if (pi, li) not in skip]
        by_cell: dict[tuple, list[Line]] = {}
        for ln in live:
            if ln.cell is not None:
                by_cell.setdefault(ln.cell, []).append(ln)
        live_grids = set(_live_grids(pi, pg, skip))
        items = [(ln.y - ln.size, 0, ln) for ln in live if ln.cell is None]
        items += [(g.y0, 1, gi) for gi, g in enumerate(pg.grids) if gi in live_grids]
        items.sort(key=lambda t: (t[0], t[1]))
        for n, (_top, kind, item) in enumerate(items):
            if kind == 0:
                b.pending.append(item)
            else:
                b.add_table(pg.grids[item], {ci: lines for (gi, ci), lines in by_cell.items() if gi == item}, n == 0)
    b.flush()
    for i in marks:
        if i < len(b.blocks):
            first = _first_paragraph(b.blocks[i])
            if first is not None:
                first.props.page_break_before = True
    footnotes: dict[int, list] = {}
    referenced = {ref.id for ref in b.note_numbers}
    for n in sorted(notes):
        lines = notes[n]
        note_left = min(ln.x0 for ln in lines)
        paras = b.paragraphs(lines, note_left, right, prevailing_pitch(lines))
        if n in referenced:
            footnotes[n] = paras
        else:
            b.blocks.extend(paras)
    _fill_space_after(b.blocks)
    for paras in footnotes.values():
        _fill_space_after(paras)
    default_font = b.fonts.most_common(1)[0][0] if b.fonts else None
    return Document(b.blocks, [section], default_font=default_font,
                    default_size_pt=body_size, footnotes=footnotes, note_numbers=b.note_numbers,
                    source_kind="pdf", source_pages=total_pages, skipped_pages=tuple(skipped))
