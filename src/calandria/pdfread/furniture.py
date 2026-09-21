"""What is on the page but not in the document's flow: headers, footers and page numbers (found
by repeating at the same height across pages), and footnote zones (small text under Word's short
rule). Nothing here is compared in this release; it is taken out so that it cannot pollute the
body, and the footnotes go to the notes stream."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import replace

from ..model import collapse_ws
from .grid import TOL
from .types import Line, PageLines

BAND = 0.14
SAME_HEIGHT = 0.006           # of the page height
NOTE_ZONE_TOP = 0.35          # a separator sits below this share of the page height
SEP_MIN, SEP_MAX = 0.15, 0.45  # of the page width; longer is a continuation separator
SMALL = 0.95                  # note text is smaller than this share of the body size
_DIGITS = re.compile(r"\d+")
# A real (if permissive) roman numeral: thousands, hundreds, tens, units, each in its own place,
# and never empty (the lookahead rules out "civil", "vivid", "mimic", "dill" -- words made only of
# the letters i v x l c d m but not in numeral order/grouping). "mix" is a real numeral (1009) and
# is accepted as one.
_ROMAN = r"(?=[ivxlcdm])m{0,3}(?:cm|cd|d?c{0,3})(?:xc|xl|l?x{0,3})(?:ix|iv|v?i{0,3})"
_PAGENUM = re.compile(rf"^(page ?)?[-–— ]*(#|{_ROMAN})[-–— ]*((of|/) ?(#|{_ROMAN}))?$")
_NOTE_START = re.compile(r"^\s*(\d{1,3})[.)]?(\s+|$)")


def _signature(text: str) -> str:
    sig = _DIGITS.sub("#", collapse_ws(text)).lower()
    return "#" if _PAGENUM.match(sig) else sig


def _in_band(pg: PageLines, ln: Line) -> bool:
    top, bottom = BAND * pg.height, (1 - BAND) * pg.height
    if ln.cell is not None:
        g = pg.grids[ln.cell[0]]
        return g.y1 < top or g.y0 > bottom
    return ln.y < top or ln.y > bottom


def _outer_half(pg: PageLines, ln: Line) -> bool:
    """The half of the band nearer the page edge, where a page number actually sits. The inner
    half reaches into the text area, so a line there needs the same repetition as any other
    signature before it counts as furniture."""
    half = BAND / 2 * pg.height
    return ln.y < half or ln.y > pg.height - half


def find_furniture(pages: list[PageLines]) -> set[tuple[int, int]]:
    n = len(pages)
    # Two pages are enough to repeat against; only a single page has nothing to repeat against.
    # (The same document saved twice can paginate differently, and a header must not survive in the
    # shorter copy only because it had one page fewer to repeat on.)
    need = 3 if n >= 4 else 2 if n >= 2 else None
    found: set[tuple[int, int]] = set()
    seen: dict[str, list[tuple[float, int, int]]] = {}
    # A running header never also appears in the middle of a page, but a numbered clause does, and
    # blanking its digits makes every clause one signature; without this the clause that lands in
    # the band at each page top repeats there and is stripped out of the body. Counted rather than
    # merely seen, because one stray copy of a header's words in the text is not evidence that the
    # words are body text: a signature is body text only where it is mostly body text.
    mid: Counter = Counter()
    banded: Counter = Counter()
    for pg in pages:
        for ln in pg.lines:
            (banded if _in_band(pg, ln) else mid)[_signature(ln.text)] += 1
    for pi, pg in enumerate(pages):
        for li, ln in enumerate(pg.lines):
            if not _in_band(pg, ln):
                continue
            sig = _signature(ln.text)
            if sig == "#" and _outer_half(pg, ln):
                found.add((pi, li))
            elif sig and mid[sig] <= banded[sig]:
                seen.setdefault(sig, []).append((ln.y / pg.height, pi, li))
    if need is None:
        return found
    for items in seen.values():
        items.sort()
        cluster = [items[0]]
        for it in items[1:] + [None]:
            if it is not None and it[0] - cluster[-1][0] <= SAME_HEIGHT:
                cluster.append(it)
                continue
            if len({pi for _h, pi, _li in cluster}) >= need:
                found.update((pi, li) for _h, pi, li in cluster)
            cluster = [it] if it is not None else []
    return found


def _separator(pg: PageLines, pi: int, skip: set, left: float, body_size: float) -> tuple[float, bool] | None:
    rules = sorted((s for s in pg.segs if s.horizontal), key=lambda s: s.y0)
    for s in rules:
        rel = s.length / pg.width
        if s.y0 < NOTE_ZONE_TOP * pg.height or rel < SEP_MIN or abs(s.x0 - left) > body_size:
            continue
        if any(g.x0 - TOL <= s.x0 and s.x1 <= g.x1 + TOL and g.y0 - TOL <= s.y0 <= g.y1 + TOL for g in pg.grids):
            continue
        if any(g.y1 > s.y0 for g in pg.grids):
            continue
        below = [ln for li, ln in enumerate(pg.lines) if (pi, li) not in skip and ln.y > s.y0]
        if below and all(ln.cell is None and ln.size < SMALL * body_size for ln in below):
            return s.y0, rel > SEP_MAX
    return None


def _number(ln: Line, last: int | None) -> int | None:
    """The note number a line starts with. A superscript number always counts; a plain one only
    when it is the next number, so a wrapped line starting '12 months' stays in its note."""
    first = ln.spans[0]
    if first.sup and first.text.strip().isdigit():
        return int(first.text)
    m = _NOTE_START.match(ln.text)
    if m and (last is None or int(m.group(1)) == last + 1):
        return int(m.group(1))
    return None


def _strip_number(ln: Line) -> Line:
    spans = list(ln.spans)
    m = _NOTE_START.match(spans[0].text) or re.match(r"^\s*\d{1,3}\s*", spans[0].text)
    spans[0] = replace(spans[0], text=spans[0].text[m.end():] if m else spans[0].text)
    spans = [s for s in spans if s.text]
    if spans:
        spans[0] = replace(spans[0], text=spans[0].text.lstrip())
    return replace(ln, spans=[s for s in spans if s.text])


def collect_notes(pages: list[PageLines], skip: set, left: float, body_size: float):
    notes: dict[int, list[Line]] = {}
    taken: set[tuple[int, int]] = set()
    last: int | None = None
    for pi, pg in enumerate(pages):
        sep = _separator(pg, pi, skip, left, body_size)
        if sep is None:
            continue
        y, _continuation = sep
        for li, ln in enumerate(pg.lines):
            if (pi, li) in skip or ln.y <= y:
                continue
            n = _number(ln, last)
            if n is not None and n not in notes:
                last = n
                notes[n] = [_strip_number(ln)]
            elif last is not None:
                notes[last].append(ln)
            else:
                continue                      # small print with no note to belong to: leave it in the body
            taken.add((pi, li))
    return notes, taken
