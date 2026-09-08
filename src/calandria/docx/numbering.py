"""numbering.xml and list-marker resolution with Word semantics."""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..model import NumInfo
from .ns import wq, wval, twips_to_pt

BULLETS = ["\u2022", "\u25e6", "\u25aa", "\u2023", "\u00b7"]  # SorkWhare's BULLETS glyphs, verbatim
_ROMAN = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"), (50, "l"),
          (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
_PH = re.compile(r"%(\d+)")


def _roman(n: int) -> str:
    out = ""
    for v, s in _ROMAN:
        while n >= v:
            out += s
            n -= v
    return out or str(n)


def _letters(n: int, upper: bool) -> str:
    out = ""
    while n > 0:
        n -= 1
        out = chr((65 if upper else 97) + n % 26) + out
        n //= 26
    return out


def fmt_num(n: int, fmt: str) -> str:
    if fmt == "lowerLetter":
        return _letters(n, False)
    if fmt == "upperLetter":
        return _letters(n, True)
    if fmt == "lowerRoman":
        return _roman(n)
    if fmt == "upperRoman":
        return _roman(n).upper()
    if fmt == "decimalZero":
        return f"0{n}" if n < 10 else str(n)
    return str(n)


@dataclass
class Level:
    fmt: str = "decimal"
    text: str = "%1."
    start: int = 1
    p_style: str | None = None
    ind_left_pt: float | None = None
    ind_hanging_pt: float | None = None
    align: str | None = None


class Numbering:
    def __init__(self):
        self.num_to_abs: dict[int, int] = {}
        self.abstract: dict[int, dict[int, Level]] = {}
        self.overrides: dict[int, dict[int, int]] = {}
        self.style_to_num: dict[str, tuple[int, int]] = {}

    @classmethod
    def parse(cls, root) -> "Numbering":
        n = cls()
        if root is None:
            return n
        for ab in root.iter(wq("abstractNum")):
            aid = ab.get(wq("abstractNumId"))
            if aid is None:
                continue
            levels: dict[int, Level] = {}
            for lv in ab.iter(wq("lvl")):
                il = lv.get(wq("ilvl"))
                if il is None:
                    continue
                ind = lv.find(f"{wq('pPr')}/{wq('ind')}")
                start = wval(lv.find(wq("start")), "1")
                levels[int(il)] = Level(
                    fmt=wval(lv.find(wq("numFmt")), "decimal"),
                    text=wval(lv.find(wq("lvlText")), "%1."),
                    start=int(start) if start.isdigit() else 1,
                    p_style=wval(lv.find(wq("pStyle"))),
                    ind_left_pt=twips_to_pt(ind.get(wq("left"))) if ind is not None else None,
                    ind_hanging_pt=twips_to_pt(ind.get(wq("hanging"))) if ind is not None else None,
                    align=wval(lv.find(f"{wq('pPr')}/{wq('jc')}")) or wval(lv.find(wq("lvlJc"))),
                )
            n.abstract[int(aid)] = levels
        for num in root.iter(wq("num")):
            nid, aid = num.get(wq("numId")), wval(num.find(wq("abstractNumId")))
            if nid is None or aid is None:
                continue
            n.num_to_abs[int(nid)] = int(aid)
            for ov in num.iter(wq("lvlOverride")):
                il, so = ov.get(wq("ilvl")), wval(ov.find(wq("startOverride")))
                if il is not None and so is not None and so.isdigit():
                    n.overrides.setdefault(int(nid), {})[int(il)] = int(so)
        for nid, aid in n.num_to_abs.items():
            for il, lv in n.abstract.get(aid, {}).items():
                if lv.p_style and lv.p_style not in n.style_to_num:
                    n.style_to_num[lv.p_style] = (nid, il)
        return n

    def level(self, num_id: int, ilvl: int):
        aid = self.num_to_abs.get(num_id)
        if aid is None:
            return None
        return self.abstract.get(aid, {}).get(ilvl)


class NumberingCounter:
    """Per-abstract-list cascading counters (Word semantics)."""

    def __init__(self, numbering: Numbering):
        self.n = numbering
        self._counts: dict[int, dict[int, int]] = {}   # abstractId -> ilvl -> current value
        self._override_used: set[tuple[int, int]] = set()

    def next(self, num_id: int, ilvl: int) -> NumInfo | None:
        lv = self.n.level(num_id, ilvl)
        if lv is None:
            return None
        if lv.fmt == "bullet":
            return NumInfo(num_id, ilvl, BULLETS[min(ilvl, len(BULLETS) - 1)], True)
        aid = self.n.num_to_abs[num_id]
        counts = self._counts.setdefault(aid, {})
        so = self.n.overrides.get(num_id, {}).get(ilvl)
        if so is not None and (num_id, ilvl) not in self._override_used:
            self._override_used.add((num_id, ilvl))
            counts[ilvl] = so - 1
        counts[ilvl] = counts.get(ilvl, lv.start - 1) + 1
        for deeper in [k for k in counts if k > ilvl]:
            del counts[deeper]
        levels = self.n.abstract[aid]

        def sub(m):
            li = int(m.group(1)) - 1
            l2 = levels.get(li, Level())
            # Ancestor references render as plain decimal; only the placeholder
            # for the level being rendered uses that level's own numFmt.
            fmt = l2.fmt if li == ilvl else "decimal"
            return fmt_num(counts.get(li, l2.start), fmt)

        return NumInfo(num_id, ilvl, _PH.sub(sub, lv.text), False)
