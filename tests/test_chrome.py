from calandria.layout.chrome import fill_fields, strip_marks
from calandria.layout.pages import GlyphRun, PlacedLine
from calandria.testing.fakefonts import FakeResolver

FR = FakeResolver()


def _g(text, x, field=None, cid=None):
    return GlyphRun(text, x, 5.0 * len(text), "Fake|", 10, False, False, False, None, "eq", False, cid, 0.0, field)


def _line(runs, x=100.0, changed=True, cids=(3,)):
    return PlacedLine(x, 36.0, 12.0, 44.0, runs, [], changed, list(cids), 0, [], "header")


def test_fill_fields_left_aligned_shifts_the_runs_after_the_field():
    ln = _line([_g("p ", 100), _g("{PAGE}", 110, "PAGE"), _g(" end", 140)])
    fill_fields(ln, {"PAGE": "12"}, {"Fake|": FR.face("Fake", False, False)}, "left")
    assert [(g.text, g.x, g.w) for g in ln.runs] == [("p ", 100, 10), ("12", 110, 10), (" end", 120, 20)]
    assert ln.x == 100


def test_fill_fields_centred_and_right_lines_move_as_a_whole():
    ln = _line([_g("{PAGE}", 200, "PAGE")], x=200)
    fill_fields(ln, {"PAGE": "4"}, {"Fake|": FR.face("Fake", False, False)}, "center")
    assert (ln.x, ln.runs[0].x, ln.runs[0].w, ln.runs[0].text) == (212.5, 212.5, 5, "4")   # 30 -> 5: -25/2
    ln = _line([_g("{NUMPAGES}", 200, "NUMPAGES")], x=200)
    fill_fields(ln, {"NUMPAGES": "100"}, {"Fake|": FR.face("Fake", False, False)}, "right")
    assert (ln.x, ln.runs[0].x, ln.runs[0].w) == (235, 235, 15)                             # 50 -> 15: -35


def test_fill_fields_only_touches_the_named_fields():
    ln = _line([_g("{PAGE}", 100, "PAGE"), _g("{NUMPAGES}", 130, "NUMPAGES")])
    fill_fields(ln, {"PAGE": "1"}, {"Fake|": FR.face("Fake", False, False)}, "left")
    assert [(g.text, g.x) for g in ln.runs] == [("1", 100), ("{NUMPAGES}", 105)]
    assert ln.runs[1].field == "NUMPAGES" and ln.runs[0].field == "PAGE"


def test_strip_marks_clears_bars_numbers_and_run_cids_but_not_modes():
    ln = _line([_g("x", 100, cid=3)])
    ln.runs[0].mode = "ins"
    strip_marks(ln)
    assert ln.changed is False and ln.cid_starts == [] and ln.runs[0].cid is None and ln.runs[0].mode == "ins"
