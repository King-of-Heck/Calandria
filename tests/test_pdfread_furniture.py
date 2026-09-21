from calandria.pdfread.furniture import _PAGENUM, _signature, collect_notes, find_furniture
from calandria.pdfread.grid import find_grids
from calandria.pdfread.types import Line, PageLines, Seg, Span

H = 792.0


def L(text, y, page=0, x0=72.0, x1=300.0, size=12.0, cell=None, spans=None):
    return Line(page, x0, x1, y, size, spans or [Span(text, "Arial", size)], cell)


def page(i, lines, grids=(), segs=()):
    return PageLines(i, 612.0, H, sorted(lines, key=lambda l: (l.y, l.x0)), list(grids), list(segs))


def doc(n, extra=lambda i: []):
    return [page(i, [L("Acme Supply Agreement", 40, i), L(f"Body text of page {i + 1}", 300, i),
                     L(f"Page {i + 1} of {n}", 760, i, x0=270 - i)] + extra(i)) for i in range(n)]


def texts(pages, found):
    return sorted({pages[p].lines[i].text for p, i in found})


def test_repeating_header_and_numbered_footer_are_furniture_and_body_is_not():
    pages = doc(5)
    assert texts(pages, find_furniture(pages)) == ["Acme Supply Agreement"] + [f"Page {i} of 5" for i in range(1, 6)]


def test_a_different_first_page_still_strips_the_rest():
    pages = doc(5)
    pages[0] = page(0, [L("DRAFT 3", 40, 0), L("Title", 300, 0)])
    found = find_furniture(pages)
    assert "DRAFT 3" not in texts(pages, found) and len([1 for p, _ in found if p > 0]) == 8


def test_a_one_page_document_loses_only_its_page_number():
    pages = doc(1)
    assert texts(pages, find_furniture(pages)) == ["Page 1 of 1"]
    three = doc(3)
    assert "Acme Supply Agreement" in texts(three, find_furniture(three))


def test_bare_and_roman_page_numbers():
    pages = [page(i, [L("Body", 300, i), L(t, 765, i)]) for i, t in enumerate(["i", "ii", "- 3 -", "4 / 9"])]
    assert len(find_furniture(pages)) == 4


def test_en_and_em_dash_page_numbers():
    pages = [page(i, [L("Body", 300, i), L(t, 765, i)]) for i, t in enumerate(["– 3 –", "— 4 —"])]
    assert len(find_furniture(pages)) == 2


def test_words_made_only_of_roman_letters_are_not_roman_numerals():
    for word in ["civil", "vivid", "mimic", "dill"]:
        assert not _PAGENUM.match(word), word
    assert _PAGENUM.match("mix")           # a real numeral (1009), accepted as one
    for numeral in ["iv", "xii"]:
        assert _PAGENUM.match(numeral), numeral
    for numbered in ["- 3 -", "page 4 of 9"]:          # digits go through _signature first
        assert _signature(numbered) == "#", numbered


def test_a_body_word_made_of_roman_letters_is_not_stripped_as_a_page_number():
    pages = doc(5)
    pages[0] = page(0, [L("Acme Supply Agreement", 40, 0), L("civil matters", 300, 0), L("Page 1 of 5", 760, 0)])
    found = find_furniture(pages)
    assert "civil matters" not in texts(pages, found)


def test_a_lone_number_line_is_furniture_only_in_the_outer_half_of_the_band():
    short = doc(1)
    assert texts(short, find_furniture(short)) == ["Page 1 of 1"]

    inner_body = doc(5)
    inner_body[2] = page(2, [L("Acme Supply Agreement", 40, 2), L("2026", 100, 2), L("Page 3 of 5", 760, 2)])
    found = texts(inner_body, find_furniture(inner_body))
    assert "2026" not in found                            # inner half of the band, does not repeat

    inner_repeating = doc(5, extra=lambda i: [L("2026", 700, i)])
    found = find_furniture(inner_repeating)
    assert len([1 for p, li in found if inner_repeating[p].lines[li].text == "2026"]) == 5


def test_a_repeated_table_header_row_at_the_page_top_is_not_furniture():
    def with_table(i):
        segs = [Seg(72, 80, 540, 80), Seg(72, 100, 540, 100), Seg(72, 600, 540, 600),
                Seg(72, 80, 72, 600), Seg(300, 80, 300, 600), Seg(540, 80, 540, 600)]
        return find_grids(segs), [L("Item", 94, i, cell=(0, 0)), L("Price", 94, i, x0=310, cell=(0, 1))]
    pages = []
    for i in range(4):
        grids, cells = with_table(i)
        pages.append(page(i, cells + [L(f"Page {i + 1}", 760, i)], grids))
    assert texts(pages, find_furniture(pages)) == ["Page 1", "Page 2", "Page 3", "Page 4"]


def test_a_header_that_is_a_small_table_is_furniture():
    segs = [Seg(72, 20, 540, 20), Seg(72, 60, 540, 60), Seg(72, 20, 72, 60), Seg(300, 20, 300, 60), Seg(540, 20, 540, 60)]
    pages = [page(i, [L("Acme", 45, i, cell=(0, 0)), L("Confidential", 45, i, x0=310, cell=(0, 1)), L("Body", 300, i)],
                  find_grids(segs)) for i in range(4)]
    assert texts(pages, find_furniture(pages)) == ["Acme", "Confidential"]


def note(n, text, y, page=0):
    return L("", y, page, size=9.0, spans=[Span(str(n), "Arial", 6.0, True), Span(" " + text, "Arial", 9.0)])


def test_footnotes_under_a_short_rule_are_lifted_with_their_numbers_stripped():
    rule = Seg(72, 690, 216, 690)
    pages = [page(0, [L("Body one", 300), L("Body two", 320), note(1, "First note", 702), L("continues here", 713, size=9.0),
                      note(2, "Second note", 724)], segs=[rule])]
    notes, taken = collect_notes(pages, set(), 72.0, 12.0)
    assert {n: [ln.text for ln in lines] for n, lines in notes.items()} == {
        1: ["First note", "continues here"], 2: ["Second note"]}
    assert taken == {(0, 2), (0, 3), (0, 4)}


def test_a_plain_number_start_begins_a_note_only_when_it_is_the_next_number():
    rule = Seg(72, 690, 216, 690)
    pages = [page(0, [L("Body", 300), L("1 See clause 4 which runs for", 702, size=9.0), L("12 months from signing.", 713, size=9.0),
                      L("2. Second note", 724, size=9.0)], segs=[rule])]
    notes, _ = collect_notes(pages, set(), 72.0, 12.0)
    assert {n: [ln.text for ln in lines] for n, lines in notes.items()} == {
        1: ["See clause 4 which runs for", "12 months from signing."], 2: ["Second note"]}


def test_a_continuation_rule_appends_to_the_previous_pages_last_note():
    pages = [page(0, [L("Body", 300), note(1, "A note that runs", 702)], segs=[Seg(72, 690, 216, 690)]),
             page(1, [L("More body", 300, 1), L("over the page.", 702, 1, size=9.0)], segs=[Seg(72, 690, 540, 690)])]
    notes, taken = collect_notes(pages, set(), 72.0, 12.0)
    assert [ln.text for ln in notes[1]] == ["A note that runs", "over the page."] and len(taken) == 2


def test_rules_that_are_not_footnote_separators():
    body_below = [page(0, [L("Heading", 300), L("Normal body text", 702)], segs=[Seg(72, 690, 216, 690)])]
    assert collect_notes(body_below, set(), 72.0, 12.0) == ({}, set())
    high = [page(0, [L("small", 120, size=9.0)], segs=[Seg(72, 100, 216, 100)])]
    assert collect_notes(high, set(), 72.0, 12.0) == ({}, set())
    indented = [page(0, [L("small", 702, size=9.0)], segs=[Seg(200, 690, 344, 690)])]
    assert collect_notes(indented, set(), 72.0, 12.0) == ({}, set())


def test_furniture_below_the_notes_is_ignored_when_already_skipped():
    pages = [page(0, [L("Body", 300), note(1, "Note", 702), L("Page 1", 760)], segs=[Seg(72, 690, 216, 690)])]
    notes, taken = collect_notes(pages, {(0, 2)}, 72.0, 12.0)
    assert list(notes) == [1] and taken == {(0, 1)}


def test_the_same_header_on_both_pages_of_a_two_page_document_is_furniture():
    """benchA.pdf is two pages and benchB.pdf is three of the same document: when two pages were
    not enough to repeat against, A kept its running header and footer in the body and B did not,
    so the pair compared as changes that are not in the document."""
    two = doc(2)
    assert texts(two, find_furniture(two)) == ["Acme Supply Agreement", "Page 1 of 2", "Page 2 of 2"]
    one = doc(1)
    assert texts(one, find_furniture(one)) == ["Page 1 of 1"]      # nothing to repeat against


def test_a_numbered_body_line_at_the_page_top_is_not_furniture():
    """gen-hf-A.pdf: every clause reads 'Section one paragraph N ...', so blanking the digits gives
    them all one signature, and the clause that happened to land at the top of each page repeated
    at the same height and was stripped -- four paragraphs a page, gone from the body. The clause
    signature is body text because it is mostly body text: in gen-hf-A its three clause signatures
    run 52, 106 and 112 mid-page against 8, 14 and 8 in the band, while the header signature that
    carries a number runs 3 mid-page against 9. The headers are still stripped, the one whose number
    changes per page along with the rest."""
    pages = [page(i, [L("Acme Supply Agreement", 40, i), L(f"Schedule 3 - Page {i + 1}", 60, i),
                      L(f"Section one paragraph {i * 4} with enough words.", 80, i),
                      L(f"Page {i + 1} of 5", 760, i)]
                  + [L(f"Section one paragraph {i * 4 + k} with enough words.", 100 * k + 200, i) for k in (1, 2, 3)])
             for i in range(5)]
    found = [pages[p].lines[i].text for p, i in find_furniture(pages)]
    assert not [t for t in found if t.startswith("Section one paragraph")]
    assert sorted(found) == sorted(["Acme Supply Agreement"] * 5 + [f"Schedule 3 - Page {i}" for i in range(1, 6)]
                                   + [f"Page {i} of 5" for i in range(1, 6)])


def test_one_mid_page_copy_does_not_keep_a_running_header_in_the_body():
    """A header stripped on no page at all because the cover page repeats its words once in the
    text is worse than the stray copy it was guarding against."""
    pages = doc(5)
    pages[0] = page(0, [L("Acme Supply Agreement", 40, 0), L("Acme Supply Agreement", 300, 0),
                        L("Body text of page 1", 500, 0), L("Page 1 of 5", 760, 0)])
    found = find_furniture(pages)
    assert sum(1 for p, i in found if pages[p].lines[i].text == "Acme Supply Agreement") == 5


def test_a_header_as_common_in_the_body_as_in_the_band_is_still_furniture():
    """A tie is not evidence that the words are body text: the band copies are stripped."""
    pages = [page(i, [L("Acme Supply Agreement", 40, i), L("Acme Supply Agreement", 300, i),
                      L(f"Page {i + 1} of 5", 760, i)]) for i in range(5)]
    found = find_furniture(pages)
    assert sum(1 for p, i in found if pages[p].lines[i].text == "Acme Supply Agreement") == 5


def test_one_bare_number_in_the_body_does_not_keep_a_repeating_year_line_in_it():
    """Every page number shares the '#' signature with any bare number in the text, so a single
    figure or table cell mid-page must not keep the repeating in-band line."""
    pages = doc(5, extra=lambda i: [L("2026", 700, i)])
    pages[2] = page(2, [L("Acme Supply Agreement", 40, 2), L("42", 300, 2), L("2026", 700, 2),
                        L("Page 3 of 5", 760, 2)])
    found = find_furniture(pages)
    assert sum(1 for p, i in found if pages[p].lines[i].text == "2026") == 5
    assert "42" not in texts(pages, found)
