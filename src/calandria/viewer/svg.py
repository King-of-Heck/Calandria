"""The Painter that writes one SVG per page. The same draw_layout walk that writes the PDF emits
these, so the screen and the PDF are one drawing. User units are points (viewBox "0 0 w h"); the
page's CSS width sets the zoom."""
from __future__ import annotations

from xml.sax.saxutils import escape, quoteattr

from ..layout.fonts import default_resolver
from ..layout.pages import Layout
from ..pdf.draw import PdfOptions, draw_layout
from ..pdf.fpdf_sink import DASH, DASH_GAP, ITALIC_DEGREES, STROKE_FRACTION
from ..pdf.rendersets import render_set

SVG_NS = "http://www.w3.org/2000/svg"


def _n(v: float) -> str:
    return f"{v:.2f}"


class SvgPainter:
    def __init__(self):
        self._pages: list[list[str]] = []

    # -- Painter ---------------------------------------------------------------------------
    def page(self, w: float, h: float) -> None:
        self._pages.append([f'<svg xmlns="{SVG_NS}" viewBox="0 0 {_n(w)} {_n(h)}" '
                            f'width="{_n(w)}pt" height="{_n(h)}pt">'])

    def text(self, x: float, baseline: float, text: str, face, size: float, color: str,
             fake_bold: bool = False, fake_italic: bool = False, width: float | None = None,
             role: str | None = None) -> None:
        if not text:
            return
        attrs = [f'x="{_n(x)}"', f'y="{_n(baseline)}"', f"font-family={quoteattr(face.family)}",
                 f'font-size="{_n(size)}"', f'fill="#{color}"']
        if role == "gutter":
            # anchored at its right edge so the viewer can enlarge it leftwards, away from the bar
            attrs[0] = f'x="{_n(x + (width or 0))}"'
            attrs += ['class="gutter"', 'text-anchor="end"']
            width = None
        if face.bold and not face.synthetic:
            attrs.append('font-weight="bold"')
        if face.italic and not face.synthetic:
            attrs.append('font-style="italic"')
        if fake_bold:
            attrs += [f'stroke="#{color}"', f'stroke-width="{_n(size * STROKE_FRACTION)}"']
        if fake_italic:
            attrs.append(f'transform="translate({_n(x)} {_n(baseline)}) skewX(-{ITALIC_DEGREES}) '
                         f'translate(-{_n(x)} -{_n(baseline)})"')
        if width:
            attrs += [f'textLength="{_n(width)}"', 'lengthAdjust="spacing"']
        attrs.append('xml:space="preserve"')
        self._pages[-1].append(f"<text {' '.join(attrs)}>{escape(text)}</text>")

    def rule(self, x1: float, x2: float, y: float, thickness: float, color: str, dotted: bool = False) -> None:
        dash = f' stroke-dasharray="{_n(DASH)} {_n(DASH_GAP)}"' if dotted else ""
        self._pages[-1].append(f'<line x1="{_n(x1)}" y1="{_n(y)}" x2="{_n(x2)}" y2="{_n(y)}" '
                               f'stroke="#{color}" stroke-width="{_n(thickness)}"{dash}/>')

    def line(self, x1: float, y1: float, x2: float, y2: float, width: float, color: str) -> None:
        self._pages[-1].append(f'<line x1="{_n(x1)}" y1="{_n(y1)}" x2="{_n(x2)}" y2="{_n(y2)}" '
                               f'stroke="#{color}" stroke-width="{_n(width)}"/>')

    # -- output -----------------------------------------------------------------------------
    def pages(self) -> list[str]:
        return ["".join(p) + "</svg>" for p in self._pages]


def render_pages(layout: Layout, render_set_name: str = "Standard", change_bars: bool = True,
                 resolver=None) -> list[str]:
    """One SVG per page of the layout, styled by the named rendering set; no report block."""
    rs = render_set(render_set_name)
    opts = PdfOptions(render_set=render_set_name, change_bars=change_bars, report="none")
    painter = SvgPainter()
    draw_layout(layout, rs, opts, painter, resolver or default_resolver(), None)
    return painter.pages()
