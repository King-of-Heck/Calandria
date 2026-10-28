from delta.diff.inline import (CONN, INLINE_TOKEN_CAP, Seg, coalesce, inline_segs, safe_inline,
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
    assert segs == [Seg("eq", "the "), Seg("del", "quick"), Seg("ins", "slow "),
                    Seg("ins", "bold", True), Seg("eq", " fox")]


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


def _shape(segs, flip=False):
    """Equal text and change runs as (old, new), so a swapped comparison can be compared as is."""
    out = []
    for m, t in _flat(segs):
        if m == "eq":
            out.append(("eq", t))
            continue
        if not out or out[-1][0] != "chg":
            out.append(("chg", "", ""))
        _, d, i = out[-1]
        if (m == "del") != flip:
            d += t
        else:
            i += t
        out[-1] = ("chg", d, i)
    return out


BENCH_A1 = ("will provide preventive maintenance, emergency response, remote monitoring, and quarterly "
            "performance reporting for the solar generation facilities identified in Schedule A.")
BENCH_B1 = ("will provide preventive maintenance, emergency response, remote monitoring, monthly "
            "performance reporting, and annual reliability planning for the solar generation "
            "facilities identified in Schedule A.")
BENCH_A2 = "must state any resulting adjustment to price, schedule, or service levels."
BENCH_B2 = ("must identify any expected price, schedule, staffing, or service-level impact before "
            "commencing changed work. Emergency changes necessary to protect personnel or equipment "
            "may be implemented immediately, with written confirmation within two business days.")


def test_longer_shared_words_win_over_a_connective_both_ways():
    # Keeping "performance reporting" beats keeping a lone "and" plus spaces, whichever side is old.
    fwd = _shape(inline_segs(BENCH_A1, BENCH_B1, [], []))
    assert ("eq", " performance reporting") in fwd
    assert fwd == _shape(inline_segs(BENCH_B1, BENCH_A1, [], []), flip=True)


def test_added_sentence_joins_the_change_before_it_both_ways():
    # The final full stop matches the final full stop, so the new sentence is not a change of its own.
    fwd = _shape(inline_segs(BENCH_A2, BENCH_B2, [], []))
    assert fwd[-1] == ("eq", ".")
    assert fwd[-2] == ("chg", "levels", "impact before commencing changed work. Emergency changes "
                       "necessary to protect personnel or equipment may be implemented immediately, "
                       "with written confirmation within two business days")
    assert fwd == _shape(inline_segs(BENCH_B2, BENCH_A2, [], []), flip=True)


def test_swapping_the_documents_mirrors_the_word_diff():
    import random
    rnd = random.Random(7)
    vocab = ["the", "and", "of", "price", "schedule", "service", "levels", ",", ".", "Provider",
             "change", "order", "a", "monthly", "quarterly"]
    def para():
        toks = [rnd.choice(vocab) for _ in range(rnd.randint(0, 14))]
        return "".join(t if t in ",." else " " + t for t in toks).strip()
    for _ in range(400):
        a, b = para(), para()
        assert _shape(inline_segs(a, b, [], [])) == _shape(inline_segs(b, a, [], []), flip=True), (a, b)


def test_an_added_sentence_ends_on_its_own_full_stop_both_ways():
    a = "Notice is due after the first anniversary."
    b = "Notice is due after the first anniversary. The Customer may also terminate within 15 days."
    assert _flat(inline_segs(a, b, [], [])) == [
        ("eq", a), ("ins", " The Customer may also terminate within 15 days.")]
    assert _flat(inline_segs(b, a, [], [])) == [
        ("eq", a), ("del", " The Customer may also terminate within 15 days.")]
    # Nothing to slide onto: left as aligned.
    assert _flat(inline_segs("a b.", "a x b.", [], [])) == [("eq", "a "), ("ins", "x "), ("eq", "b.")]
