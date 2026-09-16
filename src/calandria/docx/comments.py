"""word/comments.xml, commentsExtended.xml, people.xml -> model.Comment, plus the anchor record
the parser fills from document.xml. Comments are read like note bodies (the same _blocks); the
extended part joins threading (paraIdParent) and the resolved state (done) by w14:paraId."""
from __future__ import annotations

from dataclasses import dataclass

from ..model import Comment
from .ns import wq, w14q, w15q

# w14:paraId lives on <w:p>; capture it while reading a comment's paragraphs.
PARA_ID = w14q("paraId")


@dataclass
class CommentAnchor:
    start: tuple | None = None    # (Paragraph, raw_offset)
    end: tuple | None = None
    ref: tuple | None = None


def read_comments(pkg, ctx) -> dict[str, Comment]:
    """id -> Comment. Empty when there is no comments part. `ctx.in_part` must be True so a stray
    sectPr inside a comment never adds a section (as for notes)."""
    from .parser import _blocks       # local import: parser imports this module's CommentAnchor
    root = pkg.xml("word/comments.xml")
    if root is None:
        return {}
    ex = pkg.xml("word/commentsExtended.xml")
    parent_by: dict[str, str] = {}
    done: set[str] = set()
    if ex is not None:
        for el in ex.iter(w15q("commentEx")):
            pid = el.get(w15q("paraId"))
            if pid is None:
                continue
            if el.get(w15q("paraIdParent")):
                parent_by[pid] = el.get(w15q("paraIdParent"))
            if el.get(w15q("done")) in ("1", "true"):
                done.add(pid)
    out: dict[str, Comment] = {}
    for el in root.iter(wq("comment")):
        cid = el.get(wq("id"))
        if cid is None:
            continue
        para_ids = [p.get(PARA_ID) or "" for p in el.findall(wq("p"))]
        ctx.pending_break = False
        paras = _blocks(el, ctx)
        ctx.pending_break = False
        parent = parent_by.get(para_ids[0]) if para_ids else None
        is_done = any(pid in done for pid in para_ids)
        out[cid] = Comment(cid, el.get(wq("author")) or "", el.get(wq("initials")) or "",
                           el.get(wq("date")) or "", paras, para_ids, parent, is_done)
    return out
