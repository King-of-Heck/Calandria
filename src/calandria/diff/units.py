"""The flat stream of paragraph units the diff runs over.

Body paragraphs and table-cell paragraphs are one stream in document order, each unit carrying
its table location. Empty paragraphs are not units (they are layout, not content).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from ..model import Document, Paragraph, Table, iter_paragraphs
from .chars import FmtSpan, bold_runs, fmt_spans


@dataclass(frozen=True)
class Loc:
    ti: int
    ri: int
    ci: int
    cols: int


@dataclass
class Unit:
    index: int
    text: str
    marker: str
    bold_runs: list[list[int]]
    fmt_spans: list[FmtSpan]
    loc: Loc | None
    para: Paragraph


def walk(doc: Document) -> Iterator[tuple[Paragraph, Loc | None]]:
    """Every paragraph in stream order (empty ones included) with its table location.

    This is the ONE definition of stream order: units() is built on it, and the layout's merged
    walk relies on empties and units sharing it."""
    ti = 0
    for b in doc.blocks:
        if isinstance(b, Paragraph):
            yield b, None
        elif isinstance(b, Table):
            cols = len(b.grid_pt) or max((len(r.cells) for r in b.rows), default=0)
            for ri, row in enumerate(b.rows):
                for ci, cell in enumerate(row.cells):
                    for p in iter_paragraphs(cell.blocks):
                        yield p, Loc(ti, ri, ci, cols)
            ti += 1


def units(doc: Document) -> list[Unit]:
    out: list[Unit] = []
    for p, loc in walk(doc):
        if p.is_empty:
            continue
        out.append(Unit(len(out), p.text, p.num.marker if p.num else "", bold_runs(p), fmt_spans(p), loc, p))
    return out


def table_by_ti(doc: Document, ti: int) -> Table:
    """The ti-th top-level table -- the table a Loc.ti refers to."""
    return [b for b in doc.blocks if isinstance(b, Table)][ti]
