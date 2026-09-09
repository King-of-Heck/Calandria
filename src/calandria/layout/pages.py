"""The page model every sink draws: pages of positioned lines of glyph runs, plus table boxes.
Points, origin top-left, y downward. Colours, strikes and underlines are the sink's business
(render sets); a run carries its diff mode, formatting-change flag and change number instead.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .pieces import LayoutOptions


@dataclass
class GlyphRun:
    text: str
    x: float
    w: float
    face: str            # font face key, resolved through Layout.fonts
    size: float
    bold: bool
    italic: bool
    underline: bool      # the document's own underline (not the redline decoration)
    color: str | None    # the document's own colour, 6-hex lower-case or None
    mode: str            # eq | del | ins
    fmt: bool            # inside a formatting-change range
    cid: int | None


@dataclass
class PlacedLine:
    x: float
    top: float
    height: float
    baseline: float
    runs: list[GlyphRun]
    marker: list[GlyphRun]
    changed: bool
    cid_starts: list[int]     # change numbers whose first line this is (gutter numbers)
    row_index: int | None


@dataclass
class CellBox:
    x: float
    y: float
    w: float
    h: float
    v_merge_continue: bool


@dataclass
class TableRowBox:
    x: float
    y: float
    w: float
    h: float
    cells: list[CellBox]
    changed: bool
    cids: list[int]           # change numbers of the row's changed cells (gutter numbers)


@dataclass
class Page:
    number: int
    w: float
    h: float
    margin_left: float
    margin_top: float
    margin_right: float
    margin_bottom: float
    section: int
    lines: list[PlacedLine] = field(default_factory=list)
    table_rows: list[TableRowBox] = field(default_factory=list)


@dataclass
class FontRef:
    path: str
    font_number: int
    family: str
    bold: bool
    italic: bool
    synthetic: bool


@dataclass
class Layout:
    pages: list[Page]
    fonts: dict[str, FontRef]
    options: LayoutOptions

    @property
    def page_count(self) -> int:
        return len(self.pages)

    def to_dict(self) -> dict:
        r = lambda v: round(v, 2)  # noqa: E731

        def run(g: GlyphRun) -> dict:
            return {"t": g.text, "x": r(g.x), "w": r(g.w), "face": g.face, "size": r(g.size), "b": g.bold,
                    "i": g.italic, "u": g.underline, "clr": g.color, "m": g.mode, "fmt": g.fmt, "cid": g.cid}

        def line(ln: PlacedLine) -> dict:
            return {"x": r(ln.x), "top": r(ln.top), "h": r(ln.height), "baseline": r(ln.baseline),
                    "changed": ln.changed, "cids": list(ln.cid_starts), "row": ln.row_index,
                    "runs": [run(g) for g in ln.runs], "marker": [run(g) for g in ln.marker]}

        def trow(t: TableRowBox) -> dict:
            return {"x": r(t.x), "y": r(t.y), "w": r(t.w), "h": r(t.h), "changed": t.changed,
                    "cids": list(t.cids),
                    "cells": [{"x": r(c.x), "y": r(c.y), "w": r(c.w), "h": r(c.h), "vm": c.v_merge_continue}
                              for c in t.cells]}

        return {
            "page_count": self.page_count,
            "options": {k: getattr(self.options, k) for k in
                        ("show_equal", "show_insertions", "show_deletions", "show_formatting")},
            "fonts": {k: asdict(f) for k, f in self.fonts.items()},
            "pages": [{"number": p.number, "w": r(p.w), "h": r(p.h),
                       "margins": [r(p.margin_left), r(p.margin_top), r(p.margin_right), r(p.margin_bottom)],
                       "section": p.section, "lines": [line(ln) for ln in p.lines],
                       "table_rows": [trow(t) for t in p.table_rows]} for p in self.pages],
        }
