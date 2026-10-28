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


def _height(pg: PageLines, ln: Line) -> float:
    """Where a band line sits, in points from its own edge of the page (negative from the bottom):
    Word sets a header a fixed distance below the top edge and a footer a fixed distance above the
    bottom one, so a landscape page's footer is at a different share of the page height."""
    return ln.y if ln.y < pg.height / 2 else ln.y - pg.height


def _outer_half(pg: PageLines, ln: Line) -> bool:
    """The half of the band nearer the page edge, where a page number actually sits. The inner
    half reaches into the text area, so a line there needs the same repetition as any other
    signature before it counts as furniture."""
    half = BAND / 2 * pg.height
    return ln.y < half or ln.y > pg.height - half


def _note_text(pg: PageLines) -> set[int]:
    """The lines of footnote text on a page: a line starting with a superscript number, and the
    lines wrapped under it at its size. A note repeated at the same height on several pages (the
    same signature-block note under each signature page) is still a note, not furniture."""
    out: set[int] = set()
    start = prev = None
    for li, ln in enumerate(pg.lines):
        first = ln.spans[0] if ln.spans else None
        if first is not None and first.sup and first.text.strip().isdigit():
            start = prev = ln
            out.add(li)
        elif start is not None and abs(ln.size - start.size) < 0.05 * start.size and ln.y - prev.y <= 2 * ln.size:
            prev = ln
            out.add(li)
        else:
            start = None
    return out


def _running(pages: list[PageLines], cluster: list[tuple[float, int, int]]) -> list[tuple[int, int]]:
    """The (page, line)s of a cluster (one signature at one height) that are a running line: words
    repeated exactly on another page, or words whose one changed number moves with the page ("Schedule
    3 - Page 4" two pages after "Page 2"). Numbered titles that share a signature ("SCHEDULE 2.2(b)",
    "SCHEDULE 2.9(b)": each schedule starts a page under its own) are neither."""
    texts = {(pi, li): collapse_ws(pages[pi].lines[li].text) for _h, pi, li in cluster}
    repeats = Counter(texts.values())
    numbers = {k: [int(d) for d in _DIGITS.findall(t)] for k, t in texts.items()}
    out = []
    for k, t in texts.items():
        if repeats[t] >= 2:
            out.append(k)
            continue
        for o in texts:
            moved = [b - a for a, b in zip(numbers[k], numbers[o]) if a != b]
            if o != k and len(numbers[o]) == len(numbers[k]) and moved == [pages[o[0]].index - pages[k[0]].index]:
                out.append(k)
                break
    return out


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
    once: Counter = Counter()
    for pg in pages:
        for ln in pg.lines:
            (banded if _in_band(pg, ln) else mid)[_signature(ln.text)] += 1
            if _in_band(pg, ln):
                once[collapse_ws(ln.text)] += 1
    # Body text in the band: words found once (a header repeats), as at the top of a page whose
    # text starts at the top margin. Word never sets body text at a header's height.
    opening: list[tuple[float, int]] = []
    for pi, pg in enumerate(pages):
        notes = _note_text(pg)
        for li, ln in enumerate(pg.lines):
            if not _in_band(pg, ln) or li in notes:
                continue
            sig = _signature(ln.text)
            if sig == "#" and _outer_half(pg, ln):
                found.add((pi, li))
            elif sig and mid[sig] <= banded[sig]:
                seen.setdefault(sig, []).append((_height(pg, ln), pi, li))
            if sig != "#" and once[collapse_ws(ln.text)] == 1:
                opening.append((_height(pg, ln), pi))
    if need is None:
        return found
    for items in seen.values():
        items.sort()
        cluster = [items[0]]
        for it in items[1:] + [None]:
            if it is not None and it[0] - cluster[-1][0] <= SAME_HEIGHT * pages[it[1]].height:
                cluster.append(it)
                continue
            running = _running(pages, cluster)
            on = {pi for pi, _li in running}
            if len(on) >= need and not _body_height(pages, cluster, on, opening, need):
                found.update(running)
            cluster = [it] if it is not None else []
    return found


def _body_height(pages: list[PageLines], cluster: list[tuple[float, int, int]], on: set[int],
                 opening: list[tuple[float, int]], need: int) -> bool:
    """Is the cluster's height where the body starts? More pages than the cluster's own hold a
    one-off line there ('SCHEDULE 8.1' over each alternative version of a schedule, at the height
    of every other page's first line of text): then the repeats are titles, not a header."""
    tol = SAME_HEIGHT * max(pg.height for pg in pages)
    lo, hi = cluster[0][0] - tol, cluster[-1][0] + tol
    others = {pi for h, pi in opening if lo <= h <= hi and pi not in on}
    return len(others) >= need and len(others) > len(on)


def _separator(pg: PageLines, pi: int, skip: set, left: float, body_size: float,
               last: int | None = None) -> tuple[float, bool] | None:
    """(y, continuation) of the page's footnote rule. A rule above NOTE_ZONE_TOP is taken only when
    the line under it starts with the next note's raised number: a note long enough to fill most of
    a page (a sample clause set out in a note) pushes its rule that high."""
    rules = sorted((s for s in pg.segs if s.horizontal), key=lambda s: s.y0)
    for s in rules:
        rel = s.length / pg.width
        if rel < SEP_MIN or abs(s.x0 - left) > body_size:
            continue
        if any(g.x0 - TOL <= s.x0 and s.x1 <= g.x1 + TOL and g.y0 - TOL <= s.y0 <= g.y1 + TOL for g in pg.grids):
            continue
        if any(g.y1 > s.y0 for g in pg.grids):
            continue
        below = [ln for li, ln in enumerate(pg.lines) if (pi, li) not in skip and ln.y > s.y0]
        if not below or not all(ln.cell is None and ln.size < SMALL * body_size for ln in below):
            continue
        if s.y0 < NOTE_ZONE_TOP * pg.height:
            first = below[0].spans[0]
            if not (last is not None and first.sup and first.text.strip() == str(last + 1)):
                continue
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
        sep = _separator(pg, pi, skip, left, body_size, last)
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
