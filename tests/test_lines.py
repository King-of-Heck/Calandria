from calandria.layout.lines import Spacing, break_lines, line_height, measure
from calandria.layout.pieces import Piece
from calandria.testing.fakefonts import FakeResolver

FR = FakeResolver()          # 5 pt per character at size 10; line height 12; ascent 8; descent 4
FACE = FR.face("Fake")


def _runs(text, size=10, **kw):
    return measure([Piece(text, "eq", size=size, **kw)], FR, "Fake", 10)


def _texts(lines):
    return ["".join(r.text for r in ln.runs) for ln in lines]


def test_measure_splits_words_and_whitespace():
    runs = _runs("aa  bb")
    assert [(r.text, r.w, r.is_space) for r in runs] == [("aa", 10, False), ("  ", 10, True), ("bb", 10, False)]


def test_measure_uses_piece_font_and_style():
    (r,) = measure([Piece("x", "ins", bold=True, font="Other", size=20)], FR, "Fake", 10)
    assert r.face.key == "Other|B" and r.size == 20 and r.w == 10


def test_measure_falls_back_to_the_document_defaults():
    (r,) = measure([Piece("x", "eq")], FR, "Doc", 12)
    assert r.face.key == "Doc|" and r.size == 12


def test_wraps_at_the_last_fitting_word():
    lines = break_lines(_runs("aaaa bbbb cccc"), 45, 45, Spacing(), FACE, 10)
    assert _texts(lines) == ["aaaa bbbb", "cccc"]
    assert (lines[0].width, lines[0].gaps) == (45, 1)
    assert (lines[1].width, lines[1].gaps) == (20, 0)


def test_trailing_whitespace_is_dropped_at_the_wrap():
    lines = break_lines(_runs("aaaa bbbb"), 40, 40, Spacing(), FACE, 10)
    assert _texts(lines) == ["aaaa", "bbbb"] and lines[0].width == 20 and lines[0].gaps == 0


def test_first_line_can_be_narrower():
    lines = break_lines(_runs("aa bb cc dd"), 20, 100, Spacing(), FACE, 10)
    assert _texts(lines) == ["aa", "bb cc dd"]


def test_long_word_splits_by_character():
    lines = break_lines(_runs("abcdefghij"), 30, 30, Spacing(), FACE, 10)
    assert _texts(lines) == ["abcdef", "ghij"]


def test_long_word_after_text_starts_its_own_line_then_splits():
    lines = break_lines(_runs("aa abcdefghij"), 30, 30, Spacing(), FACE, 10)
    assert _texts(lines) == ["aa", "abcdef", "ghij"]


def test_empty_paragraph_is_one_empty_line_at_the_default_height():
    lines = break_lines([], 100, 100, Spacing(), FACE, 10)
    assert len(lines) == 1 and lines[0].runs == [] and lines[0].height == 12 and lines[0].ascent == 8


def test_line_height_rules():
    runs = _runs("x")
    assert line_height(runs, Spacing(), FACE, 10) == (12, 8)
    assert line_height(runs, Spacing("auto", 2.0), FACE, 10) == (24, 20)
    assert line_height(runs, Spacing("exact", None, 30), FACE, 10) == (30, 26)
    assert line_height(runs, Spacing("atLeast", None, 30), FACE, 10) == (30, 26)
    assert line_height(runs, Spacing("atLeast", None, 5), FACE, 10) == (12, 8)


def test_tallest_run_sets_the_line_height():
    runs = _runs("a") + _runs("b", size=20)
    assert line_height(runs, Spacing(), FACE, 10) == (24, 16)


def test_each_line_measures_its_own_runs():
    runs = _runs("aaaa ") + _runs("bbbb", size=20)     # "bbbb" at size 20 is 40 pt wide
    lines = break_lines(runs, 45, 45, Spacing(), FACE, 10)
    assert _texts(lines) == ["aaaa", "bbbb"] and [ln.height for ln in lines] == [12, 24]
