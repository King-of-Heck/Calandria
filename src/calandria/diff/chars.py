"""Formatting ranges over a paragraph's collapsed text, one walk per paragraph, run by run.

Whitespace collapses to single spaces and the ends are trimmed exactly as Paragraph.text does, so
the ranges produced here index into that text. A collapsed space keeps the first space's
formatting except bold, which is OR-ed (a space between two bold words is bold). Bold comes from
the run alone: paragraph-style and character-style bold are unresolved by design (see
tests/parity/KNOWN_DIVERGENCES.md).

A run has one formatting, so its non-space text is one span (merged with the span before it when
the formatting is the same); only a collapsed space can differ from its neighbours, when the
bold of a swallowed space is OR-ed into it. Nothing is built per character.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..model import Paragraph, WS_CHARS

_WS_RUN = re.compile(f"[{WS_CHARS}]+")


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


# A span under construction: [s, e, b, i, u, f, z, clr] (mutable; e grows, b can be OR-ed).
_S, _E, _B = 0, 1, 2


def _spans(p: Paragraph) -> list[list]:
    out: list[list] = []
    n = 0                       # collapsed characters so far
    last_space = False          # the last collapsed character is a space

    def put(length: int, fmt: tuple) -> None:
        nonlocal n
        last = out[-1] if out else None
        if last is not None and tuple(last[_B:]) == fmt:
            last[_E] += length
        else:
            out.append([n, n + length, *fmt])
        n += length

    for run in p.runs:
        pr = run.props
        fmt = (pr.bold, pr.italic, pr.underline, pr.font, pr.size_pt, pr.color)
        parts = _WS_RUN.split(run.text)         # words and the whitespace groups between them
        for k, part in enumerate(parts):
            if k:                               # a whitespace group precedes every part but the first
                if n == 0:
                    pass                        # leading whitespace: trimmed
                elif last_space:
                    # swallowed by the space before it: that space keeps its formatting but takes this bold
                    last = out[-1]
                    if pr.bold and not last[_B]:
                        if last[_E] - last[_S] == 1:
                            last[_B] = True
                            if len(out) > 1 and tuple(out[-2][_B:]) == tuple(last[_B:]):
                                out[-2][_E] = last[_E]
                                out.pop()
                        else:
                            last[_E] -= 1
                            out.append([n - 1, n, True, *last[_B + 1:]])
                else:
                    put(1, fmt)
                    last_space = True
            if part:
                put(len(part), fmt)
                last_space = False
    if last_space:                              # trailing whitespace: trimmed
        last = out[-1]
        last[_E] -= 1
        if last[_E] == last[_S]:
            out.pop()
    return out


def char_fmt(p: Paragraph) -> tuple[list[list[int]], list[FmtSpan]]:
    """(bold_runs, fmt_spans) of a paragraph from one walk of its runs."""
    raw = _spans(p)
    bold: list[list[int]] = []
    for sp in raw:
        if sp[_B]:
            if bold and bold[-1][1] == sp[_S]:
                bold[-1][1] = sp[_E]
            else:
                bold.append([sp[_S], sp[_E]])
    return bold, [FmtSpan(*sp) for sp in raw]


def bold_runs(p: Paragraph) -> list[list[int]]:
    """Bold character ranges [start, end) over p.text."""
    return char_fmt(p)[0]


def fmt_spans(p: Paragraph) -> list[FmtSpan]:
    """Maximal formatting-constant runs over p.text, index-aligned with bold_runs."""
    return char_fmt(p)[1]
