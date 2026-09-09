"""Walks a Layout and emits Painter calls: runs and markers with their decorations, the table
grid, change bars, gutter change numbers, and the pages themselves."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..layout.pages import FontRef, GlyphRun, PlacedLine
from .decor import decorations, run_effects
from .rendersets import RenderSet

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
