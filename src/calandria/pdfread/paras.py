"""Text lines -> paragraphs. The rules never look at which page a line is on except to skip the
one rule (vertical gap) that a page break makes meaningless, so a paragraph reads the same however
the PDF happened to paginate. Every threshold is a share of the font size or the line pitch."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, replace

from .types import Line, Span

MARKER = re.compile(r"^(\(?\d{1,3}(\.\d{1,3})*[.)]?|\(?[A-Za-z][.)]|\(?[ivxlcdm]{1,7}[.)]"
                    r"|[•·▪●◦])(?=[ \t])")
TOL = 0.3             # of the font size: positions closer than this are the same position
GAP = 1.25            # of the prevailing pitch: a wider line gap is a paragraph gap
SIZE_CHANGE = 0.05
PITCH_STEP = 0.05
DEFAULT_PITCH = 1.2


def _half(v: float) -> float:
    return round(v * 2) / 2


def prevailing_pitch(lines: list[Line]) -> float:
    seen: Counter = Counter()
    for p, l in zip(lines, lines[1:]):
        if p.page == l.page and p.cell == l.cell and l.y > p.y and abs(p.size - l.size) < 0.26:
            seen[round((l.y - p.y) / l.size / PITCH_STEP)] += 1
    if not seen:
        return DEFAULT_PITCH
    top = max(seen.values())
    return round(min(k for k, n in seen.items() if n == top) * PITCH_STEP, 2)


@dataclass
class PdfPara:
    lines: list[Line]
    spans: list[Span]
    align: str
    ind_left: float
    ind_first: float
    ind_hanging: float
    space_after: float | None


def _edge(cur: list[Line], nxt: Line, right: float, tol: float) -> float:
    ends = sorted((l.x1 for l in cur), reverse=True)
    if len(ends) >= 2 and ends[0] - ends[1] <= tol:
        return ends[0]
    if abs(cur[-1].x1 - nxt.x1) <= tol:
        return max(cur[-1].x1, nxt.x1)
    return right


def _ended_short(cur: list[Line], nxt: Line, right: float, tol: float) -> bool:
    words = nxt.text.split()
    if not words:
        return False
    first = (nxt.x1 - nxt.x0) * len(words[0]) / max(1, len(nxt.text))
    return _edge(cur, nxt, right, tol) - cur[-1].x1 > 1.2 * first + 0.5 * nxt.size


def _breaks(cur: list[Line], nxt: Line, right: float, pitch: float) -> bool:
    prev = cur[-1]
    size = max(prev.size, nxt.size)
    tol = TOL * size
    same_page = prev.page == nxt.page
    if same_page and nxt.y <= prev.y:
        return True
    if abs(nxt.size - prev.size) > SIZE_CHANGE * size:
        return True
    if same_page and (nxt.y - prev.y) / size > pitch * GAP:
        return True
    if _ended_short(cur, nxt, right, tol):
        return True
    if len(cur) >= 2 and abs(nxt.x0 - cur[1].x0) > tol:
        return True
    m = MARKER.match(nxt.text)
    if m and (nxt.text[m.end():m.end() + 1] == "\t" or (len(cur) >= 2 and nxt.x0 < cur[1].x0 - tol)):
        return True
    return False


def _join(lines: list[Line]) -> list[Span]:
    out: list[Span] = []
    for i, ln in enumerate(lines):
        spans = list(ln.spans)
        if i and out and spans:
            last = out[-1].text
            if last.endswith("­"):
                out[-1] = replace(out[-1], text=last[:-1])
            elif last.endswith("-") and len(last) >= 2 and last[-2].isalpha():
                pass
            elif not last[-1:].isspace():
                out[-1] = replace(out[-1], text=last + " ")
        for s in spans:
            if out and (out[-1].font, out[-1].size, out[-1].sup) == (s.font, s.size, s.sup):
                out[-1] = replace(out[-1], text=out[-1].text + s.text)
            else:
                out.append(s)
    return [replace(s, text=s.text.replace("­", "")) for s in out]


def _align(lines: list[Line], left: float, right: float, tol: float) -> str:
    mid = (left + right) / 2
    if all(abs((l.x0 + l.x1) / 2 - mid) <= tol and l.x0 - left > tol and right - l.x1 > tol for l in lines):
        return "center"
    if all(right - l.x1 <= tol and l.x0 - left > tol for l in lines):
        return "right"
    body = lines[:-1]
    if len(body) >= 2 and max(l.x1 for l in body) - min(l.x1 for l in body) <= tol:
        return "justify"
    return "left"


def _para(lines: list[Line], nxt: Line | None, left: float, right: float, pitch: float) -> PdfPara:
    size = lines[0].size
    tol = TOL * size
    align = _align(lines, left, right, tol)
    ind_left = ind_first = ind_hanging = 0.0
    if align in ("left", "justify"):
        first_x = lines[0].x0
        cont_x = lines[1].x0 if len(lines) >= 2 else first_x
        ind_left = max(0.0, _half(cont_x - left))
        if first_x - cont_x > tol:
            ind_first = _half(first_x - cont_x)
        elif cont_x - first_x > tol:
            ind_hanging = _half(cont_x - first_x)
    space_after = None
    if nxt is not None and nxt.page == lines[-1].page and nxt.y > lines[-1].y:
        space_after = max(0.0, _half(nxt.y - lines[-1].y - pitch * max(size, nxt.size)))
    return PdfPara(lines, _join(lines), align, ind_left, ind_first, ind_hanging, space_after)


def build_paragraphs(lines: list[Line], left: float, right: float, pitch: float) -> list[PdfPara]:
    groups: list[list[Line]] = []
    for ln in lines:
        if groups and not _breaks(groups[-1], ln, right, pitch):
            groups[-1].append(ln)
        else:
            groups.append([ln])
    return [_para(g, groups[i + 1][0] if i + 1 < len(groups) else None, left, right, pitch)
            for i, g in enumerate(groups)]
