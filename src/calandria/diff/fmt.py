"""Formatting-only differences between two equal-text paragraphs (uncounted changes)."""
from __future__ import annotations

from dataclasses import dataclass

from .chars import FmtSpan

_ARROW = "→"


@dataclass
class FmtRange:
    s: int
    e: int
    desc: str


def _num(z) -> str:
    if z is None:
        return "null"
    z = float(z)
    return str(int(z)) if z.is_integer() else repr(z)


def _str(f) -> str:
    return "null" if f is None else str(f)


def fmt_desc(a: FmtSpan, b: FmtSpan) -> str:
    d = []
    if a.b != b.b:
        d.append("bold " + ("added" if b.b else "removed"))
    if a.i != b.i:
        d.append("italic " + ("added" if b.i else "removed"))
    if a.u != b.u:
        d.append("underline " + ("added" if b.u else "removed"))
    if a.f != b.f:
        d.append(f"font {_str(a.f)} {_ARROW} {_str(b.f)}")
    if a.z != b.z:
        d.append(f"size {_num(a.z)} {_ARROW} {_num(b.z)}")
    if a.clr != b.clr:
        d.append("colour " + ("#" + a.clr if a.clr else "default") + f" {_ARROW} "
                 + ("#" + b.clr if b.clr else "default"))
    return "; ".join(d)


class RangeCursor:
    """Walks a list of sorted, non-overlapping (s, e) ranges as queried positions ascend.

    `.at(pos)` never restarts the scan: it only advances past ranges whose end is at or before
    `pos`, so a caller that probes strictly ascending positions gets O(ranges) total work instead
    of O(positions * ranges).
    """

    __slots__ = ("_items", "_idx")

    def __init__(self, items):
        self._items = items
        self._idx = 0

    def at(self, pos: int):
        items, idx = self._items, self._idx
        n = len(items)
        while idx < n and items[idx].e <= pos:
            idx += 1
        self._idx = idx
        if idx < n and items[idx].s <= pos:
            return items[idx]
        return None


def fmt_diff(a: list[FmtSpan], b: list[FmtSpan]) -> list[FmtRange]:
    end = max(a[-1].e if a else 0, b[-1].e if b else 0)
    out: list[FmtRange] = []
    run: FmtRange | None = None
    a_cur, b_cur = RangeCursor(a), RangeCursor(b)
    for pos in range(end):
        av, bv = a_cur.at(pos), b_cur.at(pos)
        if av is None or bv is None or av.same_fmt(bv):
            if run:
                out.append(run)
                run = None
            continue
        desc = fmt_desc(av, bv)
        if run and run.desc == desc and run.e == pos:
            run.e = pos + 1
        else:
            if run:
                out.append(run)
            run = FmtRange(pos, pos + 1, desc)
    if run:
        out.append(run)
    return out
