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


def test_caps_pieces_measure_and_draw_as_capitals():
    runs = measure([Piece("Engineering, procurement", "eq", caps=True), Piece(" and", "eq")], FR, "Fake", 10)
    assert [r.text for r in runs] == ["ENGINEERING,", " ", "PROCUREMENT", " ", "and"]
    assert runs[0].w == 60 and runs[0].piece.text == "Engineering, procurement"


from calandria.model import TabStop


def _tab_runs(*parts, size=10):
    """parts: str for text, int for that many tabs."""
    pieces = [Piece("", "eq", tab=p) if isinstance(p, int) else Piece(p, "eq") for p in parts]
    return measure(pieces, FR, "Fake", size)


def _placed(lines):
    return [[(r.text, r.w, r.leader) for r in ln.runs] for ln in lines]


def test_measure_emits_one_empty_run_per_tab():
    runs = _tab_runs("a", 2, "b")
    assert [(r.text, r.w, r.tab, r.is_space) for r in runs] == [("a", 5, False, False), ("\t", 0, True, False),
                                                                 ("\t", 0, True, False), ("b", 5, False, False)]


def test_a_tab_advances_to_the_next_default_stop():
    lines = break_lines(_tab_runs("ab", 1, "cd", 1, "e"), 200, 200, Spacing(), FACE, 10, default_tab=36)
    assert _placed(lines) == [[("ab", 10, None), ("\t", 26, None), ("cd", 10, None), ("\t", 26, None), ("e", 5, None)]]
    assert lines[0].width == 77 and lines[0].gaps == 0


def test_default_stops_count_from_the_container_not_the_line_start():
    lines = break_lines(_tab_runs("ab", 1, "c"), 200, 200, Spacing(), FACE, 10, first_x=30, x=30, default_tab=36)
    assert _placed(lines)[0][1] == ("\t", 32, None)          # 30 + 10 = 40 -> the stop at 72


def test_custom_left_stops_come_first_then_default_stops_beyond_them():
    stops = (TabStop(40.0, "left"),)
    lines = break_lines(_tab_runs("a", 1, "b", 1, "c"), 200, 200, Spacing(), FACE, 10, stops=stops, default_tab=36)
    assert _placed(lines) == [[("a", 5, None), ("\t", 35, None), ("b", 5, None), ("\t", 27, None), ("c", 5, None)]]


def test_right_stop_aligns_the_following_text_at_the_stop_with_a_leader():
    stops = (TabStop(100.0, "right", "dot"),)
    lines = break_lines(_tab_runs("Definitions", 1, "12"), 200, 200, Spacing(), FACE, 10, stops=stops, default_tab=36)
    assert _placed(lines) == [[("Definitions", 55, None), ("\t", 35, "."), ("12", 10, None)]]
    assert lines[0].width == 100


def test_centre_and_decimal_stops():
    lines = break_lines(_tab_runs("a", 1, "bcde"), 200, 200, Spacing(), FACE, 10, stops=(TabStop(50.0, "center"),))
    assert _placed(lines)[0][1] == ("\t", 35, None)          # text centred on 50: starts at 40
    lines = break_lines(_tab_runs("a", 1, "12.75"), 200, 200, Spacing(), FACE, 10, stops=(TabStop(50.0, "decimal"),))
    assert _placed(lines)[0][1] == ("\t", 35, None)          # "12" right of 40, the point at 50


def test_a_right_stop_the_text_cannot_reach_leaves_no_gap():
    lines = break_lines(_tab_runs("aaaa", 1, "bbbbbbbbbb"), 200, 200, Spacing(), FACE, 10, stops=(TabStop(30.0, "right"),))
    assert _placed(lines)[0][1] == ("\t", 0, None)


def test_a_tab_past_the_right_edge_wraps_and_is_empty_on_a_fresh_line():
    lines = break_lines(_tab_runs("abcd", 1, "e"), 50, 50, Spacing(), FACE, 10, default_tab=36)
    assert _placed(lines) == [[("abcd", 20, None), ("\t", 16, None), ("e", 5, None)]]
    lines = break_lines(_tab_runs("abcdefgh", 1, "e"), 50, 50, Spacing(), FACE, 10, default_tab=36)
    assert _placed(lines) == [[("abcdefgh", 40, None)], [("\t", 36, None), ("e", 5, None)]]
    lines = break_lines(_tab_runs("abcdefgh", 1, "e"), 50, 50, Spacing(), FACE, 10, default_tab=0)
    assert _placed(lines) == [[("abcdefgh", 40, None), ("\t", 0, None), ("e", 5, None)]]


def test_tabs_are_not_justification_gaps_and_survive_the_line_end():
    lines = break_lines(_tab_runs("a b", 1), 200, 200, Spacing(), FACE, 10, default_tab=36)
    assert lines[0].gaps == 1 and _placed(lines)[0][-1] == ("\t", 21, None)


def test_a_tab_run_does_not_raise_the_line():
    # Word sizes a line by its characters, not its tabs: an 11 pt tab between 10 pt runs (every
    # entry of the EPC template's stored TOC) leaves the line at the text's height. A line that
    # holds only tabs keeps the paragraph's default height.
    runs = _runs("a") + measure([Piece("", "eq", size=20, tab=1)], FR, "Fake", 10) + _runs("b")
    assert line_height(runs, Spacing(), FACE, 10) == (12, 8)
    only_tabs = measure([Piece("", "eq", size=20, tab=1)], FR, "Fake", 10)
    assert line_height(only_tabs, Spacing(), FACE, 10) == (12, 8)


def test_a_raised_piece_measures_small_and_carries_its_rise():
    (r,) = measure([Piece("12", "eq", size=10, rise=True)], FR, "Fake", 10)
    assert (r.text, r.size, r.rise, r.w) == ("12", 6.5, 3.5, 6.5)     # 0.65 x size, raised 0.35 x size
    (n,) = measure([Piece("x", "eq", size=10)], FR, "Fake", 10)
    assert n.rise == 0.0
