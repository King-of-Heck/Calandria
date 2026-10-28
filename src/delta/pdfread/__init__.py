"""Read a text PDF into the Document the rest of Delta compares, lays out and draws.

    extract (pypdf: file structure only) -> grids -> lines -> borderless tables -> furniture, footnotes
        -> paragraphs -> Document

Structure is inferred from geometry alone; see each module for its rules. A compared pair is read
in two steps: `read_pdf` each side up to its lines (the slow part, cached by the app), then `finish`
both together, so the rules that read the document's style judge the pair as one."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from ..model import Document
from .borderless import find_borderless
from .build import body_metrics, build_document, pair_style
from .extract import NO_TEXT, extract_pages, unreadable
from .furniture import collect_notes, find_furniture
from .grid import find_grids
from .lines import build_lines
from .types import PageData, PageLines, PdfRefused


def page_lines(index: int, pd: PageData, pos: int) -> PageLines:
    """One page's lines, each run first bucketed by the grid cell it sits in (or the body), so a
    text line never straddles two cells; body lines laid out as a borderless table become its
    cells. `pos` is the page's position among the pages read."""
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
    lines = [ln for key, runs in buckets.items() if key is not None for ln in build_lines(runs, page=pos, cell=key)]
    borderless, body = find_borderless(build_lines(buckets.get(None, []), page=pos), first=len(grids))
    grids += borderless              # after the ruled grids, whose cell lines already point at them
    lines += body
    lines.sort(key=lambda ln: (ln.y, ln.x0))
    return PageLines(index, pd.width, pd.height, lines, grids, pd.segs)


@dataclass(frozen=True)
class PdfReading:
    """A PDF read as far as it can be without the other side of the pair: its lines, with the
    header/footer lines and the footnote lines set aside."""
    pages: list[PageLines]
    skip: set                        # (page, line) not in the body: furniture and footnote lines
    notes: dict = field(default_factory=dict)
    total_pages: int = 0
    skipped: tuple = ()              # 1-based numbers of the pages with no readable text
    source_kind: ClassVar[str] = "pdf"


def read_pdf(data: bytes, progress=None) -> PdfReading:
    raw = extract_pages(data, progress)
    good = [(i, p) for i, p in enumerate(raw) if not unreadable(p)]
    if sum(p.chars for _i, p in good) == 0:
        raise PdfRefused(NO_TEXT)
    skipped = tuple(i + 1 for i, p in enumerate(raw) if unreadable(p))
    pages = [page_lines(i, p, pos) for pos, (i, p) in enumerate(good)]
    skip = find_furniture(pages)
    left, _right, body_size = body_metrics(pages, skip)   # a second call happens inside build_document,
    # with `skip | note_lines` (footnote lines left out too) — a different `skip` set on purpose, not a duplicate to collapse
    notes, note_lines = collect_notes(pages, skip, left, body_size)
    return PdfReading(pages, skip | note_lines, notes, len(raw), skipped)


def finish(*readings: PdfReading) -> list[Document]:
    """The Documents of one PDF or of a compared pair, every side read by the pair's one Style."""
    style = pair_style([(r.pages, r.skip) for r in readings])
    return [build_document(r.pages, r.skip, r.notes, r.total_pages, r.skipped, style) for r in readings]


def parse_pdf(data: bytes, progress=None) -> Document:
    """One PDF on its own. Two PDFs to compare go through `finish` together."""
    (doc,) = finish(read_pdf(data, progress))
    return doc
