"""Entry points: a Layout (+ an optional report) -> PDF bytes."""
from __future__ import annotations

from ..layout.fonts import default_resolver
from ..layout.pages import Layout
from .draw import DrawResult, PdfOptions, draw_layout
from .fpdf_sink import FpdfPainter
from .report import ReportInfo
from .rendersets import render_set


def render(layout: Layout, report: ReportInfo | None = None,
           opts: PdfOptions | None = None) -> tuple[bytes, DrawResult]:
    opts = opts or PdfOptions()
    rs = render_set(opts.render_set)
    resolver = opts.fonts or default_resolver()
    painter = FpdfPainter(creation=opts.now)
    result = draw_layout(layout, rs, opts, painter, resolver, report)
    return painter.output(), result


def write_pdf(layout: Layout, report: ReportInfo | None = None, opts: PdfOptions | None = None) -> bytes:
    return render(layout, report, opts)[0]
