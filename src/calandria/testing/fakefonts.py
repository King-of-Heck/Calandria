"""Fixed-metric fonts for exact layout tests: every glyph is char_w * size wide, every line
lh * size tall with the baseline asc * size below the top. Same surface as layout.fonts."""
from __future__ import annotations


class FakeFace:
    def __init__(self, family: str, bold: bool, italic: bool, char_w: float, lh: float, asc: float):
        self.family, self.bold, self.italic, self.synthetic = family, bold, italic, False
        self.key = f"{family}|{'B' if bold else ''}{'I' if italic else ''}"
        self.path, self.font_number = f"<fake:{self.key}>", 0
        self._cw, self._lh, self._asc = char_w, lh, asc

    def width(self, text: str, size: float) -> float:
        return len(text) * self._cw * size

    def line_height(self, size: float) -> float:
        return self._lh * size

    def ascent(self, size: float) -> float:
        return self._asc * size

    def descent(self, size: float) -> float:
        return (self._lh - self._asc) * size


class FakeResolver:
    def __init__(self, char_w: float = 0.5, lh: float = 1.2, asc: float = 0.8):
        self._args = (char_w, lh, asc)
        self._faces: dict[tuple[str, bool, bool], FakeFace] = {}
        self.fallback = "Fake"

    def resolve_family(self, family):
        return family or self.fallback

    def face(self, family, bold: bool = False, italic: bool = False) -> FakeFace:
        k = (self.resolve_family(family), bool(bold), bool(italic))
        if k not in self._faces:
            self._faces[k] = FakeFace(k[0], k[1], k[2], *self._args)
        return self._faces[k]
