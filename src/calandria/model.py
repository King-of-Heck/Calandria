"""Calandria document tree. Every later stage (diff, layout, sinks) consumes this."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterator

# JavaScript's \s (the reference engine's whitespace): Python's \s differs at U+0085 / U+FEFF.
WS_CHARS = "\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
_WS = re.compile(f"[{WS_CHARS}]+")


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
    suff: str = "tab"        # what follows the marker: tab | space | nothing (w:suff)
    jc: str = "left"         # marker alignment at the first-line position (w:lvlJc)


@dataclass
class ParaProps:
    style_id: str | None = None
    align: str = "left"
    ind_left_pt: float = 0.0
    ind_hanging_pt: float = 0.0
    ind_first_line_pt: float = 0.0
    ind_right_pt: float = 0.0
    space_before_pt: float | None = None
    space_after_pt: float | None = None
    line_spacing: float | None = None
    line_rule: str | None = None
    line_exact_pt: float | None = None
    keep_next: bool = False
    keep_lines: bool = False
    page_break_before: bool = False
    contextual_spacing: bool = False
    outline_level: int | None = None
    style_name: str | None = None
    section_break: bool = False   # this paragraph carries a <w:sectPr>; it is the last of its section


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
    height_pt: float | None = None     # w:trHeight (twips -> pt)
    height_rule: str | None = None     # auto | atLeast | exact (Word's default for a set height is atLeast)


@dataclass
class Table:
    rows: list[Row]
    grid_pt: list[float] = field(default_factory=list)
    ind_pt: float = 0.0                # w:tblInd (dxa) -- the table's left edge relative to the margin


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
    # w:sectPr/w:type: "nextPage" (Word's default when the element is absent), "continuous",
    # "nextColumn", "evenPage", "oddPage". Every value except continuous/nextColumn starts the
    # following paragraph on a new page. Appended last so positional construction stays stable.
    type: str = "nextPage"


@dataclass
class Document:
    blocks: list
    sections: list[Section]
    default_font: str | None = None
    default_size_pt: float = 11.0
    even_and_odd: bool = False
    default_tab_pt: float = 36.0       # w:settings/w:defaultTabStop (720 twips when absent)

    def paragraphs(self) -> Iterator[Paragraph]:
        yield from iter_paragraphs(self.blocks)


def iter_paragraphs(blocks) -> Iterator[Paragraph]:
    for b in blocks:
        if isinstance(b, Paragraph):
            yield b
        elif isinstance(b, Table):
            for row in b.rows:
                for cell in row.cells:
                    yield from iter_paragraphs(cell.blocks)
