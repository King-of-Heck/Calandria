"""Calandria document tree. Every later stage (diff, layout, sinks) consumes this."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterator

_WS = re.compile(r"\s+")


def collapse_ws(s: str) -> str:
    return _WS.sub(" ", s).strip()


@dataclass
class RunProps:
    bold: bool = False
    italic: bool = False
    underline: bool = False
    font: str | None = None
    size_pt: float | None = None
    color: str | None = None


@dataclass
class Run:
    text: str
    props: RunProps


@dataclass
class NumInfo:
    num_id: int
    ilvl: int
    marker: str
    is_bullet: bool


@dataclass
class ParaProps:
    style_id: str | None = None
    align: str = "left"
    ind_left_pt: float = 0.0
    ind_hanging_pt: float = 0.0
    ind_first_line_pt: float = 0.0
    space_before_pt: float | None = None
    space_after_pt: float | None = None
    line_spacing: float | None = None
    line_rule: str | None = None
    keep_next: bool = False
    keep_lines: bool = False
    page_break_before: bool = False
    contextual_spacing: bool = False
    outline_level: int | None = None


@dataclass
class Paragraph:
    runs: list[Run]
    props: ParaProps
    num: NumInfo | None = None

    @property
    def text(self) -> str:
        return collapse_ws("".join(r.text for r in self.runs))

    @property
    def is_empty(self) -> bool:
        return self.text == ""


@dataclass
class Cell:
    blocks: list
    grid_span: int = 1
    v_merge: str | None = None


@dataclass
class Row:
    cells: list[Cell]


@dataclass
class Table:
    rows: list[Row]
    grid_pt: list[float] = field(default_factory=list)


@dataclass
class Section:
    page_w_pt: float = 612.0
    page_h_pt: float = 792.0
    margin_top_pt: float = 72.0
    margin_right_pt: float = 72.0
    margin_bottom_pt: float = 72.0
    margin_left_pt: float = 72.0
    header_pt: float = 36.0
    footer_pt: float = 36.0
    title_pg: bool = False


@dataclass
class Document:
    blocks: list
    sections: list[Section]
    default_font: str | None = None
    default_size_pt: float = 11.0
    even_and_odd: bool = False

    def paragraphs(self) -> Iterator[Paragraph]:
        yield from _walk(self.blocks)


def _walk(blocks) -> Iterator[Paragraph]:
    for b in blocks:
        if isinstance(b, Paragraph):
            yield b
        elif isinstance(b, Table):
            for row in b.rows:
                for cell in row.cells:
                    yield from _walk(cell.blocks)
