from calandria.layout.chrome import strip_marks
from calandria.layout.pages import GlyphRun, PlacedLine

# The fields themselves are substituted before a part is measured (chrome.part_blocks), so they are
# tested at the engine level in tests/test_engine_hf.py.


def _g(text, x, field=None, cid=None):
    return GlyphRun(text, x, 5.0 * len(text), "Fake|", 10, False, False, False, None, "eq", False, cid, 0.0, field)


def _line(runs, x=100.0, changed=True, cids=(3,)):
    return PlacedLine(x, 36.0, 12.0, 44.0, runs, [], changed, list(cids), 0, [], "header")


def test_strip_marks_clears_bars_numbers_and_run_cids_but_not_modes():
    ln = _line([_g("x", 100, cid=3)])
    ln.runs[0].mode = "ins"
    strip_marks(ln)
    assert ln.changed is False and ln.cid_starts == [] and ln.runs[0].cid is None and ln.runs[0].mode == "ins"
