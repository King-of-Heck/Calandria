"""The merged document: the revised document in order, empty paragraphs kept, each deleted
paragraph interleaved where it stood -- the order every sink lays out ("final showing markup").
"""
from __future__ import annotations

from dataclasses import dataclass

from ..diff.changes import Comparison, Row
from ..diff.units import Loc, walk
from ..model import Paragraph


@dataclass
class Item:
    para: Paragraph
    loc: Loc | None
    side: str                    # "b" = revised document; "a" = original-only (a deleted row)
    section: int                 # index into doc.sections
    row: Row | None = None       # None for an empty revised paragraph
    row_index: int | None = None


def merged_items(cmp: Comparison) -> list[Item]:
    if cmp.b_doc is None or cmp.a_doc is None:
        raise ValueError("merged_items needs a Comparison from compare(a, b) (documents attached)")
    rows = cmp.rows
    by_ni = {r.ni: k for k, r in enumerate(rows) if r.ni is not None}
    out: list[Item] = []
    state = {"emitted": 0, "section": 0}

    def flush_deleted(upto: int):
        # rows[:upto] precede the revised paragraph about to be emitted; the deleted ones among
        # them that have not been placed yet go here, in row order.
        while state["emitted"] < upto:
            r = rows[state["emitted"]]
            if r.ni is None:
                u = cmp.a_units[r.oi]
                out.append(Item(u.para, u.loc, "a", state["section"], r, state["emitted"]))
            state["emitted"] += 1

    ni = 0
    for para, loc in walk(cmp.b_doc):
        if para.is_empty:
            out.append(Item(para, loc, "b", state["section"]))
        else:
            k = by_ni[ni]
            ni += 1
            flush_deleted(k)
            out.append(Item(para, loc, "b", state["section"], rows[k], k))
            state["emitted"] = max(state["emitted"], k + 1)
        if para.props.section_break:
            state["section"] += 1
    flush_deleted(len(rows))
    return out
