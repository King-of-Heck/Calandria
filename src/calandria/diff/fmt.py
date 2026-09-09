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


def _at(spans: list[FmtSpan], pos: int) -> FmtSpan | None:
    for sp in spans:
        if sp.s <= pos < sp.e:
            return sp
    return None


def fmt_diff(a: list[FmtSpan], b: list[FmtSpan]) -> list[FmtRange]:
    end = max(a[-1].e if a else 0, b[-1].e if b else 0)
    out: list[FmtRange] = []
    run: FmtRange | None = None
    for pos in range(end):
        av, bv = _at(a, pos), _at(b, pos)
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
