"""Walks a Layout and emits Painter calls: runs and markers with their decorations, the table
grid, change bars, gutter change numbers, and the pages themselves."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..layout.pages import FontRef, GlyphRun, Layout, Page, PlacedLine, TableRowBox
from .decor import decorations, run_effects
from .rendersets import RenderSet
from .report import GAP, ReportInfo, draw_report, report_height

BLACK = "000000"


@dataclass
class PdfOptions:
    render_set: str = "Standard"
    change_bars: bool = True
    report: str = "last"            # first | last | none
    fonts: object | None = None     # a FontResolver (or the test FakeResolver); None = system fonts
    now: datetime | None = None     # the comparison time stamped in the report; None = now


def cid_label(cids: list[int]) -> str:
    """Gutter label: contiguous numbers hyphenated, the rest comma-joined ("1-3, 5, 7-8")."""
    nums = sorted(set(cids))
    parts: list[str] = []
    i = 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        parts.append(str(nums[i]) if i == j else f"{nums[i]}-{nums[j]}")
        i = j + 1
    return ", ".join(parts)


def draw_runs(line: PlacedLine, runs: list[GlyphRun], fonts: dict[str, FontRef], rs: RenderSet, painter) -> None:
    """Text and decorations of one list of glyph runs on one line (the marker or the body runs)."""
    for g in runs:
        face = fonts[g.face]
        style = rs.category(g.mode, g.fmt)
        color = style.color if style else (g.color or BLACK)
        eff = run_effects(style.effects if style else (), g.underline)
        fake_bold = (face.synthetic and face.bold) or "bold" in eff
        fake_italic = (face.synthetic and face.italic) or "italic" in eff
        if g.text.strip():
            painter.text(g.x, line.baseline, g.text, face, g.size, color, fake_bold, fake_italic)
        for x1, x2, y, t, dotted in decorations(eff, g.x, g.x + g.w, line.baseline, g.size):
            painter.rule(x1, x2, y, t, color, dotted)


BAR_WIDTH = 1.5
BAR_GAP = 6.0          # bar x = margin_left - BAR_GAP
NUMBER_SIZE = 7.0
NUMBER_GAP = 10.0      # number right edge = margin_left - NUMBER_GAP
GRID_WIDTH = 0.5
_EPS = 1e-6


def _in_row(line: PlacedLine, rows: list[TableRowBox]) -> bool:
    return any(r.y - _EPS <= line.top and line.top + line.height <= r.y + r.h + _EPS
               and r.x - _EPS <= line.x <= r.x + r.w + _EPS for r in rows)


def bar_intervals(page: Page) -> list[tuple[float, float]]:
    """Vertical (top, bottom) spans of the change bars: changed rows as a whole, changed lines
    outside rows, merged when they touch or overlap."""
    spans = [(r.y, r.y + r.h) for r in page.table_rows if r.changed]
    spans += [(ln.top, ln.top + ln.height) for ln in page.lines
              if ln.changed and not _in_row(ln, page.table_rows)]
    spans.sort()
    merged: list[tuple[float, float]] = []
    for a, b in spans:
        if merged and a <= merged[-1][1] + 0.5:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def draw_grid(page: Page, painter) -> None:
    """The uniform table grid (KNOWN_DIVERGENCES (m)): four rules per cell, no top rule on a
    vertically merged continuation."""
    for row in page.table_rows:
        for c in row.cells:
            x2, y2 = c.x + c.w, c.y + c.h
            if not c.v_merge_continue:
                painter.line(c.x, c.y, x2, c.y, GRID_WIDTH, BLACK)
            painter.line(x2, c.y, x2, y2, GRID_WIDTH, BLACK)
            painter.line(c.x, y2, x2, y2, GRID_WIDTH, BLACK)
            painter.line(c.x, c.y, c.x, y2, GRID_WIDTH, BLACK)


def draw_page(page: Page, fonts: dict[str, FontRef], rs: RenderSet, opts: PdfOptions, painter, number_face) -> None:
    painter.page(page.w, page.h)
    draw_grid(page, painter)
    for ln in page.lines:
        draw_runs(ln, ln.marker, fonts, rs, painter)
        draw_runs(ln, ln.runs, fonts, rs, painter)
    for ln in page.lines:
        if ln.cid_starts:
            label = cid_label(ln.cid_starts)
            w = number_face.width(label, NUMBER_SIZE)
            painter.text(page.margin_left - NUMBER_GAP - w, ln.baseline, label, number_face, NUMBER_SIZE, BLACK)
    if opts.change_bars:
        x = page.margin_left - BAR_GAP
        for y1, y2 in bar_intervals(page):
            painter.line(x, y1, x, y2, BAR_WIDTH, BLACK)


def content_bottom(page: Page) -> float:
    """The lowest edge of anything on the page (the top margin on an empty page)."""
    ys = [page.margin_top]
    ys += [ln.top + ln.height for ln in page.lines]
    ys += [r.y + r.h for r in page.table_rows]
    return max(ys)


@dataclass
class DrawResult:
    pages: int                  # pages emitted, report page included
    report_page: int | None     # 1-based page the report block is on, None when omitted


def _report_faces(layout: Layout, resolver):
    fam = next((f.family for f in layout.fonts.values()), None)
    return resolver.face(fam), resolver.face(fam, bold=True)


def draw_layout(layout: Layout, rs: RenderSet, opts: PdfOptions, painter, resolver,
                report: ReportInfo | None) -> DrawResult:
    regular, bold = _report_faces(layout, resolver)      # the document's own face; also the gutter numbers
    where = opts.report if report is not None else "none"
    n, report_page = 0, None
    if where == "first":
        g = layout.pages[0]
        painter.page(g.w, g.h)
        draw_report(report, g.margin_left, g.margin_top, g.w - g.margin_left - g.margin_right, regular, bold, painter)
        n, report_page = 1, 1
    for page in layout.pages:
        draw_page(page, layout.fonts, rs, opts, painter, regular)
        n += 1
    if where == "last":
        last = layout.pages[-1]
        w = last.w - last.margin_left - last.margin_right
        y = content_bottom(last) + GAP
        if y + report_height(report, regular, bold) > last.h - last.margin_bottom + _EPS:
            painter.page(last.w, last.h)
            n, y = n + 1, last.margin_top
        draw_report(report, last.margin_left, y, w, regular, bold, painter)
        report_page = n
    return DrawResult(n, report_page)
