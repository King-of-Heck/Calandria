"""Plain data handed between the PDF reader's stages. Coordinates are points: x from the page's
left edge, y DOWN from the page's top edge (the layout engine's direction, not the PDF's)."""
from __future__ import annotations

from dataclasses import dataclass, field


class PdfRefused(ValueError):
    """A PDF the reader will not read; the message is written for the user."""


@dataclass(frozen=True)
class TextRun:
    text: str
    x0: float
    x1: float
    y: float          # the baseline
    size: float       # the font size as drawn
    font: str         # /BaseFont without the slash (a subset prefix still on it)


@dataclass(frozen=True)
class Seg:
    """One axis-aligned piece of a drawn border or rule: x0 <= x1, y0 <= y1."""
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def horizontal(self) -> bool:
        return (self.x1 - self.x0) >= (self.y1 - self.y0)

    @property
    def length(self) -> float:
        return max(self.x1 - self.x0, self.y1 - self.y0)


@dataclass
class PageData:
    width: float
    height: float
    runs: list[TextRun] = field(default_factory=list)
    segs: list[Seg] = field(default_factory=list)
    images: int = 0
    chars: int = 0        # characters decoded on the page
    bad_chars: int = 0    # of them, characters the font could not map


@dataclass(frozen=True)
class Span:
    text: str
    font: str
    size: float
    sup: bool = False     # smaller and raised: a footnote mark, an ordinal


@dataclass
class Line:
    page: int             # index into the pages that were read
    x0: float
    x1: float
    y: float              # the baseline of the line's dominant size
    size: float           # the dominant size
    spans: list[Span]
    cell: tuple | None = None    # (grid index on the page, cell index in that grid), or None = body

    @property
    def text(self) -> str:
        return "".join(s.text for s in self.spans)


@dataclass
class PageLines:
    index: int            # the page's index in the PDF (0-based)
    width: float
    height: float
    lines: list[Line]     # every line of the page, body and cells, sorted by (y, x0)
    grids: list           # grid.Grid, in top-to-bottom order
    segs: list[Seg]
