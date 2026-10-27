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
# DRAWN_SPACE_GAP: where the text draws its word spaces as characters, a gap must be this wide to be
# a space it left out. Word's ExportAsFixedFormat draws every letter on its own with adjustments of up
# to 0.21 em between the letters of a word (measured over a 198-page contract: 3,500 gaps at 0.11,
# a tail to 0.21), and its undrawn word gaps start at 0.36; its Save As PDF keeps them under 0.08.
DRAWN_SPACE_GAP = 0.3
TAB_GAP = 2.0
SAME_SPOT = 0.05      # of the font size: the same text this close to an earlier run is that run drawn again (fake bold)


def _half(v: float) -> float:
    return round(v * 2) / 2


def _dedupe(runs: list[TextRun]) -> list[TextRun]:
    out: list[TextRun] = []
    for r in runs:
        # A duplicate is drawn right after its original, so a short trailing window is enough to
        # catch it; this keeps the scan linear instead of comparing against every run seen so far.
        if any(o.text == r.text and abs(o.x0 - r.x0) < SAME_SPOT * r.size and abs(o.y - r.y) < SAME_SPOT * r.size
               for o in out[-8:]):
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


def _raised(row: list[TextRun]) -> set[int]:
    """ids of the runs that are superscripts over the row's largest text: smaller and raised above
    its baseline. Measured against the largest size, not the one covering most width, so a footnote
    mark wider than the glyph it sits on (a 6.5 pt "97" on a 10 pt placeholder bullet) is still one."""
    inked = [r for r in row if r.text.strip()]
    if not inked:
        return set()
    top = max(_half(r.size) for r in inked)
    ys = sorted(r.y for r in inked if _half(r.size) == top)
    base = ys[len(ys) // 2]
    return {id(r) for r in inked if _half(r.size) < SUP_SIZE * top and r.y < base - SUP_RISE * top}


def _line(row: list[TextRun], page: int, cell, space_gap: float = SPACE_GAP) -> Line:
    raised = _raised(row)
    y, size = _dominant([r for r in row if id(r) not in raised] or row)
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
            elif gap > space_gap * size and not spaced:
                text = " " + text
        sup = id(r) in raised or (_half(r.size) < SUP_SIZE * size and r.y < y - SUP_RISE * size)
        span = Span(text, r.font, _half(r.size), sup)
        if spans and (spans[-1].font, spans[-1].size, spans[-1].sup) == (span.font, span.size, span.sup):
            spans[-1] = replace(spans[-1], text=spans[-1].text + text)
        else:
            spans.append(span)
        prev = r
    spans[0] = replace(spans[0], text=spans[0].text.lstrip())
    spans[-1] = replace(spans[-1], text=spans[-1].text.rstrip())
    inked = [r for r in row if r.text.strip()]
    # The right end is the ink's: Word draws the spaces after a sentence's full stop, which would
    # put a paragraph's last line past the margin and make a justified line look ragged.
    ends_spaced = row[-1].text[-1:].isspace()     # the PDF drew a space after the last word
    return Line(page, inked[0].x0, inked[-1].ink_end, y, size, [s for s in spans if s.text], cell, ends_spaced)


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
    # The text draws its spaces when any run of it holds one between characters or on its own.
    drawn = any(" " in r.text.strip() or (r.text and not r.text.strip()) for r in runs)
    gap = DRAWN_SPACE_GAP if drawn else SPACE_GAP
    lines = [_line(row, page, cell, gap) for row in rows if any(t.text.strip() for t in row)]
    return sorted(lines, key=lambda ln: (ln.y, ln.x0))
