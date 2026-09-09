"""Render the change model in the reference engine's HTML row shape for the parity gate.

Only the harness speaks HTML; the change model itself is plain data. The escaping and wrapper
rules here reproduce the reference's row html byte for byte, which is what lets the gate compare
whole rows instead of a lossy projection.
"""
from __future__ import annotations

from ..diff.changes import Comparison, Row
from ..diff.chars import FmtSpan
from ..diff.fmt import FmtRange, RangeCursor
from ..diff.inline import Seg

_DEFAULT_SPAN = FmtSpan(0, 0, False, False, False, None, None, None)


def esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_html(segs: list[Seg]) -> str:
    html = ""
    k = 0
    while k < len(segs):
        m = segs[k].m
        inner = ""
        while k < len(segs) and segs[k].m == m:
            s = segs[k]
            inner += "<b>" + esc(s.t) + "</b>" if s.b else esc(s.t)
            k += 1
        if m == "del":
            html += "<del>" + inner + "</del>"
        elif m == "ins":
            html += "<ins>" + inner + "</ins>"
        else:
            html += inner
    return html


def fmt_wrap(text: str, spans: list[FmtSpan], ranges: list[FmtRange]) -> str:
    span_cur = RangeCursor(spans)
    diff_cur = RangeCursor(ranges)

    out = ""
    i = 0
    while i < len(text):
        sp = span_cur.at(i) or _DEFAULT_SPAN
        d = diff_cur.at(i)
        j = i + 1
        while j < len(text):
            s2 = span_cur.at(j) or sp
            d2 = diff_cur.at(j)
            if not s2.same_fmt(sp):
                break
            if (d.desc if d else None) != (d2.desc if d2 else None):
                break
            j += 1
        inner = esc(text[i:j])
        if sp.b:
            inner = "<b>" + inner + "</b>"
        if sp.i:
            inner = "<i>" + inner + "</i>"
        if sp.u:
            inner = "<u>" + inner + "</u>"
        if d:
            inner = '<span class="fmtchg" title="' + esc(d.desc).replace('"', "&quot;") + '">' + inner + "</span>"
        out += inner
        i = j
    return out


def row_record(cmp: Comparison, row: Row) -> dict:
    u = cmp.unit_for(row)
    html = fmt_wrap(u.text, u.fmt_spans, row.fmt_ranges) if row.fmt_changed else render_html(row.segments)
    return {
        "type": row.type, "cid": row.cid, "cat": row.cat, "oi": row.oi, "ni": row.ni, "html": html,
        "numChanged": row.num_changed, "oldMarker": row.old_marker,
        "fmtChanged": row.fmt_changed, "fmtDescs": [r.desc for r in row.fmt_ranges] or None,
        "tbl": u.loc.as_dict() if u.loc else None,
    }


def records(cmp: Comparison) -> list[dict]:
    return [row_record(cmp, r) for r in cmp.rows]
