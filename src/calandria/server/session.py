"""One comparison held in memory for the viewer: the parsed documents, the current options, the
comparison, its layout, and the payloads the JSON API hands the browser."""
from __future__ import annotations

import os
import threading
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime

from .. import __version__
from ..diff.changes import Comparison
from ..diff.compare import compare
from ..docx.parser import parse_docx
from ..layout.engine import layout
from ..layout.fonts import default_resolver
from ..layout.pages import Layout
from ..layout.pieces import LayoutOptions
from ..pdf.draw import PdfOptions
from ..pdf.report import report_info, report_lines
from ..pdf.rendersets import RENDER_SETS
from ..pdf.writer import REPORTS, render
from ..viewer.svg import render_pages

OPTION_KEYS = ("ignore_case", "count_numbering", "show_equal", "show_insertions", "show_deletions",
               "show_formatting")


@dataclass(frozen=True)
class Options:
    ignore_case: bool = False
    count_numbering: bool = True
    show_equal: bool = True
    show_insertions: bool = True
    show_deletions: bool = True
    show_formatting: bool = True

    def layout_options(self, fonts=None) -> LayoutOptions:
        return LayoutOptions(show_equal=self.show_equal, show_insertions=self.show_insertions,
                             show_deletions=self.show_deletions, show_formatting=self.show_formatting,
                             fonts=fonts)


class BadRequest(ValueError):
    """Input the client got wrong (a 400): an unknown option, rendering set or report placement."""


class NoComparison(LookupError):
    """Nothing is loaded yet (a 409): the pages, the PDF and a relayout need a comparison first."""


class BadDocument(BadRequest):
    """A file that is not a Word document (named in the message)."""


def parse_options(d, base: Options | None = None) -> Options:
    """Booleans by name, merged over `base`; an unknown key or a non-boolean is a BadRequest."""
    if not isinstance(d, dict):
        raise BadRequest("options must be an object")
    bad = sorted(set(d) - set(OPTION_KEYS))
    if bad:
        raise BadRequest("unknown options: " + ", ".join(bad))
    for k, v in d.items():
        if not isinstance(v, bool):
            raise BadRequest(f"option {k} must be true or false")
    return replace(base or Options(), **d)


def check_render(render_set: str, report: str | None = None) -> None:
    if render_set not in RENDER_SETS:
        raise BadRequest(f"unknown rendering set {render_set!r}; available: " + ", ".join(RENDER_SETS))
    if report is not None and report not in REPORTS:
        raise BadRequest(f"unknown report placement {report!r}; expected first, last or none")


def _parse(name: str, data: bytes):
    try:
        return parse_docx(data)
    except Exception as e:
        raise BadDocument(f"{name}: not a Word document ({type(e).__name__})") from e


def change_marks(lay: Layout) -> tuple[dict[int, dict], list[list]]:
    """(anchors, marks). anchors[cid] = {"page", "top"} of the line that starts the change (the
    first line carrying one of its runs when no line starts it); marks = [page, top, height,
    [cids]] for every line and every changed table row carrying change numbers (the highlight)."""
    anchors: dict[int, dict] = {}
    marks: list[list] = []
    for pg in lay.pages:
        for ln in pg.lines:
            cids = sorted({g.cid for g in ln.runs + ln.marker if g.cid is not None} | set(ln.cid_starts))
            if not cids:
                continue
            marks.append([pg.number, round(ln.top, 2), round(ln.height, 2), cids])
            for c in ln.cid_starts:
                anchors.setdefault(c, {"page": pg.number, "top": round(ln.top, 2)})
        for row in pg.table_rows:
            if row.cids:
                marks.append([pg.number, round(row.y, 2), round(row.h, 2), sorted(set(row.cids))])
    for page, top, _h, cids in marks:
        for c in cids:
            anchors.setdefault(c, {"page": page, "top": top})
    return anchors, marks


def _stem(name: str) -> str:
    return os.path.splitext(os.path.basename(name))[0]


class Session:
    def __init__(self, fonts=None, clock=None):
        self.fonts = fonts                      # a FontResolver / FakeResolver; None = system fonts, resolved once
        self._clock = clock or datetime.now
        self.lock = threading.Lock()            # the app serializes every API call through it
        self.last_seen = time.monotonic()
        self.a_name = self.b_name = None
        self.a_doc = self.b_doc = None
        self.options = Options()
        self.cmp: Comparison | None = None
        self.layout: Layout | None = None
        self.when: datetime | None = None

    @property
    def loaded(self) -> bool:
        return self.layout is not None

    def touch(self) -> None:
        self.last_seen = time.monotonic()

    def state(self) -> dict:
        names = {"original": self.a_name, "modified": self.b_name} if self.loaded else None
        return {"version": __version__, "loaded": self.loaded, "names": names}

    # -- loading and layout -----------------------------------------------------------------
    def load(self, a_name: str, a_bytes: bytes, b_name: str, b_bytes: bytes,
             options: Options | None = None) -> None:
        """Nothing is committed until the new pair has compared AND laid out, so a bad file or a
        failure part way leaves the session showing exactly what it was showing before."""
        a, b = _parse(a_name, a_bytes), _parse(b_name, b_bytes)
        self._commit(a_name, b_name, a, b, options or self.options)

    def relayout(self, options: Options) -> None:
        if self.a_doc is None:
            raise NoComparison("no comparison loaded")
        self._commit(self.a_name, self.b_name, self.a_doc, self.b_doc, options)

    def _commit(self, a_name: str, b_name: str, a_doc, b_doc, options: Options) -> None:
        if self.fonts is None:
            self.fonts = default_resolver()
        when = self._clock()
        cmp = compare(a_doc, b_doc, ignore_case=options.ignore_case,
                      count_numbering=options.count_numbering)
        lay = layout(cmp, options.layout_options(self.fonts))
        self.a_name, self.b_name, self.a_doc, self.b_doc = a_name, b_name, a_doc, b_doc
        self.options, self.when, self.cmp, self.layout = options, when, cmp, lay

    def _need(self) -> None:
        if not self.loaded:
            raise NoComparison("no comparison loaded")

    def _info(self, render_set: str, when: datetime | None = None):
        return report_info(self.cmp, self.a_name, self.b_name, render_set, when or self.when)

    # -- payloads ---------------------------------------------------------------------------
    def pages(self, render_set: str = "Standard", change_bars: bool = True) -> dict:
        self._need()
        check_render(render_set)
        return {"render_set": render_set, "change_bars": change_bars,
                "pages": render_pages(self.layout, render_set, change_bars, self.fonts),
                "report_lines": report_lines(self._info(render_set))}

    def payload(self, render_set: str = "Standard", change_bars: bool = True) -> dict:
        self._need()
        anchors, marks = change_marks(self.layout)
        d = self.cmp.to_dict()
        return {"names": {"original": self.a_name, "modified": self.b_name},
                "options": asdict(self.options), "summary": d["summary"], "changes": d["changes"],
                "page_count": self.layout.page_count, "anchors": anchors, "marks": marks,
                "render_sets": list(RENDER_SETS),
                "render_set_styles": {k: v.to_dict() for k, v in RENDER_SETS.items()},
                **self.pages(render_set, change_bars)}

    def pdf(self, render_set: str = "Standard", change_bars: bool = True, report: str = "last") -> tuple[bytes, str]:
        """(PDF bytes, a file name for the download)."""
        self._need()
        check_render(render_set, report)
        now = self._clock()
        opts = PdfOptions(render_set=render_set, change_bars=change_bars, report=report, fonts=self.fonts, now=now)
        data, _ = render(self.layout, self._info(render_set, now), opts)
        return data, f"{_stem(self.a_name)} vs {_stem(self.b_name)} redline.pdf"
