import pytest

from calandria.diff.text import (categorize, content_tokens, norm, sim, sim_upper, tokenize,
                                 words_only)


def test_tokenize_keeps_money_and_dates_whole():
    assert tokenize("$1,200.50 due 2026-09-08, ok") == [
        "$", "1,200.50", " ", "due", " ", "2026-09-08", ",", " ", "ok"]


def test_tokenize_ascii_word_class_like_the_reference():
    # JS \w is ASCII-only: a non-ASCII letter is its own punctuation-class token.
    assert tokenize("café x") == ["caf", "é", " ", "x"]


def test_tokenize_covers_every_character():
    for s in ["", "a", "  two  spaces ", "x\ty\nz", "3:45pm-ish", "(a)-(b)"]:
        assert "".join(tokenize(s)) == s


def test_words_only_lowercases_and_drops_punctuation():
    assert words_only("Hello, World-wide 42!") == ["hello", "world", "wide", "42"]


def test_content_tokens_drop_whitespace():
    assert content_tokens("a  b") == ["a", "b"]


def test_norm_collapses_and_optionally_lowercases():
    assert norm("  Hello   World ") == "Hello World"
    assert norm("  Hello   World ", ignore_case=True) == "hello world"


def test_sim_is_dice_over_lcs_of_content_tokens():
    assert sim("a b c", "a b d") == pytest.approx(4 / 6)
    assert sim("", "") == 1.0
    assert sim("a", "") == 0.0


def test_sim_upper_bounds_sim():
    ta, tb = ["a", "b", "c"], ["a", "b", "d"]
    assert sim_upper(ta, tb) == pytest.approx(4 / 6)
    assert sim_upper(["a"] * 4, ["a"]) == pytest.approx(2 / 5)   # length ratio wins
    assert sim_upper([], []) == 1.0 and sim_upper(["a"], []) == 0.0


def test_categorize():
    assert categorize("Hello, world.", "Hello world") == "punctuation"
    assert categorize("The Provider", "The provider") == "punctuation"   # case-only counts as punctuation
    assert categorize("a b", "a c") == "content"


def test_tokenize_and_content_tokens_use_the_reference_whitespace_class():
    # U+FEFF is whitespace in the reference engine (JS \s) even though it is not in Python's.
    assert tokenize("a" + chr(0xfeff) + "b") == ["a", chr(0xfeff), "b"]
    assert content_tokens("a" + chr(0xfeff) + "b") == ["a", "b"]
    # U+0085 (NEL) is NOT whitespace in the reference engine, so norm() must not collapse it.
    assert norm("a" + chr(0x85) + "b") == "a" + chr(0x85) + "b"
