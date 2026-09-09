from calandria.diff.chars import FmtSpan, bold_runs, collapsed_chars, fmt_spans
from calandria.model import Paragraph, ParaProps, Run, RunProps


def _p(*runs):
    return Paragraph([Run(t, RunProps(**pr)) for t, pr in runs], ParaProps())


def test_collapsed_chars_reproduce_paragraph_text():
    p = _p(("  Bold ", {"bold": True}), (" \tplain\n", {}), ("x  ", {}))
    coll = collapsed_chars(p)
    assert "".join(ch.c for ch in coll) == p.text == "Bold plain x"


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
