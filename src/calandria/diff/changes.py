"""The change model: rows in document order, passages numbered in reading order, the counts.

This is the single object the layout engine, the viewer and the reports consume. It is plain
data (to_dict() is JSON) and carries no rendering. A row is one paragraph of the comparison; a
passage is one numbered change inside it (spec section 14).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..model import Document
from .fmt import FmtRange
from .inline import Seg
from .units import Unit

# insertions / deletions / numbering_changes count passages and add up to total; content,
# punctuation, numbering, formatting, moves, splits, merges keep the reference's per-row meaning
# for the parity gate (numbering = every renumbered row, counted or not).
SUMMARY_KEYS = ("insertions", "deletions", "moves", "content", "numbering", "punctuation", "total",
                "formatting", "splits", "merges", "numbering_changes")


def empty_summary() -> dict:
    return {k: 0 for k in SUMMARY_KEYS}


@dataclass
class Passage:
    cid: int
    category: str                   # "insertion" | "deletion" | "numbering"
    row: int                        # index into Comparison.rows

    def as_dict(self) -> dict:
        return {"cid": self.cid, "category": self.category, "row": self.row}


@dataclass
class Row:
    type: str                       # "equal" | "changed" | "inserted" | "deleted"
    oi: int | None                  # index into the original units
    ni: int | None                  # index into the revised units
    segments: list[Seg]
    cat: str | None = None          # "content" | "punctuation" on changed rows
    fmt_changed: bool = False
    fmt_ranges: list[FmtRange] = field(default_factory=list)
    num_changed: bool = False
    old_marker: str | None = None
    cids: list[int] = field(default_factory=list)   # the row's passage numbers in reading order
    num_cid: int | None = None      # the numbering passage (a renumbered marker), when counted


def row_passages(row: Row, row_index: int, first: int, count_numbering: bool) -> list[Passage]:
    """Numbers the row's passages from `first` and stamps them on the row and its segments
    (spec 14.1, 14.2). The renumbered marker comes first. Then, per side: an inserted passage is
    a maximal stretch of `ins` segments broken only by an equal segment holding visible text;
    whitespace-only equal text and `del` segments in between do not break it. Deleted passages
    likewise. A replacement therefore numbers its deletion before its insertion."""
    out: list[Passage] = []
    n = first - 1
    row.cids = []
    row.num_cid = None
    if row.num_changed and count_numbering:
        n += 1
        row.num_cid = n
        row.cids.append(n)
        out.append(Passage(n, "numbering", row_index))
    open_ins: int | None = None
    open_del: int | None = None
    for s in row.segments:
        if s.m == "eq":
            s.cid = None
            if s.t.strip():
                open_ins = open_del = None
            continue
        if s.m == "ins":
            if open_ins is None:
                n += 1
                open_ins = n
                row.cids.append(n)
                out.append(Passage(n, "insertion", row_index))
            s.cid = open_ins
        else:
            if open_del is None:
                n += 1
                open_del = n
                row.cids.append(n)
                out.append(Passage(n, "deletion", row_index))
            s.cid = open_del
    return out


@dataclass
class Comparison:
    rows: list[Row]
    summary: dict
    a_units: list[Unit]
    b_units: list[Unit]
    ignore_case: bool
    count_numbering: bool
    passages: list[Passage] = field(default_factory=list)
    a_doc: Document | None = None
    b_doc: Document | None = None
    # (side, NoteRef) -> "ins" | "del" | "eq": how a note's reference mark is drawn when the text
    # around it is shared -- an inserted note's mark is inserted, a deleted note's deleted
    note_modes: dict = field(default_factory=dict)
    note_rows: dict = field(default_factory=dict)    # (side, NoteRef) -> index of the note's first row

    def unit_for(self, row: Row) -> Unit:
        return self.b_units[row.ni] if row.ni is not None else self.a_units[row.oi]

    def _row_dict(self, r: Row) -> dict:
        u = self.unit_for(r)
        loc = u.loc.as_dict() if u.loc else None
        return {
            "type": r.type, "cids": list(r.cids), "num_cid": r.num_cid, "cat": r.cat,
            "oi": r.oi, "ni": r.ni, "loc": loc, "marker": u.marker, "old_marker": r.old_marker,
            "stream": u.stream, "note": {"kind": u.note.kind, "id": u.note.id} if u.note else None,
            "num_changed": r.num_changed, "fmt_changed": r.fmt_changed,
            "fmt_descs": [x.desc for x in r.fmt_ranges],
            "segments": [{"m": s.m, "t": s.t, "b": s.b, "cid": s.cid} for s in r.segments],
        }

    def to_dict(self) -> dict:
        return {"options": {"ignore_case": self.ignore_case, "count_numbering": self.count_numbering},
                "summary": dict(self.summary),
                "passages": [p.as_dict() for p in self.passages],
                "changes": [self._row_dict(r) for r in self.rows]}
