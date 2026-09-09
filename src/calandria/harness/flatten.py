"""Project the tree onto SorkWhare's flat paragraph records for the parity harness."""
from __future__ import annotations

import re

from ..diff.units import Unit, units
from ..model import Document

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


def _rec(u: Unit) -> dict:
    pr = u.para.props
    p = u.para
    return {
        "text": u.text,
        "marker": u.marker,
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
        "boldRuns": u.bold_runs,
        "tbl": {"ti": u.loc.ti, "ri": u.loc.ri, "ci": u.loc.ci, "cols": u.loc.cols} if u.loc else None,
    }


def flatten(doc: Document) -> list[dict]:
    return [_rec(u) for u in units(doc)]
