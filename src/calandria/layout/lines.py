"""Measured runs and greedy line breaking on glyph widths.

A line's height follows Word: single spacing is the tallest run's font line height (hhea
ascender - descender + lineGap), "auto" multiplies it, "exact" fixes it, "atLeast" takes the
larger; text is bottom-aligned in the line, so the baseline sits `descent` above the bottom.
Breaking is first-fit on word/whitespace tokens; a word wider than the whole line is split at the
last character that fits (Word's behaviour for an unbreakable word); trailing whitespace never
counts toward a line's width or its justification gaps.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..model import WS_CHARS
from .pieces import Piece

_TOKEN = re.compile(f"[^{WS_CHARS}]+|[{WS_CHARS}]+")
_WS = re.compile(f"^[{WS_CHARS}]+$")


@dataclass
class Run:
    text: str
    w: float
    piece: Piece
    face: object
    size: float

    @property
    def is_space(self) -> bool:
        return bool(_WS.match(self.text))


@dataclass
class Line:
    runs: list[Run]
    width: float        # natural width, trailing whitespace excluded
    gaps: int           # whitespace runs inside the line (justification stretches these)
    height: float
    ascent: float       # baseline offset from the top of the line


@dataclass
class Spacing:
    rule: str | None = None          # None/"auto" | "exact" | "atLeast"
    multiple: float | None = None    # "auto" multiplier (None = single)
    exact_pt: float | None = None    # fixed height for exact / floor for atLeast


def measure(pieces: list[Piece], fonts, default_font, default_size: float) -> list[Run]:
    out: list[Run] = []
    for p in pieces:
        face = fonts.face(p.font or default_font, p.bold, p.italic)
        size = p.size or default_size
        for tk in _TOKEN.findall(p.text):
            out.append(Run(tk, face.width(tk, size), p, face, size))
    return out


def line_height(runs: list[Run], spacing: Spacing, default_face, default_size: float) -> tuple[float, float]:
    if runs:
        natural = max(r.face.line_height(r.size) for r in runs)
        desc = max(r.face.descent(r.size) for r in runs)
    else:
        natural = default_face.line_height(default_size)
        desc = default_face.descent(default_size)
    h = natural
    if spacing.rule == "exact" and spacing.exact_pt is not None:
        h = spacing.exact_pt
    elif spacing.rule == "atLeast" and spacing.exact_pt is not None:
        h = max(natural, spacing.exact_pt)
    elif spacing.multiple:
        h = natural * spacing.multiple
    return h, h - desc


def _fit_chars(face, size: float, text: str, avail: float) -> int:
    w = 0.0
    for i, ch in enumerate(text):
        cw = face.width(ch, size)
        if w + cw > avail and i > 0:
            return i
        w += cw
    return len(text)


def break_lines(runs: list[Run], first_avail: float, avail: float, spacing: Spacing,
                default_face, default_size: float) -> list[Line]:
    lines: list[Line] = []
    cur: list[Run] = []
    cur_w = 0.0

    def room() -> float:
        return first_avail if not lines else avail

    def close():
        nonlocal cur, cur_w
        while cur and cur[-1].is_space:
            cur.pop()
        h, asc = line_height(cur, spacing, default_face, default_size)
        lines.append(Line(cur, sum(r.w for r in cur), sum(1 for r in cur if r.is_space), h, asc))
        cur, cur_w = [], 0.0

    for run in runs:
        if not cur and run.is_space:
            continue
        if cur and cur_w + run.w > room():
            close()
            if run.is_space:
                continue
        if not cur and run.w > room() and len(run.text) > 1:
            rest = run.text
            while rest:
                n = _fit_chars(run.face, run.size, rest, room())
                part = Run(rest[:n], run.face.width(rest[:n], run.size), run.piece, run.face, run.size)
                cur.append(part)
                cur_w += part.w
                rest = rest[n:]
                if rest:
                    close()
            continue
        cur.append(run)
        cur_w += run.w
    if cur or not lines:
        close()
    return lines
