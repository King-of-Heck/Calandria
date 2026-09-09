"""The change model: rows in document order, numbered changes, per-category counts.

This is the single object the layout engine, the viewer and the reports consume. It is plain
data (to_dict() is JSON) and carries no rendering.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..model import Document
from .fmt import FmtRange
from .inline import Seg
from .units import Unit

SUMMARY_KEYS = ("insertions", "deletions", "moves", "amendments", "content", "numbering",
                "punctuation", "total", "formatting", "splits", "merges")

_CATEGORY = {"inserted": "insertion", "deleted": "deletion", "changed": "amendment"}


def empty_summary() -> dict:
    return {k: 0 for k in SUMMARY_KEYS}


@dataclass
class Row:
    type: str                       # "equal" | "changed" | "inserted" | "deleted"
    oi: int | None                  # index into the original units
    ni: int | None                  # index into the revised units
    segments: list[Seg]
    cid: int | None = None
    cat: str | None = None          # "content" | "punctuation" on changed rows
    fmt_changed: bool = False
    fmt_ranges: list[FmtRange] = field(default_factory=list)
    num_changed: bool = False
    old_marker: str | None = None

    @property
    def category(self) -> str | None:
        if self.type != "equal":
            return _CATEGORY[self.type]
        if self.num_changed:
            return "numbering"
        if self.fmt_changed:
            return "formatting"
        return None


@dataclass
class Comparison:
    rows: list[Row]
    summary: dict
    a_units: list[Unit]
    b_units: list[Unit]
    ignore_case: bool
    count_numbering: bool
    a_doc: Document | None = None
    b_doc: Document | None = None

    def unit_for(self, row: Row) -> Unit:
        return self.b_units[row.ni] if row.ni is not None else self.a_units[row.oi]

    def _row_dict(self, r: Row) -> dict:
        u = self.unit_for(r)
        loc = {"ti": u.loc.ti, "ri": u.loc.ri, "ci": u.loc.ci, "cols": u.loc.cols} if u.loc else None
        return {
            "type": r.type, "category": r.category, "cid": r.cid, "cat": r.cat,
            "oi": r.oi, "ni": r.ni, "loc": loc, "marker": u.marker, "old_marker": r.old_marker,
            "num_changed": r.num_changed, "fmt_changed": r.fmt_changed,
            "fmt_descs": [x.desc for x in r.fmt_ranges],
            "segments": [{"m": s.m, "t": s.t, "b": s.b} for s in r.segments],
        }

    def to_dict(self) -> dict:
        return {"options": {"ignore_case": self.ignore_case, "count_numbering": self.count_numbering},
                "summary": dict(self.summary),
                "changes": [self._row_dict(r) for r in self.rows]}
