"""Read a text PDF into the Document the rest of Calandria compares, lays out and draws.

    extract (pypdf: file structure only) -> grids -> lines -> furniture, footnotes -> paragraphs -> Document

Structure is inferred from geometry alone; see each module for its rules."""
from __future__ import annotations

from ..model import Document
from .build import body_metrics, build_document
from .extract import NO_TEXT, extract_pages, unreadable
from .furniture import collect_notes, find_furniture
from .grid import find_grids
from .lines import build_lines
from .types import PageData, PageLines, PdfRefused


def page_lines(index: int, pd: PageData, pos: int) -> PageLines:
    """One page's lines, each run first bucketed by the grid cell it sits in (or the body), so a
    text line never straddles two cells. `pos` is the page's position among the pages read."""
    grids = find_grids(pd.segs)
    buckets: dict = {}
    for r in pd.runs:
        key = None
        x, y = (r.x0 + r.x1) / 2, r.y - 0.3 * r.size
        for gi, g in enumerate(grids):
            ci = g.cell_at(x, y)
            if ci is not None:
                key = (gi, ci)
                break
        buckets.setdefault(key, []).append(r)
    lines = [ln for key, runs in buckets.items() for ln in build_lines(runs, page=pos, cell=key)]
    lines.sort(key=lambda ln: (ln.y, ln.x0))
    return PageLines(index, pd.width, pd.height, lines, grids, pd.segs)


def parse_pdf(data: bytes, progress=None) -> Document:
    raw = extract_pages(data, progress)
    good = [(i, p) for i, p in enumerate(raw) if not unreadable(p)]
    if sum(p.chars for _i, p in good) == 0:
        raise PdfRefused(NO_TEXT)
    skipped = tuple(i + 1 for i, p in enumerate(raw) if unreadable(p))
    pages = [page_lines(i, p, pos) for pos, (i, p) in enumerate(good)]
    skip = find_furniture(pages)
    left, _right, body_size = body_metrics(pages, skip)
    notes, note_lines = collect_notes(pages, skip, left, body_size)
    return build_document(pages, skip | note_lines, notes, len(raw), skipped)
