"""The drawing surface the sink draws on. Four operations, points, origin top-left, y downward.
`face` is any object with path, font_number, family, bold, italic, synthetic (a layout FontRef, a
fonts.Face or the test FakeFace); the painter decides how to load it."""
from __future__ import annotations

from typing import Protocol


class Painter(Protocol):
    def page(self, w: float, h: float) -> None: ...

    def text(self, x: float, baseline: float, text: str, face, size: float, color: str,
             fake_bold: bool = False, fake_italic: bool = False) -> None: ...

    def rule(self, x1: float, x2: float, y: float, thickness: float, color: str,
             dotted: bool = False) -> None: ...

    def line(self, x1: float, y1: float, x2: float, y2: float, width: float, color: str) -> None: ...


def rgb(color: str) -> tuple[int, int, int]:
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
