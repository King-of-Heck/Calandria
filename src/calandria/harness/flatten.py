"""Project the tree onto SorkWhare's flat paragraph records for the parity harness."""
from __future__ import annotations

import re

from ..model import Document, Paragraph, Table, iter_paragraphs

# SorkWhare 1.16.0.html, extractStructured (~line 503-506): "Heading ONLY from an explicit
# Heading N / Title style." styleId "Title" (any case) is a hardcoded special case; otherwise
# the style's own NAME is tried first ("heading 2"), falling back to the styleId itself
# ("Heading2") -- the id fallback works even when the style isn't defined in styles.xml at
# all. w:outlineLvl is parsed into the reference's style map but is never consulted for this
# field, so it must not be consulted here either -- that is the whole point of this
# projection existing separately from the model's Word-semantics outline_level.
_TITLE_STYLE = re.compile(r"^Title$", re.I)
_HEADING_NAME = re.compile(r"heading\s*(\d)", re.I)
_HEADING_ID = re.compile(r"Heading(\d)", re.I)


def _heading(pr) -> int | None:
    sid = pr.style_id
    if not sid:
        return None
    if _TITLE_STYLE.match(sid):
        return 1
    m = (_HEADING_NAME.search(pr.style_name) if pr.style_name else None) or _HEADING_ID.search(sid)
    return min(6, int(m.group(1))) if m else None


_WS_CHAR = re.compile(r"\s")


def _bold_runs(p: Paragraph) -> list[list[int]]:
    """Bold character ranges [start, end) over the paragraph's collapsed text.

    Mirrors the reference engine's construction (extractStructured, ~lines 460-472): every
    character carries its run's bold flag; whitespace becomes a single space; a space that
    collapses into the preceding one contributes its bold flag to the survivor (bold is OR-ed,
    so a space between two bold words stays bold); leading and trailing spaces are dropped.
    The resulting indices are aligned with `Paragraph.text`.
    """
    coll: list[list] = []
    for run in p.runs:
        bold = run.props.bold
        for ch in run.text:
            c = " " if _WS_CHAR.match(ch) else ch
            if c == " " and coll and coll[-1][0] == " ":
                coll[-1][1] = coll[-1][1] or bold
                continue
            coll.append([c, bold])
    start = 0
    end = len(coll)
    while start < end and coll[start][0] == " ":
        start += 1
    while end > start and coll[end - 1][0] == " ":
        end -= 1
    coll = coll[start:end]
    out: list[list[int]] = []
    run_start = -1
    for k, (_c, bold) in enumerate(coll):
        if bold:
            if run_start < 0:
                run_start = k
        elif run_start >= 0:
            out.append([run_start, k])
            run_start = -1
    if run_start >= 0:
        out.append([run_start, len(coll)])
    return out


def _rec(p: Paragraph, tbl) -> dict:
    pr = p.props
    return {
        "text": p.text,
        "marker": p.num.marker if p.num else "",
        "isNumbered": p.num is not None,
        "ilvl": p.num.ilvl if p.num else 0,
        "styleId": pr.style_id,
        "align": pr.align,
        "indLeftPt": pr.ind_left_pt,
        "indHangingPt": pr.ind_hanging_pt,
        "indFirstLinePt": pr.ind_first_line_pt,
        "spaceBeforePt": pr.space_before_pt,
        "spaceAfterPt": pr.space_after_pt,
        "lineSpacing": pr.line_spacing,
        "lineExactPt": pr.line_exact_pt,
        "keepNext": pr.keep_next,
        "keepLines": pr.keep_lines,
        "pageBreakBefore": pr.page_break_before,
        "contextualSpacing": pr.contextual_spacing,
        "heading": _heading(pr),
        "boldRuns": _bold_runs(p),
        "tbl": tbl,
    }


def flatten(doc: Document) -> list[dict]:
    out, ti = [], 0
    for b in doc.blocks:
        if isinstance(b, Paragraph):
            if not b.is_empty:
                out.append(_rec(b, None))
        elif isinstance(b, Table):
            cols = len(b.grid_pt) or max((len(r.cells) for r in b.rows), default=0)
            for ri, row in enumerate(b.rows):
                for ci, cell in enumerate(row.cells):
                    for p in iter_paragraphs(cell.blocks):
                        if not p.is_empty:
                            out.append(_rec(p, {"ti": ti, "ri": ri, "ci": ci, "cols": cols}))
            ti += 1
    return out
