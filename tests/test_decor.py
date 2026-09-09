import pytest

from calandria.pdf.decor import decorations, run_effects


def test_single_underline_and_strike_geometry():
    assert decorations(frozenset({"underline"}), 10, 30, 100, 10) == [(10, 30, 101.1, 0.6, False)]
    assert decorations(frozenset({"strikethrough"}), 10, 30, 100, 10) == [(10, 30, 97.4, 0.6, False)]


def test_double_forms_and_dotted():
    du = decorations(frozenset({"double-underline"}), 0, 20, 100, 10)
    assert du[0] == pytest.approx((0, 20, 100.8, 0.45, False))
    assert du[1] == pytest.approx((0, 20, 102.0, 0.45, False))
    ds = decorations(frozenset({"double-strikethrough"}), 0, 20, 100, 10)
    assert ds[0] == pytest.approx((0, 20, 96.9, 0.45, False))
    assert ds[1] == pytest.approx((0, 20, 97.9, 0.45, False))
    assert decorations(frozenset({"dotted-underline"}), 0, 20, 100, 10) == [(0, 20, 101.1, 0.6, True)]


def test_order_is_stable_and_bold_italic_draw_nothing():
    eff = frozenset({"double-strikethrough", "bold", "underline", "italic", "strikethrough", "double-underline"})
    ys = [round(d[2] - 100, 2) for d in decorations(eff, 0, 1, 100, 10)]
    assert ys == [1.1, 0.8, 2.0, -2.6, -3.1, -2.1]
    assert decorations(frozenset({"bold", "italic"}), 0, 1, 100, 10) == []


def test_run_effects_merges_the_document_underline():
    assert run_effects(frozenset(), False) == frozenset()
    assert run_effects(frozenset(), True) == frozenset({"underline"})
    assert run_effects(frozenset({"strikethrough"}), True) == frozenset({"strikethrough", "underline"})
    assert run_effects(frozenset({"double-underline"}), True) == frozenset({"double-underline"})
    assert run_effects(frozenset({"dotted-underline"}), True) == frozenset({"underline"})
    assert run_effects(frozenset({"dotted-underline"}), False) == frozenset({"dotted-underline"})
