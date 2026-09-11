"""Styled text pieces of one comparison row, ready for measurement.

A row's segments concatenate back to the paragraph texts they came from: the del-mode segments
plus the shared (eq) segments spell the original paragraph, the ins-mode segments plus the shared
ones spell the revised paragraph (the dense-rewrite coalescing duplicates a shared connective into
both, and both cursors advance over it). Walking the segments with one cursor per side therefore
recovers where every segment sits in its source text, and the unit's per-character formatting
spans are sliced at those offsets. Bold is per character here (the diff's per-token majority bold
on Seg.b is a presentation choice of the reference row shape and is not used).
"""
from __future__ import annotations

from dataclasses import dataclass

from ..diff.changes import Comparison, Row
from ..diff.units import Unit


@dataclass
class LayoutOptions:
    show_equal: bool = True
    show_insertions: bool = True
    show_deletions: bool = True
    show_formatting: bool = True
    fonts: object | None = None    # a FontResolver (or the test FakeResolver); None = system fonts
    side: str = "blackline"        # blackline | original | modified (spec §12.1)


@dataclass
class Piece:
    text: str
    mode: str                      # eq | del | ins
    bold: bool = False
    italic: bool = False
    underline: bool = False
    font: str | None = None
    size: float | None = None
    color: str | None = None
    fmt: bool = False              # inside a formatting-change range (only when formatting is shown)
    cid: int | None = None

    def style_key(self):
        return (self.mode, self.bold, self.italic, self.underline, self.font, self.size, self.color,
                self.fmt, self.cid)


def visible(row: Row, opts: LayoutOptions) -> bool:
    if row.type == "equal":
        return opts.show_equal or (row.fmt_changed and opts.show_formatting) or row.num_changed
    if row.type == "inserted":
        return opts.show_insertions
    if row.type == "deleted":
        return opts.show_deletions
    return opts.show_insertions or opts.show_deletions


def merge_pieces(pieces: list[Piece]) -> list[Piece]:
    out: list[Piece] = []
    for p in pieces:
        if out and out[-1].style_key() == p.style_key():
            out[-1].text += p.text
        elif p.text:
            out.append(Piece(p.text, p.mode, p.bold, p.italic, p.underline, p.font, p.size, p.color,
                             p.fmt, p.cid))
    return out


def _slice(unit: Unit, s: int, e: int, mode: str, ranges, cid) -> list[Piece]:
    spans = unit.fmt_spans
    cuts = {s, e}
    for sp in spans:
        if s < sp.s < e:
            cuts.add(sp.s)
        if s < sp.e < e:
            cuts.add(sp.e)
    for r in ranges:
        if s < r.s < e:
            cuts.add(r.s)
        if s < r.e < e:
            cuts.add(r.e)
    pts = sorted(cuts)
    out: list[Piece] = []
    for a, b in zip(pts, pts[1:]):
        sp = next((x for x in spans if x.s <= a < x.e), None)
        fmt = any(r.s <= a < r.e for r in ranges)
        text = unit.text[a:b]
        if sp is None:
            out.append(Piece(text, mode, fmt=fmt, cid=cid))
        else:
            out.append(Piece(text, mode, sp.b, sp.i, sp.u, sp.f, sp.z, sp.clr, fmt, cid))
    return out


def row_pieces(cmp: Comparison, row: Row, opts: LayoutOptions) -> list[Piece]:
    ou = cmp.a_units[row.oi] if row.oi is not None else None
    ru = cmp.b_units[row.ni] if row.ni is not None else None
    ranges = row.fmt_ranges if (row.fmt_changed and opts.show_formatting) else []
    oa = ob = 0
    out: list[Piece] = []
    for seg in row.segments:
        n = len(seg.t)
        if seg.m == "del":
            unit, start, oa = ou, oa, oa + n
        elif seg.m == "ins":
            unit, start, ob = ru, ob, ob + n
        else:
            unit, start = (ou, oa) if opts.side == "original" else (ru, ob)
            oa += n
            ob += n
        if seg.m == "del" and not opts.show_deletions:
            continue
        if seg.m == "ins" and not opts.show_insertions:
            continue
        out.extend(_slice(unit, start, start + n, seg.m, ranges if seg.m == "eq" else [], row.cid))
    return merge_pieces(out)
