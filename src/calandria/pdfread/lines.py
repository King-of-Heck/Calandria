"""Text runs -> text lines. Runs sharing a baseline are one line, ordered left to right; a
smaller raised run stays on its line as a superscript; gaps become a space or a tab. Every
threshold is a share of the font size."""
from __future__ import annotations

from dataclasses import replace

from .types import Line, Span, TextRun

SAME_LINE = 0.45      # of the larger size: baselines this close are one line
SUP_SIZE = 0.85       # a superscript is smaller than this share of the line's size ...
SUP_RISE = 0.15       # ... and raised by more than this share of it
SPACE_GAP = 0.12      # a word space is 0.22 em in Calibri, 0.25 in Times, 0.28 in Arial; kerning moves far less
TAB_GAP = 2.0


def _half(v: float) -> float:
    return round(v * 2) / 2


def _dedupe(runs: list[TextRun]) -> list[TextRun]:
    out: list[TextRun] = []
    for r in runs:
        if any(o.text == r.text and abs(o.x0 - r.x0) < 0.6 and abs(o.y - r.y) < 0.6 for o in out[-8:]):
            continue
        out.append(r)
    return out


def _dominant(row: list[TextRun]) -> tuple[float, float]:
    """(baseline, size) of the size that covers the most width in the row."""
    width: dict[float, float] = {}
    for r in row:
        if r.text.strip():
            width[_half(r.size)] = width.get(_half(r.size), 0.0) + (r.x1 - r.x0)
    size = max(width, key=lambda z: (width[z], z))
    ys = sorted(r.y for r in row if _half(r.size) == size and r.text.strip())
    return ys[len(ys) // 2], size


def _line(row: list[TextRun], page: int, cell) -> Line:
    y, size = _dominant(row)
    row = sorted(row, key=lambda r: r.x0)
    spans: list[Span] = []
    prev: TextRun | None = None
    for r in row:
        text = r.text
        if prev is not None:
            gap = r.x0 - prev.x1
            spaced = spans[-1].text[-1:].isspace() or text[:1].isspace()
            if gap > TAB_GAP * size:
                spans[-1] = replace(spans[-1], text=spans[-1].text.rstrip())
                text = "\t" + text.lstrip()
            elif gap > SPACE_GAP * size and not spaced:
                text = " " + text
        sup = _half(r.size) < SUP_SIZE * size and r.y < y - SUP_RISE * size
        span = Span(text, r.font, _half(r.size), sup)
        if spans and (spans[-1].font, spans[-1].size, spans[-1].sup) == (span.font, span.size, span.sup):
            spans[-1] = replace(spans[-1], text=spans[-1].text + text)
        else:
            spans.append(span)
        prev = r
    spans[0] = replace(spans[0], text=spans[0].text.lstrip())
    spans[-1] = replace(spans[-1], text=spans[-1].text.rstrip())
    inked = [r for r in row if r.text.strip()]
    return Line(page, inked[0].x0, inked[-1].x1, y, size, [s for s in spans if s.text], cell)


def build_lines(runs: list[TextRun], page: int = 0, cell: tuple | None = None) -> list[Line]:
    rows: list[list[TextRun]] = []
    for r in _dedupe(sorted(runs, key=lambda r: (r.y, r.x0))):
        for row in reversed(rows[-3:]):
            big = max(row, key=lambda t: t.size)
            if abs(r.y - big.y) <= SAME_LINE * max(r.size, big.size):
                row.append(r)
                break
        else:
            rows.append([r])
    lines = [_line(row, page, cell) for row in rows if any(t.text.strip() for t in row)]
    return sorted(lines, key=lambda ln: (ln.y, ln.x0))
