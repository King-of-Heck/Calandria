from calandria.pdfread.paras import MARKER, build_paragraphs, nothing_wraps, prevailing_pitch
from calandria.pdfread.types import Line, Span

LEFT, RIGHT = 72.0, 540.0
FULL = "The Supplier shall deliver the Goods to the Buyer at the Delivery Point on the agreed date"
CONT = "the following provisions shall apply without limiting the generality of the foregoing"


def L(text, y, x0=LEFT, x1=RIGHT, page=0, size=12.0, font="Arial", spans=None):
    return Line(page, x0, x1, y, size, spans or [Span(text, font, size)])


def texts(paras):
    return ["".join(s.text for s in p.spans) for p in paras]


def test_prevailing_pitch_is_the_commonest_ratio_and_has_a_default():
    lines = [L("a", 100), L("b", 113.8), L("c", 127.6), L("d", 160), L("e", 173.8)]
    assert prevailing_pitch(lines) == 1.15
    assert prevailing_pitch([L("alone", 100)]) == 1.2
    assert prevailing_pitch([L("a", 100), L("b", 100, page=1)]) == 1.2


def test_full_lines_at_the_prevailing_pitch_are_one_paragraph():
    (p,) = build_paragraphs([L(FULL, 100), L(FULL, 113.8), L("and no later.", 127.6, x1=150)], LEFT, RIGHT, 1.15)
    assert texts([p]) == [FULL + " " + FULL + " and no later."]
    assert (p.align, p.ind_left, p.ind_first, p.ind_hanging) == ("justify", 0.0, 0.0, 0.0)


def test_a_wider_gap_starts_a_new_paragraph_and_gives_space_after():
    a, b = build_paragraphs([L(FULL, 100), L(FULL, 113.8), L(FULL, 139.6), L(FULL, 153.4)], LEFT, RIGHT, 1.15)
    assert len(a.lines) == 2 and len(b.lines) == 2
    assert a.space_after == 12.0 and b.space_after is None        # 25.8 - 13.8


def test_a_line_that_ended_short_closes_its_paragraph_even_at_the_same_pitch():
    a, b = build_paragraphs([L("Short heading", 100, x1=160), L(FULL, 113.8)], LEFT, RIGHT, 1.15)
    assert texts([a, b]) == ["Short heading", FULL]


def test_a_paragraph_flows_across_a_page_break_but_a_short_line_still_ends_it():
    (p,) = build_paragraphs([L(FULL, 700), L(FULL, 90, page=1)], LEFT, RIGHT, 1.15)
    assert len(p.lines) == 2
    a, b = build_paragraphs([L("The end.", 700, x1=120), L(FULL, 90, page=1)], LEFT, RIGHT, 1.15)
    assert texts([a, b]) == ["The end.", FULL]


def test_first_line_and_hanging_indents_are_measured():
    (p,) = build_paragraphs([L(FULL, 100, x0=108), L(FULL, 113.8), L(FULL, 127.6)], LEFT, RIGHT, 1.15)
    assert (p.ind_left, p.ind_first, p.ind_hanging) == (0.0, 36.0, 0.0)
    (p,) = build_paragraphs([L("(a)\t" + FULL, 100), L(FULL, 113.8, x0=108), L(FULL, 127.6, x0=108)], LEFT, RIGHT, 1.15)
    assert (p.ind_left, p.ind_first, p.ind_hanging) == (36.0, 0.0, 36.0)


def test_a_changed_continuation_indent_or_size_starts_a_new_paragraph():
    paras = build_paragraphs([L(FULL, 100), L(FULL, 113.8), L(FULL, 127.6, x0=108)], LEFT, RIGHT, 1.15)
    assert [len(p.lines) for p in paras] == [2, 1]
    paras = build_paragraphs([L(FULL, 100, size=14), L(FULL, 116)], LEFT, RIGHT, 1.15)
    assert len(paras) == 2


def test_markers():
    for s in ["12.3 Payment", "1. Scope", "(a) the", "a)\tthe", "(iv) where", "• item", "\titem"]:
        assert MARKER.match(s), s
    for s in ["Payment 12.3", "2026 was", "and (a) the", "A long line", "(see clause 4)", "\titem"]:
        assert not MARKER.match(s), s


def test_a_marker_with_a_tab_starts_a_paragraph_but_a_wrapped_clause_reference_does_not():
    a, b = build_paragraphs([L(FULL, 100), L("12.3\t" + FULL, 113.8)], LEFT, RIGHT, 1.15)
    assert len(a.lines) == len(b.lines) == 1
    (p,) = build_paragraphs([L(FULL, 100), L("12.3 of this Agreement applies to " + FULL[:40], 113.8)], LEFT, RIGHT, 1.15)
    assert len(p.lines) == 2


def test_a_hanging_marker_without_a_tab_is_found_by_its_position():
    lines = [L("(a) " + FULL, 100), L(FULL, 113.8, x0=96), L("(b) " + FULL, 127.6), L(FULL, 141.4, x0=96)]
    a, b = build_paragraphs(lines, LEFT, RIGHT, 1.15)
    assert len(a.lines) == len(b.lines) == 2


def test_an_indented_justified_block_is_one_paragraph():
    lines = [L(FULL, 100, x0=108, x1=504), L(FULL, 113.8, x0=108, x1=504), L("the end.", 127.6, x0=108, x1=160)]
    (p,) = build_paragraphs(lines, LEFT, RIGHT, 1.15)
    assert len(p.lines) == 3 and p.ind_left == 36.0


def test_hyphens_join_without_a_space_and_soft_hyphens_vanish():
    (p,) = build_paragraphs([L("the parties agree a non-", 100), L("compete clause which is long enough to fill", 113.8)],
                            LEFT, RIGHT, 1.15)
    assert texts([p])[0].startswith("the parties agree a non-compete clause")
    (p,) = build_paragraphs([L("an obli­", 100), L("gation that carries on to the right margin here", 113.8)],
                            LEFT, RIGHT, 1.15)
    assert texts([p])[0].startswith("an obligation that")
    (p,) = build_paragraphs([L("between 5 -", 100), L("10 days of the notice reaching the other party", 113.8)],
                            LEFT, RIGHT, 1.15)
    assert texts([p])[0].startswith("between 5 - 10 days")


def test_spans_keep_their_format_across_the_join():
    bold = [Span("Definitions. ", "Arial,Bold", 12.0), Span("In this Agreement the following words have", "Arial", 12.0)]
    (p,) = build_paragraphs([L("", 100, spans=bold), L("the meanings given to them below in each case", 113.8)],
                            LEFT, RIGHT, 1.15)
    assert [(s.text[:12], s.font) for s in p.spans] == [("Definitions.", "Arial,Bold"), ("In this Agre", "Arial")]
    assert p.spans[1].text.endswith("following words have the meanings given to them below in each case")


def test_centred_and_right_aligned_lines():
    (c,) = build_paragraphs([L("SCHEDULE 1", 100, x0=266, x1=346)], LEFT, RIGHT, 1.15)
    (r,) = build_paragraphs([L("Ref: 2026/17", 100, x0=470, x1=540)], LEFT, RIGHT, 1.15)
    (lf,) = build_paragraphs([L("Left text", 100, x1=130)], LEFT, RIGHT, 1.15)
    assert (c.align, r.align, lf.align) == ("center", "right", "left")
    assert (c.ind_left, r.ind_left) == (0.0, 0.0)


def test_no_lines_no_paragraphs():
    assert build_paragraphs([], LEFT, RIGHT, 1.15) == []


PASSAGE = [(FULL, RIGHT), (CONT, RIGHT), (CONT, RIGHT), ("and no later.", 130.0),
           (FULL, RIGHT), ("the second paragraph ends.", 200.0)]


def spaced(rows, step):
    return [L(t, 100 + step * i, x1=x1) for i, (t, x1) in enumerate(rows)]


def test_the_wrap_statistic_reads_the_lines_that_reach_the_right_edge():
    """A line that reaches the edge, does not finish its sentence AND is followed by a line that
    carries on in lowercase wrapped; one that reaches the edge and ends there is a paragraph of its
    own. WRAPPING's text is realistic wrapped prose -- each continuation line picks up lowercase,
    the way a clause that runs past the margin actually looks on the page (unlike FULL, which
    starts a fresh capitalised clause and so would not read as a continuation)."""
    wrapping = [L(CONT, 100 + 14 * i) for i in range(6)] + [L("and no later.", 184, x1=130)]
    assert nothing_wraps(wrapping, RIGHT) is False
    one_liners = [L(f"Clause {i} remains identical.", 100 + 14 * i) for i in range(6)] + [L("End.", 184, x1=130)]
    assert nothing_wraps(one_liners, RIGHT) is True
    assert nothing_wraps(wrapping[:3], RIGHT) is True                  # too few full lines to judge
    assert nothing_wraps([], RIGHT) is True


def test_one_and_a_half_line_spacing_keeps_a_wrapped_passage_whole():
    """Word's '1.5 lines' is about 1.73 em, wider than LINE_MAX, so the cap alone would make every
    wrapped line its own paragraph. In a document where text really wraps the cap is off."""
    lines = spaced(PASSAGE, 20.75)
    assert prevailing_pitch(lines) == 1.75 and nothing_wraps(lines, RIGHT) is False
    assert [len(p.lines) for p in build_paragraphs(lines, LEFT, RIGHT, 1.75, no_wrap=False)] == [4, 2]


def test_double_line_spacing_keeps_a_wrapped_passage_whole():
    lines = spaced(PASSAGE, 27.6)
    assert prevailing_pitch(lines) == 2.3 and nothing_wraps(lines, RIGHT) is False
    assert [len(p.lines) for p in build_paragraphs(lines, LEFT, RIGHT, 2.3, no_wrap=False)] == [4, 2]


def test_a_heading_between_double_spaced_paragraphs_still_splits_off():
    body = [(FULL, RIGHT), (CONT, RIGHT), ("ends here.", 150.0)]
    lines = spaced(body + [("Heading One", 200.0)] + body + [("Heading Two", 210.0)] + body, 27.6)
    assert nothing_wraps(lines, RIGHT) is False
    paras = build_paragraphs(lines, LEFT, RIGHT, prevailing_pitch(lines), no_wrap=False)
    assert [len(p.lines) for p in paras] == [3, 1, 3, 1, 3]
    assert texts(paras)[1::2] == ["Heading One", "Heading Two"]


def test_a_document_of_one_line_paragraphs_does_not_read_as_one_paragraph():
    """Word's numbers, from big200A.pdf: 200 clauses of near-identical length, each its own
    paragraph, 12 pt, 24.77 pt apart. Nothing wraps, so the commonest gap IS the paragraph gap and
    the pitch rule alone would join the lot; no line of text sits 2 em below the line before it."""
    lines = [Line(0, 72.1, 519.94, 83.33 + 24.77 * i, 12.0, [Span(f"Clause {i} remains identical.", "Arial", 12.0)])
             for i in range(4)]
    pitch = prevailing_pitch(lines)
    assert pitch == 2.05
    assert len(build_paragraphs(lines, 72.1, 533.4, pitch)) == 4


def test_a_schedule_of_one_line_clauses_ending_mid_word_does_not_collapse():
    """The reviewer's worst case: 20 full-width one-line clauses, 12 pt, 24.77 pt apart, each
    ending "; and" with no terminal punctuation at all. Under the old rule ("doesn't end a
    sentence" alone) every line reads as a wrapped continuation and the whole schedule collapses
    into one paragraph. None of them actually wrap: each next line starts with a fresh "(x)"
    marker, not a lowercase continuation, so nothing_wraps must read this as "nothing wraps" and
    the LINE_MAX cap must split the 20 clauses apart."""
    lines = [L(f"({i + 1}) the Supplier shall deliver the Goods to the Delivery Point on the "
                "agreed date; and", 100 + 24.77 * i)
             for i in range(20)]
    assert nothing_wraps(lines, RIGHT) is True
    pitch = prevailing_pitch(lines)
    paras = build_paragraphs(lines, LEFT, RIGHT, pitch, no_wrap=nothing_wraps(lines, RIGHT))
    assert len(paras) == 20


def test_a_line_ending_a_right_double_quote_counts_as_a_sentence_end():
    """Word's right double quotation mark ("as is.”) closes a sentence just as an ASCII quote
    does. Six full-width lines each end that way, and every one is followed by a lowercase word --
    the shape that would otherwise read as wrapping -- but a line ending in ” must never count
    as carrying a sentence on, so the document must read as "nothing wraps" regardless."""
    full = [L(f"clause {i} ends with a right double quote as is.”", 100 + 24.77 * i)
            for i in range(6)] + [L("the schedule continues below.", 250.0, x1=200)]
    assert nothing_wraps(full, RIGHT) is True
