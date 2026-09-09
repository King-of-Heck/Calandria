"""Rendering sets: one data object drives the change styling of every sink (V1, V2)."""
from __future__ import annotations

from dataclasses import asdict, dataclass

EFFECTS = frozenset({"bold", "italic", "underline", "double-underline", "dotted-underline",
                     "strikethrough", "double-strikethrough"})


@dataclass(frozen=True)
class CatStyle:
    color: str                              # 6-hex lower-case
    effects: frozenset = frozenset()
    background: str | None = None           # 6-hex or None (no fill); data only in v2.0.0
    prefix: str = ""                        # data only in v2.0.0 (would change widths)
    suffix: str = ""

    def __post_init__(self):
        bad = set(self.effects) - EFFECTS
        if bad:
            raise ValueError(f"unknown effects: {sorted(bad)}")


@dataclass(frozen=True)
class RenderSet:
    name: str
    insert: CatStyle
    delete: CatStyle
    formatting: CatStyle
    move_from: CatStyle
    move_to: CatStyle
    cell_inserted: str | None = None
    cell_deleted: str | None = None
    cell_merged: str | None = None
    cell_split: str | None = None
    table_moved: str | None = None

    def category(self, mode: str, fmt: bool) -> CatStyle | None:
        """The style of a run by its diff mode (eq | del | ins) and formatting-change flag."""
        if mode == "ins":
            return self.insert
        if mode == "del":
            return self.delete
        return self.formatting if fmt else None

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("insert", "delete", "formatting", "move_from", "move_to"):
            d[k]["effects"] = sorted(d[k]["effects"])
        return d


STANDARD = RenderSet(
    "Standard",
    insert=CatStyle("0000ff", frozenset({"double-underline"})),
    delete=CatStyle("ff0000", frozenset({"strikethrough"})),
    formatting=CatStyle("7c3aed", frozenset({"dotted-underline"})),
    move_from=CatStyle("008000", frozenset({"strikethrough"})),
    move_to=CatStyle("008000", frozenset({"double-underline"})),
    cell_inserted="e6e6fa", cell_deleted="ffdead", cell_merged="008080", cell_split="ff00ff",
    table_moved="ccffcc",
)

BLACK_AND_WHITE = RenderSet(
    "Black and White",
    insert=CatStyle("000000", STANDARD.insert.effects),
    delete=CatStyle("000000", STANDARD.delete.effects),
    formatting=CatStyle("000000", STANDARD.formatting.effects),
    move_from=CatStyle("000000", STANDARD.move_from.effects),
    move_to=CatStyle("000000", STANDARD.move_to.effects),
)

RENDER_SETS: dict[str, RenderSet] = {s.name: s for s in (STANDARD, BLACK_AND_WHITE)}


def render_set(name: str) -> RenderSet:
    try:
        return RENDER_SETS[name]
    except KeyError:
        raise KeyError(f"unknown rendering set {name!r}; available: " + ", ".join(RENDER_SETS)) from None
