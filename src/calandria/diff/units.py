"""The flat stream of paragraph units the diff runs over.

Body paragraphs and table-cell paragraphs are one stream in document order, each unit carrying
its table location. Empty paragraphs are not units (they are layout, not content).
"""
from __future__ import annotations

from dataclasses import dataclass

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


def units(doc: Document) -> list[Unit]:
    out: list[Unit] = []

    def add(p: Paragraph, loc: Loc | None):
        if p.is_empty:
            return
        out.append(Unit(len(out), p.text, p.num.marker if p.num else "", bold_runs(p), fmt_spans(p),
                        loc, p))

    ti = 0
    for b in doc.blocks:
        if isinstance(b, Paragraph):
            add(b, None)
        elif isinstance(b, Table):
            cols = len(b.grid_pt) or max((len(r.cells) for r in b.rows), default=0)
            for ri, row in enumerate(b.rows):
                for ci, cell in enumerate(row.cells):
                    for p in iter_paragraphs(cell.blocks):
                        add(p, Loc(ti, ri, ci, cols))
            ti += 1
    return out
