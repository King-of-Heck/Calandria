"""document.xml -> model.Document."""
from __future__ import annotations

from ..model import (Cell, Document, ParaProps, Paragraph, Row, Run, RunProps, Section, Table)
from .ns import wq, wval, wbool, twips_to_pt
from .numbering import Numbering, NumberingCounter
from .package import Package
from .styles import Styles, read_ppr, read_rpr

_TRANSPARENT = {wq("hyperlink"), wq("smartTag"), wq("sdt"), wq("sdtContent"), wq("fldSimple"),
                wq("ins"), wq("customXml"), wq("dir"), wq("bdo")}
_SKIP = {wq("del"), wq("moveFrom"), wq("pPr"), wq("rPr"), wq("proofErr"), wq("bookmarkStart"),
         wq("bookmarkEnd"), wq("commentRangeStart"), wq("commentRangeEnd")}


class _Ctx:
    def __init__(self, styles: Styles, numbering: Numbering):
        self.styles = styles
        self.numbering = numbering
        self.counter = NumberingCounter(numbering)
        self.pending_break = False
        self.sections: list[Section] = []


def parse_docx(src) -> Document:
    # The whole tree is built before the context manager exits, so nothing reads the zip
    # afterwards -- and a path input does not leave a file handle open behind the caller.
    with Package.open(src) as pkg:
        return parse_package(pkg)


def parse_package(pkg: Package) -> Document:
    styles = Styles.parse(pkg.xml("word/styles.xml"))
    numbering = Numbering.parse(pkg.xml("word/numbering.xml"))
    ctx = _Ctx(styles, numbering)
    root = pkg.xml("word/document.xml")
    body = root.find(wq("body")) if root is not None else None
    blocks = _blocks(body, ctx) if body is not None else []
    if body is not None:
        sp = body.find(wq("sectPr"))
        if sp is not None:
            ctx.sections.append(_section(sp))
    if not ctx.sections:
        ctx.sections.append(Section())
    settings = pkg.xml("word/settings.xml")
    eao = settings is not None and wbool(settings.find(wq("evenAndOddHeaders")))
    return Document(blocks, ctx.sections, default_font=styles.defaults["font"],
                    default_size_pt=styles.defaults["size_pt"], even_and_odd=eao)


def _blocks(parent, ctx: _Ctx) -> list:
    out = []
    for el in parent:
        if el.tag == wq("p"):
            out.append(_paragraph(el, ctx))
        elif el.tag == wq("tbl"):
            out.append(_table(el, ctx))
        elif el.tag in _TRANSPARENT:
            out.extend(_blocks(el, ctx))
    return out


def _runs(el, ctx: _Ctx, para_rpr: dict, out: list[Run], state: dict):
    """Collect runs under el into out. state['text_seen'] tracks page-break placement."""
    for child in el:
        tag = child.tag
        if tag in _SKIP:
            continue
        if tag == wq("r"):
            props = _run_props(child.find(wq("rPr")), para_rpr, ctx)
            buf = []
            for x in child:
                if x.tag == wq("t") or x.tag == wq("delText"):
                    buf.append(x.text or "")
                elif x.tag == wq("tab"):
                    buf.append("\t")
                elif x.tag == wq("br"):
                    if x.get(wq("type")) == "page":
                        if state["text_seen"] or "".join(buf).strip():
                            ctx.pending_break = True          # applies to the NEXT paragraph
                        else:
                            state["break_before"] = True      # applies to THIS paragraph
                    else:
                        buf.append("\n")
                elif x.tag == wq("noBreakHyphen"):
                    buf.append("-")
                elif x.tag == wq("sym"):
                    buf.append("\ufffd")
                elif x.tag == wq("cr"):
                    buf.append("\n")
            text = "".join(buf)
            if text.strip():
                state["text_seen"] = True
            if text:
                out.append(Run(text, props))
        elif tag in _TRANSPARENT:
            _runs(child, ctx, para_rpr, out, state)


def _run_props(rpr, para_rpr: dict, ctx: _Ctx) -> RunProps:
    d = dict(para_rpr)
    own = read_rpr(rpr)
    d.update(own)
    return RunProps(bold=bool(own.get("bold", False)),   # bold: run level only (SorkWhare invariant)
                    italic=bool(d.get("italic", False)), underline=bool(d.get("underline", False)),
                    font=d.get("font") or ctx.styles.defaults["font"],
                    size_pt=d.get("size_pt") or ctx.styles.defaults["size_pt"], color=d.get("color"))


def _paragraph(el, ctx: _Ctx) -> Paragraph:
    ppr = el.find(wq("pPr"))
    style_id = wval(ppr.find(wq("pStyle"))) if ppr is not None else None
    # resolved_ppr(None) (no pStyle) resolves through Word's default paragraph style chain,
    # not an empty chain -- see Styles._chain.
    style_ppr = ctx.styles.resolved_ppr(style_id)
    own = read_ppr(ppr)
    merged = dict(style_ppr)
    merged.update(own)
    para_rpr = ctx.styles.resolved_rpr(style_id)

    # ---- Numbering: paragraph's own numPr, else the style chain's own numPr (already folded
    # into `merged` above), else a level that names this style via its own <w:pStyle>.
    num = None
    lv = None
    num_id, ilvl = merged.get("num_id"), merged.get("ilvl", 0)
    if num_id is None and style_id in ctx.numbering.style_to_num:
        num_id, ilvl = ctx.numbering.style_to_num[style_id]
    if num_id:
        num = ctx.counter.next(num_id, ilvl)
        lv = ctx.numbering.level(num_id, ilvl)
        if lv is not None:
            if "ind_left_pt" not in merged and lv.ind_left_pt is not None:
                merged["ind_left_pt"] = lv.ind_left_pt
            if "ind_hanging_pt" not in merged and lv.ind_hanging_pt is not None:
                merged["ind_hanging_pt"] = lv.ind_hanging_pt

    # ---- Spacing (w:spacing), resolved PER ATTRIBUTE: paragraph's own -> the numbering
    # LEVEL's own <w:pPr>/<w:spacing> -> the style chain (or the default paragraph style
    # when the paragraph names no pStyle, already folded into `style_ppr` above) ->
    # docDefaults' <w:pPrDefault>. spaceBefore/spaceAfter fall back independently; the
    # "line" group (line_spacing/line_rule/line_exact_pt) is taken atomically from whichever
    # source is the first to set a line rule at all -- these three always arrive together
    # from one <w:spacing> element and describe mutually exclusive line-height concepts
    # (a multiplier for "auto", a fixed point height for "exact"/"atLeast"), so they must
    # never be picked from two different sources.
    level_ppr = lv.ppr if lv is not None else {}
    defaults = ctx.styles.defaults
    space_before_pt = own.get("space_before_pt")
    if space_before_pt is None:
        space_before_pt = level_ppr.get("space_before_pt")
    if space_before_pt is None:
        space_before_pt = style_ppr.get("space_before_pt")
    if space_before_pt is None:
        space_before_pt = defaults.get("space_before_pt")
    space_after_pt = own.get("space_after_pt")
    if space_after_pt is None:
        space_after_pt = level_ppr.get("space_after_pt")
    if space_after_pt is None:
        space_after_pt = style_ppr.get("space_after_pt")
    if space_after_pt is None:
        space_after_pt = defaults.get("space_after_pt")
    line_spacing = line_rule = line_exact_pt = None
    for src in (own, level_ppr, style_ppr, defaults):
        if src.get("line_rule") is not None:
            line_spacing, line_rule, line_exact_pt = (
                src.get("line_spacing"), src.get("line_rule"), src.get("line_exact_pt"))
            break
    merged["space_before_pt"], merged["space_after_pt"] = space_before_pt, space_after_pt
    for key, val in (("line_spacing", line_spacing), ("line_rule", line_rule), ("line_exact_pt", line_exact_pt)):
        if val is None:
            merged.pop(key, None)
        else:
            merged[key] = val

    # `heading` (Title/Heading-N style detection) is a projection concern, not a model one --
    # see harness/flatten.py. The model keeps Word semantics: outline_level is w:outlineLvl
    # from the paragraph's own pPr, else the style chain, else None (already resolved into
    # `merged` by the dict merge above; never derived from styleId/style name here).
    outline = merged.get("outline_level")
    st = ctx.styles.get(style_id)
    style_name = st.name if st is not None else None

    # A pending break travels from paragraph to paragraph. Snapshot what arrived from
    # earlier paragraphs, then let _runs discover (and reset) whatever this paragraph's
    # OWN content contributes going forward -- the two must never be conflated, or a
    # break that lands after this paragraph's own text (which is destined for the NEXT
    # paragraph) gets misattributed to this one instead.
    had_pending = ctx.pending_break
    ctx.pending_break = False

    runs: list[Run] = []
    state = {"text_seen": False, "break_before": False}
    _runs(el, ctx, para_rpr, runs, state)

    props = ParaProps(style_id=style_id, align=merged.get("align", "left"),
                      ind_left_pt=merged.get("ind_left_pt", 0.0), ind_hanging_pt=merged.get("ind_hanging_pt", 0.0),
                      ind_first_line_pt=merged.get("ind_first_line_pt", 0.0),
                      space_before_pt=merged.get("space_before_pt"), space_after_pt=merged.get("space_after_pt"),
                      line_spacing=merged.get("line_spacing"), line_rule=merged.get("line_rule"),
                      line_exact_pt=merged.get("line_exact_pt"),
                      keep_next=merged.get("keep_next", False), keep_lines=merged.get("keep_lines", False),
                      page_break_before=merged.get("page_break_before", False),
                      contextual_spacing=merged.get("contextual_spacing", False), outline_level=outline,
                      style_name=style_name)
    p = Paragraph(runs, props, num)

    if p.is_empty:
        # Empty: no distinction between "before" and "after" text (there is none), so any
        # break found here (or still unresolved from before) simply keeps traveling. A break
        # that only reaches _runs from a skipped subtree (e.g. inside w:del) never sets
        # break_before or pending_break in the first place, so it correctly does not travel.
        ctx.pending_break = had_pending or state["break_before"] or ctx.pending_break
    else:
        if state["break_before"] or had_pending:
            p.props.page_break_before = True
        # else: ctx.pending_break already holds whatever this paragraph's own trailing
        # break (if any) set during _runs, correctly destined for the NEXT paragraph.

    if ppr is not None:
        sp = ppr.find(wq("sectPr"))
        if sp is not None:
            section = _section(sp)
            ctx.sections.append(section)
            # A section break stored on a paragraph takes effect AFTER that paragraph: the
            # following paragraph starts a new page. "continuous" flows on, and "nextColumn"
            # only starts a new column, so neither breaks the page.
            if section.type not in ("continuous", "nextColumn"):
                ctx.pending_break = True
    return p


def _table(el, ctx: _Ctx) -> Table:
    grid = [twips_to_pt(g.get(wq("w"))) or 0.0 for g in el.findall(f"{wq('tblGrid')}/{wq('gridCol')}")]
    rows = []
    for tr in el.findall(wq("tr")):
        cells = []
        for tc in tr.findall(wq("tc")):
            tcpr = tc.find(wq("tcPr"))
            span, vm = 1, None
            if tcpr is not None:
                gs = tcpr.find(wq("gridSpan"))
                if gs is not None:
                    span = int(wval(gs, "1"))
                v = tcpr.find(wq("vMerge"))
                if v is not None:
                    vm = "continue" if wval(v) == "continue" or wval(v) is None else "restart"
            cells.append(Cell(_blocks(tc, ctx), grid_span=span, v_merge=vm))
        rows.append(Row(cells))
    ctx.pending_break = False   # a break inside a cell never escapes the table (SorkWhare 1.3.1)
    return Table(rows, grid_pt=grid)


def _section(sp) -> Section:
    s = Section()
    sz = sp.find(wq("pgSz"))
    if sz is not None:
        w, h = twips_to_pt(sz.get(wq("w"))), twips_to_pt(sz.get(wq("h")))
        if w:
            s.page_w_pt = round(w, 2)
        if h:
            s.page_h_pt = round(h, 2)
    mar = sp.find(wq("pgMar"))
    if mar is not None:
        for attr, key in (("top", "margin_top_pt"), ("right", "margin_right_pt"), ("bottom", "margin_bottom_pt"),
                          ("left", "margin_left_pt"), ("header", "header_pt"), ("footer", "footer_pt")):
            v = twips_to_pt(mar.get(wq(attr)))
            if v is not None:
                setattr(s, key, abs(v))
    s.title_pg = wbool(sp.find(wq("titlePg")))
    s.type = wval(sp.find(wq("type")), "nextPage") or "nextPage"
    return s
