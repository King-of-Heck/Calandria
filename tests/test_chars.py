import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from calandria.diff.chars import FmtSpan, bold_runs, char_fmt, fmt_spans
from calandria.diff.units import walk
from calandria.model import WS_CHARS
from calandria.testing.makedocx import DOC, make_docx
from calandria.docx.parser import parse_docx
from calandria.model import Paragraph, ParaProps, Run, RunProps


def _p(*runs):
    return Paragraph([Run(t, RunProps(**pr)) for t, pr in runs], ParaProps())


def test_spans_cover_the_paragraph_text_exactly():
    p = _p(("  Bold ", {"bold": True}), (" \tplain\n", {}), ("x  ", {}))
    spans = fmt_spans(p)
    assert p.text == "Bold plain x"
    assert spans[0].s == 0 and spans[-1].e == len(p.text)
    assert all(a.e == b.s for a, b in zip(spans, spans[1:]))


def test_bold_runs_or_on_collapsed_space():
    # A space between two bold words stays bold; a bold space swallowed by a plain one bolds it.
    p = _p(("Bold ", {"bold": True}), (" word", {"bold": True}))
    assert bold_runs(p) == [[0, 9]]
    p2 = _p(("plain ", {}), (" bold", {"bold": True}))
    assert bold_runs(p2) == [[5, 10]]     # collapsed space took the second run's bold


def test_bold_runs_empty_and_trailing():
    assert bold_runs(_p(("no bold", {}))) == []
    assert bold_runs(_p(("ab", {}), ("cd", {"bold": True}))) == [[2, 4]]


def test_fmt_spans_are_maximal_and_aligned():
    p = _p(("Hello ", {"font": "Calibri", "size_pt": 11.0}),
           ("World", {"font": "Calibri", "size_pt": 11.0, "italic": True}),
           ("!", {"font": "Calibri", "size_pt": 11.0, "italic": True}))
    assert fmt_spans(p) == [
        FmtSpan(0, 6, False, False, False, "Calibri", 11.0, None),
        FmtSpan(6, 12, False, True, False, "Calibri", 11.0, None)]


def test_fmt_spans_keep_first_space_props_but_or_bold():
    p = _p(("a ", {"italic": True}), (" b", {"bold": True}))
    spans = fmt_spans(p)
    assert spans[1] == FmtSpan(1, 2, True, True, False, None, None, None)   # the collapsed space
    assert spans[2] == FmtSpan(2, 3, True, False, False, None, None, None)


def test_same_fmt_ignores_position():
    a = FmtSpan(0, 1, True, False, False, "A", 10.0, "ff0000")
    b = FmtSpan(5, 9, True, False, False, "A", 10.0, "ff0000")
    assert a.same_fmt(b) and not a.same_fmt(FmtSpan(5, 9, True, False, False, "A", 10.0, None))


# -- v2.4.3: the per-run walk against the per-character walk it replaced -------------------------
# The old code, kept here as the oracle: one Ch per character, spans merged afterwards.

_WS_CHAR = re.compile(f"[{WS_CHARS}]")


@dataclass
class _Ch:
    c: str
    b: bool
    i: bool
    u: bool
    f: str | None
    z: float | None
    clr: str | None


def _old_collapsed_chars(p):
    coll = []
    for run in p.runs:
        pr = run.props
        for ch in run.text:
            c = " " if _WS_CHAR.match(ch) else ch
            if c == " " and coll and coll[-1].c == " ":
                coll[-1].b = coll[-1].b or pr.bold
                continue
            coll.append(_Ch(c, pr.bold, pr.italic, pr.underline, pr.font, pr.size_pt, pr.color))
    start, end = 0, len(coll)
    while start < end and coll[start].c == " ":
        start += 1
    while end > start and coll[end - 1].c == " ":
        end -= 1
    return coll[start:end]


def _old_bold_runs(p):
    out, run_start = [], -1
    coll = _old_collapsed_chars(p)
    for k, ch in enumerate(coll):
        if ch.b:
            if run_start < 0:
                run_start = k
        elif run_start >= 0:
            out.append([run_start, k])
            run_start = -1
    if run_start >= 0:
        out.append([run_start, len(coll)])
    return out


def _old_fmt_spans(p):
    out = []
    for k, ch in enumerate(_old_collapsed_chars(p)):
        cur = FmtSpan(k, k + 1, ch.b, ch.i, ch.u, ch.f, ch.z, ch.clr)
        if out and out[-1].same_fmt(cur) and out[-1].e == k:
            out[-1] = FmtSpan(out[-1].s, k + 1, cur.b, cur.i, cur.u, cur.f, cur.z, cur.clr)
        else:
            out.append(cur)
    return out


def _same_as_old(p):
    bold, spans = char_fmt(p)
    assert (bold, spans) == (_old_bold_runs(p), _old_fmt_spans(p)), p.runs
    assert "".join(ch.c for ch in _old_collapsed_chars(p)) == p.text
    if spans:
        assert spans[0].s == 0 and spans[-1].e == len(p.text)
        assert all(a.e == b.s and not a.same_fmt(b) for a, b in zip(spans, spans[1:]))
    else:
        assert p.text == ""


EDGE_CASES = [
    [],
    [("", {})],
    [("   ", {"bold": True})],
    [("  ", {}), ("\t", {"bold": True}), (" ", {"italic": True})],
    [(" lead", {"bold": True})],
    [("  ", {"italic": True}), ("word", {})],
    [("trail ", {}), ("  ", {"bold": True})],
    [("a ", {}), (" ", {"bold": True})],
    [("a ", {"italic": True}), (" b", {"bold": True})],
    [("a ", {"bold": True, "italic": True}), (" ", {"italic": True}), (" b", {"bold": True})],
    [("a ", {}), (" ", {"bold": True}), (" b", {})],
    [("ab ", {}), (" ", {"bold": True}), ("c", {"bold": True})],
    [("a", {"bold": True}), (" ", {}), ("b", {"bold": True})],
    [("a", {"bold": True}), (" ", {}), (" b", {"bold": True})],
    [("x", {"font": "A"}), ("y", {"font": "A"}), ("z", {"font": "B"}), (" ", {"font": "B"}), ("w", {"font": "A"})],
    [("one\u00a0two", {}), ("\u2003three", {"underline": True})],
    [("bold", {"bold": True}), ("bold", {"bold": True, "size_pt": 9.0}), ("plain", {})],
    [("a\n\n", {}), ("\r\nb", {"bold": True}), ("  c", {"bold": True}), ("\t", {}), ("d", {"color": "ff0000"})],
]


@pytest.mark.parametrize("runs", EDGE_CASES)
def test_per_run_walk_matches_the_per_character_oracle(runs):
    _same_as_old(_p(*runs))


def _corpus_paragraphs():
    corpus = Path(__file__).resolve().parent / "corpus"
    for path in sorted(corpus.glob("*.docx")) if corpus.is_dir() else []:
        try:
            doc = parse_docx(path)
        except Exception:
            continue
        for p, _loc in walk(doc):
            yield p


def test_per_run_walk_matches_the_oracle_on_the_corpus():
    n = 0
    for p in _corpus_paragraphs():
        _same_as_old(p)
        n += 1
    if n == 0:
        pytest.skip("no corpus documents on this machine")


def test_per_run_walk_matches_the_oracle_on_a_generated_document():
    body = "".join(
        f'<w:p><w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">  Clause {k} </w:t></w:r>'
        f'<w:r><w:rPr><w:i/></w:rPr><w:t xml:space="preserve"> says\t</w:t></w:r>'
        f'<w:r><w:t xml:space="preserve"> that {k * 7} </w:t></w:r></w:p>' for k in range(40))
    doc = parse_docx(make_docx({"word/document.xml": DOC(body)}))
    ps = [p for p, _ in walk(doc)]
    assert len(ps) == 40
    for p in ps:
        _same_as_old(p)
