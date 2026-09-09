from calandria.diff.inline import (CONN, INLINE_TOKEN_CAP, Seg, coalesce, inline_segs, safe_inline,
                                   tok_bold, whole_segs)


def _flat(segs):
    """(mode, text) pairs with adjacent same-mode segments joined (bold ignored)."""
    out = []
    for s in segs:
        if out and out[-1][0] == s.m:
            out[-1] = (s.m, out[-1][1] + s.t)
        else:
            out.append((s.m, s.t))
    return out


def test_tok_bold_majority_rule():
    toks = ["Hello", " ", "World", " ", "ab"]
    # "Hello" bold, "ab" half bold (1 of 2 -> >= 0.5 -> bold); whitespace never bold.
    assert tok_bold(toks, [[0, 5], [12, 13]]) == [True, False, False, False, True]
    assert tok_bold(toks, []) == [False] * 5


def test_whole_segs_split_at_bold_boundaries():
    assert whole_segs("ab cd", [[3, 5]], "del") == [Seg("del", "ab "), Seg("del", "cd", True)]
    assert whole_segs("plain", [], "ins") == [Seg("ins", "plain")]
    assert whole_segs("", [], "eq") == []


def test_simple_replace_stays_word_level():
    assert _flat(inline_segs("a red car", "a blue car", [], [])) == [
        ("eq", "a "), ("del", "red"), ("ins", "blue"), ("eq", " car")]


def test_dense_rewrite_folds_lone_connective_into_both_sides():
    # C4 parity: two del-runs and two ins-runs separated only by a lone "and" collapse to one
    # struck phrase + one inserted phrase, the connective duplicated into both.
    segs = inline_segs("red and blue cars", "green and yellow cars", [], [])
    assert _flat(segs) == [("del", "red and blue"), ("ins", "green and yellow"), ("eq", " cars")]


def test_multi_word_shared_run_is_a_hard_anchor():
    segs = inline_segs("red and big blue cars", "green and big yellow cars", [], [])
    assert _flat(segs) == [("del", "red"), ("ins", "green"), ("eq", " and big "),
                           ("del", "blue"), ("ins", "yellow"), ("eq", " cars")]


def test_one_sided_edit_around_a_connective_does_not_collapse():
    segs = inline_segs("red and blue cars", "red and yellow cars", [], [])
    assert _flat(segs) == [("eq", "red and "), ("del", "blue"), ("ins", "yellow"), ("eq", " cars")]


def test_collapse_keeps_bold_flags_per_segment():
    # "big red" -> "small green" (red/green bold): the shared space splits two del-runs and two
    # ins-runs, so this DOES collapse; the folded whitespace goes to both sides and bold survives.
    segs = inline_segs("big red", "small green", [[4, 7]], [[6, 11]])
    assert segs == [Seg("del", "big", False), Seg("del", " ", False), Seg("del", "red", True),
                    Seg("ins", "small", False), Seg("ins", " ", False), Seg("ins", "green", True)]


def test_bold_flip_inside_one_phrase_is_one_run():
    # B3: the inserted phrase "bold " is two segments (bold flips on the trailing space) but ONE
    # ins-run; with a single del-run the collapse must not trigger.
    segs = inline_segs("the quick fox", "the slow bold fox", [], [[9, 13]])
    assert segs == [Seg("eq", "the "), Seg("del", "quick"), Seg("ins", "slow"), Seg("eq", " "),
                    Seg("ins", "bold", True), Seg("ins", " "), Seg("eq", "fox")]


def test_equal_tokens_take_revised_text_and_original_bold():
    segs = inline_segs("same", "same", [[0, 4]], [])
    assert segs == [Seg("eq", "same", True)]


def test_coalesce_strips_transparent_edges_out_of_the_span():
    segs = [Seg("eq", "x"), Seg("eq", " "), Seg("del", "a"), Seg("ins", "b"), Seg("eq", " "),
            Seg("del", "c"), Seg("ins", "d"), Seg("eq", " "), Seg("eq", "y")]
    out = coalesce(segs)
    assert _flat(out) == [("eq", "x "), ("del", "a c"), ("ins", "b d"), ("eq", " y")]


def test_conn_set():
    assert CONN == frozenset("a an the and or nor of to in on at by for as if is".split())


def test_safe_inline_falls_back_above_token_cap():
    long = " ".join(f"w{i}" for i in range(INLINE_TOKEN_CAP // 2 + 10))   # > cap tokens with spaces
    other = long.replace("w7 ", "changed ")
    segs = safe_inline(long, other, [], [])
    assert _flat(segs) == [("del", long), ("ins", other)]
    assert _flat(safe_inline("a b", "a c", [], [])) == [("eq", "a "), ("del", "b"), ("ins", "c")]
