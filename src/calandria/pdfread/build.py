"""Paragraphs, ruled grids and notes -> the Document the rest of Calandria reads. The walk is over
ONE stream of body items in reading order, page after page, so a paragraph or a table that
continues over a page break comes out whole."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import replace

from ..model import (Cell, Document, NoteRef, Paragraph, ParaProps, Row, Run, RunProps, Section, Table,
                     TabStop, collapse_ws)
from .grid import TOL, Grid, GridCell
from .paras import MARKER, PdfPara, build_paragraphs, nothing_wraps, prevailing_pitch
from .types import Line, PageLines

_SUBSET = re.compile(r"^[A-Z]{6}\+")
_STYLE_TAIL = re.compile(r"^(.+?)(BoldItalic|BoldOblique|Bold|Italic|Oblique)$")
_WORDS = re.compile(r"[A-Z][a-z]+|[A-Z]+(?![a-z])|[a-z]+|\d+")
_STYLE_WORDS = {"bold", "italic", "oblique", "regular", "roman", "mt", "ps", "psmt"}
_CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z])")
MIN_MARGIN = 0.03      # of the page width or height: a measured margin is never less than this


def _half(v: float) -> float:
    return round(v * 2) / 2


def split_font(name: str) -> tuple[str, bool, bool]:
    """'ABCDEF+TimesNewRomanPS-BoldItalicMT' -> ('Times New Roman', True, True)."""
    base = _SUBSET.sub("", name)
    head, tail = (re.split(r"[,-]", base, maxsplit=1) + [""])[:2]
    head = re.sub(r"(PSMT|PS|MT)$", "", head)
    m = _STYLE_TAIL.match(head)
    if m:
        head, tail = m.group(1), m.group(2) + tail
    words = _WORDS.findall(tail)                     # 'BoldItalicMT' -> Bold, Italic, MT; 'Semibold' stays one word
    low = [w.lower() for w in words]
    bold, italic = "bold" in low, "italic" in low or "oblique" in low
    rest = [w for w in words if w.lower() not in _STYLE_WORDS]
    family = " ".join([_CAMEL.sub(" ", head.replace("_", " ")).strip(), *rest]).strip()
    return family or "Unknown", bold, italic


def _body(pages: list[PageLines], skip: set) -> list[Line]:
    return [ln for pi, pg in enumerate(pages) for li, ln in enumerate(pg.lines)
            if ln.cell is None and (pi, li) not in skip]


def body_metrics(pages: list[PageLines], skip: set) -> tuple[float, float, float]:
    """(left edge, right edge, body font size) of the text column. The left edge is the leftmost
    x that a fair number of lines start at, so one outdented line does not move the margin."""
    lines = _body(pages, skip)
    if not lines:
        width = pages[0].width if pages else 612.0
        return 72.0, width - 72.0, 11.0
    starts = Counter(_half(ln.x0) for ln in lines)
    floor = max(2, len(lines) // 50) if len(lines) >= 10 else 1
    common = [x for x, n in starts.items() if n >= floor]
    left = min(common) if common else min(starts)
    right = max(ln.x1 for ln in lines if ln.x0 >= left - 0.5) if any(ln.x0 >= left - 0.5 for ln in lines) else max(ln.x1 for ln in lines)
    sizes: Counter = Counter()
    for ln in lines:
        sizes[ln.size] += len(ln.text)
    top = max(sizes.values())
    return left, right, min(z for z, n in sizes.items() if n == top)


class _Builder:
    def __init__(self, left: float, right: float, pitch: float, no_wrap: bool, known_notes: set[int]):
        self.left, self.right, self.pitch, self.no_wrap = left, right, pitch, no_wrap
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

    def paragraph(self, p: PdfPara) -> Paragraph:
        runs = self.runs(p)
        tabs = ()
        if p.ind_hanging > 0 and runs:
            m = MARKER.match(runs[0].text)
            if m:
                rest = runs[0].text[m.end():]
                runs[0] = Run(runs[0].text[:m.end()] + "\t" + rest.lstrip(" \t"), runs[0].props)
                tabs = (TabStop(pos_pt=p.ind_left),)
        props = ParaProps(align=p.align, ind_left_pt=p.ind_left, ind_hanging_pt=p.ind_hanging,
                          ind_first_line_pt=p.ind_first, space_before_pt=0.0, space_after_pt=p.space_after, tabs=tabs)
        return Paragraph(runs, props)

    def paragraphs(self, lines: list[Line], left: float, right: float, pitch: float) -> list[Paragraph]:
        # Body, table cells and notes all use the one document-level answer: the same call on both
        # PDFs cancels out, and a cell or a note is far too little text to measure wrapping on.
        return [self.paragraph(p) for p in build_paragraphs(lines, left, right, pitch, no_wrap=self.no_wrap)]

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
    b = _Builder(left, right, pitch, nothing_wraps(body_lines, right), set(notes))
    for pi, pg in enumerate(pages):
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
    return Document(b.blocks, [_section(pages, skip, left, right)], default_font=default_font,
                    default_size_pt=body_size, footnotes=footnotes, note_numbers=b.note_numbers,
                    source_kind="pdf", source_pages=total_pages, skipped_pages=tuple(skipped))
