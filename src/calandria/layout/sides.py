"""The three sides of one comparison: the blackline (final showing markup, today's layout) and
the two clean projections, original and modified. A side layout is the same engine run over the
merged items filtered to that side, with the options that drop the other side's pieces; the
rows keep their index, so every line of a side still says which comparison row it came from."""
from __future__ import annotations

from dataclasses import replace

from ..diff.changes import Comparison
from .merged import Item
from .pieces import LayoutOptions

SIDES = ("blackline", "original", "modified")


def side_options(opts: LayoutOptions) -> LayoutOptions:
    """The options the engine runs with for `opts.side`: the blackline's own; for a side, the
    other side's pieces hidden and no formatting-change ranges (they belong to the blackline).
    On the original side the shared text takes the original document's own character formatting
    (pieces.row_pieces)."""
    if opts.side == "blackline":
        return opts
    if opts.side == "original":
        return replace(opts, show_insertions=False, show_deletions=True, show_formatting=False)
    if opts.side == "modified":
        return replace(opts, show_insertions=True, show_deletions=False, show_formatting=False)
    raise ValueError(f"unknown side {opts.side!r}; expected one of {', '.join(SIDES)}")


def side_items(items: list[Item], cmp: Comparison, side: str) -> list[Item]:
    """The merged items that exist on `side`. Original: the rows with an original paragraph,
    each carrying the original paragraph itself (its own indents, spacing and list marker); the
    revised document's empty paragraphs and inserted rows are not part of it. Modified: the
    revised document's paragraphs (empty ones included) minus the deleted rows. Table items keep
    their table location, so a shared table takes the revised-side table's geometry on every
    side, exactly as the blackline does (see tables.py); only the text is the side's own."""
    if side == "blackline":
        return items
    if side == "original":
        return [replace(it, para=cmp.a_units[it.row.oi].para)
                for it in items if it.row is not None and it.row.oi is not None]
    if side == "modified":
        return [it for it in items if it.row is None or it.row.ni is not None]
    raise ValueError(f"unknown side {side!r}; expected one of {', '.join(SIDES)}")
