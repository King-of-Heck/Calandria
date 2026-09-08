"""styles.xml: document defaults and the paragraph-style chain."""
from __future__ import annotations

from dataclasses import dataclass, field

from .ns import wq, wval, wbool, half_pt, twips_to_pt


def read_rpr(rpr) -> dict:
    """Run properties from a <w:rPr>; only keys that are set are returned."""
    out: dict = {}
    if rpr is None:
        return out
    b = rpr.find(wq("b"))
    if b is not None:
        out["bold"] = wbool(b)
    i = rpr.find(wq("i"))
    if i is not None:
        out["italic"] = wbool(i)
    u = rpr.find(wq("u"))
    if u is not None:
        out["underline"] = wval(u, "single") != "none"
    fonts = rpr.find(wq("rFonts"))
    if fonts is not None and fonts.get(wq("ascii")):
        out["font"] = fonts.get(wq("ascii"))
    sz = rpr.find(wq("sz"))
    if sz is not None and half_pt(wval(sz)) is not None:
        out["size_pt"] = half_pt(wval(sz))
    color = rpr.find(wq("color"))
    if color is not None:
        v = wval(color)
        out["color"] = None if v is None or v.lower() == "auto" else v.lower()
    return out


def read_ppr(ppr) -> dict:
    """Paragraph properties from a <w:pPr>; only keys that are set are returned."""
    out: dict = {}
    if ppr is None:
        return out
    jc = ppr.find(wq("jc"))
    if jc is not None:
        v = wval(jc, "left")
        out["align"] = {"both": "justify", "start": "left", "end": "right"}.get(v, v)
    ind = ppr.find(wq("ind"))
    if ind is not None:
        for attr, key in (("left", "ind_left_pt"), ("start", "ind_left_pt"),
                          ("hanging", "ind_hanging_pt"), ("firstLine", "ind_first_line_pt")):
            v = twips_to_pt(ind.get(wq(attr)))
            if v is not None:
                out[key] = v
    sp = ppr.find(wq("spacing"))
    if sp is not None:
        before, after = twips_to_pt(sp.get(wq("before"))), twips_to_pt(sp.get(wq("after")))
        if before is not None:
            out["space_before_pt"] = before
        if after is not None:
            out["space_after_pt"] = after
        line = sp.get(wq("line"))
        rule = sp.get(wq("lineRule")) or "auto"
        if line is not None:
            try:
                n = float(line)
                out["line_rule"] = rule
                out["line_spacing"] = n / 240.0 if rule == "auto" else n / 20.0
            except ValueError:
                pass
    for tag, key in (("keepNext", "keep_next"), ("keepLines", "keep_lines"),
                     ("contextualSpacing", "contextual_spacing"), ("pageBreakBefore", "page_break_before")):
        el = ppr.find(wq(tag))
        if el is not None:
            out[key] = wbool(el)
    ol = ppr.find(wq("outlineLvl"))
    if ol is not None and wval(ol) is not None:
        out["outline_level"] = int(wval(ol))
    numpr = ppr.find(wq("numPr"))
    if numpr is not None:
        nid, il = numpr.find(wq("numId")), numpr.find(wq("ilvl"))
        if nid is not None and wval(nid) is not None:
            out["num_id"] = int(wval(nid))
        if il is not None and wval(il) is not None:
            out["ilvl"] = int(wval(il))
    return out


@dataclass
class Style:
    id: str
    name: str = ""
    type: str = "paragraph"
    based_on: str | None = None
    rpr: dict = field(default_factory=dict)
    ppr: dict = field(default_factory=dict)


class Styles:
    def __init__(self):
        self._map: dict[str, Style] = {}
        self.defaults = {"font": None, "size_pt": 11.0, "space_after_pt": None, "line_spacing": None}
        self.style_to_num: dict[str, tuple[int, int]] = {}

    @classmethod
    def parse(cls, root) -> "Styles":
        s = cls()
        if root is None:
            return s
        dd = root.find(wq("docDefaults"))
        if dd is not None:
            r = read_rpr(dd.find(f"{wq('rPrDefault')}/{wq('rPr')}"))
            p = read_ppr(dd.find(f"{wq('pPrDefault')}/{wq('pPr')}"))
            s.defaults = {"font": r.get("font"), "size_pt": r.get("size_pt", 11.0),
                          "space_after_pt": p.get("space_after_pt"), "line_spacing": p.get("line_spacing")}
        for el in root.iter(wq("style")):
            sid = el.get(wq("styleId"))
            if not sid:
                continue
            st = Style(id=sid, name=wval(el.find(wq("name")), ""), type=el.get(wq("type")) or "paragraph",
                       based_on=wval(el.find(wq("basedOn"))),
                       rpr=read_rpr(el.find(wq("rPr"))),      # direct child only: pPr/rPr is the paragraph mark
                       ppr=read_ppr(el.find(wq("pPr"))))
            s._map[sid] = st
        return s

    def get(self, sid):
        return self._map.get(sid) if sid else None

    def _chain(self, sid):
        seen, out = set(), []
        st = self.get(sid)
        while st is not None and st.id not in seen:
            seen.add(st.id)
            out.append(st)
            st = self.get(st.based_on)
        return out  # child first

    def resolved_rpr(self, sid) -> dict:
        out: dict = {}
        for st in reversed(self._chain(sid)):
            out.update(st.rpr)
        return out

    def resolved_ppr(self, sid) -> dict:
        out: dict = {}
        for st in reversed(self._chain(sid)):
            out.update(st.ppr)
        return out
