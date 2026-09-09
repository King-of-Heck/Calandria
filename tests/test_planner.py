from calandria.layout.planner import BlockSpec, Break, plan_breaks


def B(*hs, **kw):
    return BlockSpec(list(hs), **kw)


def const(a):
    return lambda p: a


def test_everything_fits():
    plan = plan_breaks([B(10, 10), B(10)], const(50))
    assert plan.breaks == [] and plan.before == [True, True]


def test_a_block_that_would_leave_one_line_moves_whole():
    plan = plan_breaks([B(10, 10, 10), B(10, 10, 10), B(10, 10, 10)], const(50))
    assert plan.breaks == [Break(1, 0), Break(2, 0)]


def test_widow_control_keeps_two_lines_after_the_break():
    assert plan_breaks([B(10, 10, 10, 10, 10)], const(40)).breaks == [Break(0, 3)]


def test_orphan_control_moves_the_block_when_one_line_would_stay():
    assert plan_breaks([B(10, 10), B(10, 10, 10)], const(35)).breaks == [Break(1, 0)]


def test_widow_pushback_retries_on_a_fresh_page_before_forcing():
    assert plan_breaks([B(10, 10, 10, 10), B(10, 10, 10)], const(60)).breaks == [Break(1, 0)]


def test_page_break_before():
    assert plan_breaks([B(10), B(10, page_break_before=True), B(10)], const(100)).breaks == [Break(1, 0)]


def test_page_break_before_at_the_very_top_adds_no_page():
    assert plan_breaks([B(10, page_break_before=True)], const(100)).breaks == []


def test_keep_next_moves_the_heading_with_its_paragraph():
    blocks = [B(10, 10), B(10, keep_next=True), B(10, 10, 10)]
    assert plan_breaks(blocks, const(45)).breaks == [Break(1, 0)]
    blocks[1].keep_next = False
    assert plan_breaks(blocks, const(45)).breaks == [Break(2, 0)]


def test_keep_next_chain_counts_the_spacing_between_members():
    blocks = [B(10, 10), B(10, keep_next=True, space_after=10), B(10, 10, 10, space_before=10)]
    assert plan_breaks(blocks, const(60)).breaks == [Break(1, 0)]     # needs 10+10+10+20 = 50 > 40 free
    assert plan_breaks(blocks, const(80)).breaks == []                  # 50 <= 60 free, then all fits


def test_keep_next_chain_stops_at_a_page_break_before():
    blocks = [B(10, 10), B(10, keep_next=True), B(10, 10, 10, page_break_before=True)]
    assert plan_breaks(blocks, const(35)).breaks == [Break(2, 0)]


def test_keep_lines_moves_a_paragraph_that_fits_a_page_whole():
    blocks = [B(10, 10), B(10, 10, 10, 10, keep_lines=True)]
    assert plan_breaks(blocks, const(50)).breaks == [Break(1, 0)]
    blocks[1].keep_lines = False
    assert plan_breaks(blocks, const(50)).breaks == [Break(1, 2)]


def test_keep_lines_taller_than_a_page_splits_like_any_paragraph():
    assert plan_breaks([B(*([10] * 8), keep_lines=True)], const(50)).breaks == [Break(0, 5)]


def test_space_before_and_after_consume_the_page():
    assert plan_breaks([B(10, space_after=35), B(10)], const(50)).breaks == [Break(1, 0)]
    assert plan_breaks([B(10), B(10, space_before=35)], const(50)).breaks == [Break(1, 0)]
    assert plan_breaks([B(10), B(10, space_before=30)], const(50)).breaks == []


def test_space_before_dropped_on_an_automatic_page_kept_after_an_explicit_break():
    plan = plan_breaks([B(10, 10, 10), B(10, space_before=45)], const(30))
    assert plan.breaks == [Break(1, 0)] and plan.before == [True, False]
    plan = plan_breaks([B(10), B(10, space_before=15, page_break_before=True)], const(30))
    assert plan.breaks == [Break(1, 0)] and plan.before == [True, True]


def test_first_page_applies_space_before():
    plan = plan_breaks([B(10, space_before=20), B(10)], const(35))
    # page 2 was started automatically, so block 1's space-before is dropped
    assert plan.before == [True, False] and plan.breaks == [Break(1, 0)]


def test_a_line_taller_than_the_page_is_forced_through():
    assert plan_breaks([B(100, 10)], const(50)).breaks == [Break(0, 1)]


def test_avail_varies_per_page():
    plan = plan_breaks([B(10, 10, 10), B(10, 10, 10)], lambda p: 30 if p == 0 else 100)
    assert plan.breaks == [Break(1, 0)]


def test_space_before_is_dropped_when_widow_control_pushes_the_block_whole():
    # block 1 seems to fit (3 + 20 <= 25 free) but its third line does not; orphan control
    # moves it whole to page 2, an automatic page, so its space-before is dropped there.
    plan = plan_breaks([B(10), B(10, 10, 10, space_before=3)], const(35))
    assert plan.breaks == [Break(1, 0)] and plan.before == [True, False]
