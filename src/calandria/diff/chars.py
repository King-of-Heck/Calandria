"""Per-character formatting over a paragraph's collapsed text.

Whitespace collapses to single spaces and the ends are trimmed exactly as Paragraph.text does, so
the ranges produced here index into that text. A collapsed space keeps the first space's
formatting except bold, which is OR-ed (a space between two bold words is bold). Bold comes from
the run alone: paragraph-style and character-style bold are unresolved by design (see
tests/parity/KNOWN_DIVERGENCES.md).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..model import Paragraph

_WS_CHAR = re.compile(r"\s")


@dataclass
class Ch:
    c: str
    b: bool
    i: bool
    u: bool
    f: str | None
    z: float | None
    clr: str | None


@dataclass(frozen=True)
class FmtSpan:
    s: int
    e: int
    b: bool
    i: bool
    u: bool
    f: str | None
    z: float | None
    clr: str | None

    def same_fmt(self, o: "FmtSpan") -> bool:
        return (self.b == o.b and self.i == o.i and self.u == o.u and self.f == o.f
                and self.z == o.z and self.clr == o.clr)


def collapsed_chars(p: Paragraph) -> list[Ch]:
    coll: list[Ch] = []
    for run in p.runs:
        pr = run.props
        for ch in run.text:
            c = " " if _WS_CHAR.match(ch) else ch
            if c == " " and coll and coll[-1].c == " ":
                coll[-1].b = coll[-1].b or pr.bold
                continue
            coll.append(Ch(c, pr.bold, pr.italic, pr.underline, pr.font, pr.size_pt, pr.color))
    start, end = 0, len(coll)
    while start < end and coll[start].c == " ":
        start += 1
    while end > start and coll[end - 1].c == " ":
        end -= 1
    return coll[start:end]


def bold_runs(p: Paragraph) -> list[list[int]]:
    """Bold character ranges [start, end) over p.text."""
    out: list[list[int]] = []
    run_start = -1
    coll = collapsed_chars(p)
    for k, ch in enumerate(coll):
        if ch.b:
            if run_start < 0:
                run_start = k
        elif run_start >= 0:
            out.append([run_start, k])
            run_start = -1
    if run_start >= 0:
        out.append([run_start, len(coll)])
    return out


def fmt_spans(p: Paragraph) -> list[FmtSpan]:
    """Maximal formatting-constant runs over p.text, index-aligned with bold_runs."""
    out: list[FmtSpan] = []
    for k, ch in enumerate(collapsed_chars(p)):
        cur = FmtSpan(k, k + 1, ch.b, ch.i, ch.u, ch.f, ch.z, ch.clr)
        if out and out[-1].same_fmt(cur) and out[-1].e == k:
            out[-1] = FmtSpan(out[-1].s, k + 1, cur.b, cur.i, cur.u, cur.f, cur.z, cur.clr)
        else:
            out.append(cur)
    return out
