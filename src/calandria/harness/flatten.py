"""Project the tree onto SorkWhare's flat paragraph records for the parity harness."""
from __future__ import annotations

from ..model import Document, Paragraph, Table


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
        "keepNext": pr.keep_next,
        "keepLines": pr.keep_lines,
        "pageBreakBefore": pr.page_break_before,
        "contextualSpacing": pr.contextual_spacing,
        "heading": None if pr.outline_level is None else pr.outline_level + 1,
        "tbl": tbl,
    }


def _cell_paras(blocks):
    for b in blocks:
        if isinstance(b, Paragraph):
            yield b
        elif isinstance(b, Table):
            for row in b.rows:
                for cell in row.cells:
                    yield from _cell_paras(cell.blocks)


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
                    for p in _cell_paras(cell.blocks):
                        if not p.is_empty:
                            out.append(_rec(p, {"ti": ti, "ri": ri, "ci": ci, "cols": cols}))
            ti += 1
    return out
