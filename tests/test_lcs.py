import random

import pytest

from calandria.diff import lcs
from calandria.diff.lcs import lcs_ops


def test_equal_sequences():
    assert lcs_ops(["a", "b"], ["a", "b"]) == [("equal", 0, 0), ("equal", 1, 1)]


def test_tie_breaks_prefer_delete_then_insert():
    # Suffix table: dp[1][0] == dp[0][1] at the start, so the reference deletes first.
    assert lcs_ops(["a", "b"], ["b", "a"]) == [("delete", 0, 0), ("equal", 1, 0), ("insert", 2, 1)]


def test_replace_in_the_middle():
    assert lcs_ops(["a", "b", "c"], ["a", "x", "c"]) == [
        ("equal", 0, 0), ("delete", 1, 1), ("insert", 2, 1), ("equal", 2, 2)]


def test_empty_sides():
    assert lcs_ops([], ["a"]) == [("insert", 0, 0)]
    assert lcs_ops(["a"], []) == [("delete", 0, 0)]
    assert lcs_ops([], []) == []


def test_large_path_trims_prefix_and_suffix(monkeypatch):
    monkeypatch.setattr(lcs, "DP_CELL_CAP", 4)
    a = ["p", "q", "x", "y", "s", "t"]
    b = ["p", "q", "u", "s", "t"]
    ops = lcs_ops(a, b)
    assert ops[:2] == [("equal", 0, 0), ("equal", 1, 1)]
    assert ops[-2:] == [("equal", 4, 3), ("equal", 5, 4)]
    assert [o for o in ops if o[0] != "equal"] == [("delete", 2, 2), ("delete", 3, 2), ("insert", 4, 2)]


def test_anchors_path_matches_dp_on_unique_lines(monkeypatch):
    a = [f"line {i}" for i in range(60)]
    b = a[:20] + ["new A"] + a[20:41] + a[42:]      # one insert, one delete
    full = lcs_ops(a, b)
    monkeypatch.setattr(lcs, "DP_CELL_CAP", 10)     # force trim + patience anchors + recursion
    assert lcs_ops(a, b) == full
    assert sum(1 for t, _, _ in full if t == "equal") == 59


def test_no_anchors_falls_back_to_delete_all_then_insert_all(monkeypatch):
    monkeypatch.setattr(lcs, "DP_CELL_CAP", 1)
    ops = lcs_ops(["x", "x", "x"], ["y", "y"])
    assert ops == [("delete", 0, 0), ("delete", 1, 0), ("delete", 2, 0), ("insert", 3, 0), ("insert", 3, 1)]


def test_ops_are_a_valid_edit_script_random():
    rng = random.Random(7)
    for _ in range(200):
        a = [rng.choice("abcd") for _ in range(rng.randint(0, 12))]
        b = [rng.choice("abcd") for _ in range(rng.randint(0, 12))]
        rebuilt = []
        for tag, i, j in lcs_ops(a, b):
            if tag == "equal":
                assert a[i] == b[j]
                rebuilt.append(b[j])
            elif tag == "insert":
                rebuilt.append(b[j])
        assert rebuilt == b
