from calandria.pdfread.lines import build_lines
from calandria.pdfread.types import TextRun


def R(text, x0, x1, y=100.0, size=12.0, font="Arial"):
    return TextRun(text, x0, x1, y, size, font)


def test_runs_on_one_baseline_make_one_line_left_to_right():
    (ln,) = build_lines([R("world", 110, 140), R("Hello ", 72, 110)], page=3, cell=(0, 2))
    assert (ln.text, ln.x0, ln.x1, ln.y, ln.size, ln.page, ln.cell) == ("Hello world", 72, 140, 100, 12, 3, (0, 2))
    assert len(ln.spans) == 1


def test_two_baselines_are_two_lines_in_reading_order():
    a, b = build_lines([R("second", 72, 110, y=114), R("first", 72, 100, y=100)])
    assert (a.text, b.text) == ("first", "second")


def test_a_format_change_starts_a_new_span_and_sizes_round_to_half_points():
    (ln,) = build_lines([R("plain ", 72, 110, size=11.04), R("bold", 110, 140, size=11.04, font="Arial,Bold")])
    assert [(s.text, s.font, s.size) for s in ln.spans] == [("plain ", "Arial", 11.0), ("bold", "Arial,Bold", 11.0)]


def test_a_raised_smaller_run_is_a_superscript_on_its_line():
    (ln,) = build_lines([R("1", 130, 134, y=95.5, size=8), R("the Supplier", 72, 130), R(" shall", 134, 160)])
    assert [(s.text, s.sup) for s in ln.spans] == [("the Supplier", False), ("1", True), (" shall", False)]
    assert (ln.y, ln.size) == (100, 12)


def test_word_positioned_runs_without_space_characters_get_spaces():
    (ln,) = build_lines([R("The", 72, 90), R("quick", 94, 120), R("fox", 124, 140)])
    assert ln.text == "The quick fox"


def test_no_second_space_where_one_is_already_there_and_kerning_gaps_add_none():
    (ln,) = build_lines([R("The ", 72, 94), R("quick", 94.5, 120), R("ly", 120.4, 130)])
    assert ln.text == "The quickly"


def test_a_wide_gap_is_a_tab_and_replaces_trailing_spaces():
    (ln,) = build_lines([R("12.3 ", 72, 96), R("Payment", 126, 170)])
    assert ln.text == "12.3\tPayment"
    (ln,) = build_lines([R("Name:", 72, 100), R("Title:", 300, 330)])
    assert ln.text == "Name:\tTitle:"


def test_text_drawn_twice_for_fake_bold_is_read_once():
    (ln,) = build_lines([R("Heading", 72, 120), R("Heading", 72.3, 120.3)])
    assert ln.text == "Heading"


def test_a_redrawn_run_is_measured_against_its_own_font_size():
    (ln,) = build_lines([R("Heading", 72, 120, size=24), R("Heading", 73.0, 121.0, size=24)])
    assert ln.text == "Heading"
    (ln,) = build_lines([R("x", 72, 75, size=6), R("x", 72.5, 75.5, size=6)])
    assert ln.text.count("x") == 2


def test_blank_lines_are_dropped_and_edges_ignore_outer_whitespace():
    lines = build_lines([R("   ", 72, 80, y=50), R(" padded ", 72, 120)])
    assert [ln.text for ln in lines] == ["padded"]
