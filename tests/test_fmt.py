from calandria.diff.chars import FmtSpan
from calandria.diff.fmt import FmtRange, fmt_desc, fmt_diff


def _sp(s, e, **kw):
    d = dict(b=False, i=False, u=False, f="Calibri", z=11.0, clr=None)
    d.update(kw)
    return FmtSpan(s, e, **d)


def test_desc_order_and_wording():
    a = _sp(0, 5)
    b = _sp(0, 5, b=True, i=True, u=True, f="Arial", z=12.0, clr="ff0000")
    assert fmt_desc(a, b) == ("bold added; italic added; underline added; font Calibri → Arial; "
                              "size 11 → 12; colour default → #ff0000")
    assert fmt_desc(b, a) == ("bold removed; italic removed; underline removed; font Arial → Calibri; "
                              "size 12 → 11; colour #ff0000 → default")


def test_desc_number_and_null_formatting():
    assert fmt_desc(_sp(0, 1, z=10.5), _sp(0, 1, z=11.0)) == "size 10.5 → 11"
    assert fmt_desc(_sp(0, 1, f=None), _sp(0, 1, f="Arial")) == "font null → Arial"


def test_fmt_diff_no_change():
    assert fmt_diff([_sp(0, 5)], [_sp(0, 5)]) == []


def test_fmt_diff_ranges_split_on_description_change():
    a = [_sp(0, 10)]
    b = [_sp(0, 3, b=True), _sp(3, 6), _sp(6, 10, i=True)]
    assert fmt_diff(a, b) == [FmtRange(0, 3, "bold added"), FmtRange(6, 10, "italic added")]


def test_fmt_diff_merges_adjacent_same_description_spans():
    a = [_sp(0, 4), _sp(4, 8, z=12.0)]
    b = [_sp(0, 4, b=True), _sp(4, 8, b=True, z=12.0)]
    assert fmt_diff(a, b) == [FmtRange(0, 8, "bold added")]


def test_fmt_diff_skips_uncovered_positions():
    assert fmt_diff([_sp(0, 4)], [_sp(0, 2, b=True)]) == [FmtRange(0, 2, "bold added")]
