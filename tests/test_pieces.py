import io

from calandria.diff.compare import compare
from calandria.docx.parser import parse_docx
from calandria.layout.pieces import LayoutOptions, Piece, merge_pieces, row_pieces, visible
from calandria.testing.makedocx import DOC, P, PR, R, make_docx


def _cmp(body_a, body_b):
    a = parse_docx(io.BytesIO(make_docx({"word/document.xml": DOC(body_a)})))
    b = parse_docx(io.BytesIO(make_docx({"word/document.xml": DOC(body_b)})))
    return compare(a, b)


def _text(pieces, modes):
    return "".join(p.text for p in pieces if p.mode in modes)


def test_pieces_reassemble_both_sides_of_a_changed_row():
    c = _cmp(PR(R("The ") + R("quick", "<w:i/>") + R(" brown fox")),
             PR(R("The ") + R("slow", "<w:i/>") + R(" brown ") + R("fox", "<w:b/>")))
    (row,) = c.rows
    assert row.type == "changed"
    ps = row_pieces(c, row, LayoutOptions())
    assert _text(ps, {"del", "eq"}) == "The quick brown fox"
    assert _text(ps, {"ins", "eq"}) == "The slow brown fox"
    assert [p.italic for p in ps if p.text == "quick"] == [True]
    assert [p.italic for p in ps if p.text == "slow"] == [True]
    assert [p.bold for p in ps if p.text == "fox"] == [True]
    assert all(p.cid == 1 for p in ps)


def test_dense_rewrite_duplicates_the_shared_connective_into_both_sides():
    # coalesce() folds " and " into the struck and the inserted phrase; the two cursors must
    # both advance over it, or every later offset would be wrong.
    c = _cmp(P("Red and blue cars are parked outside."), P("Green and yellow cars are parked outside."))
    (row,) = c.rows
    ps = row_pieces(c, row, LayoutOptions())
    assert _text(ps, {"del", "eq"}) == "Red and blue cars are parked outside."
    assert _text(ps, {"ins", "eq"}) == "Green and yellow cars are parked outside."


def test_deleted_row_takes_formatting_from_the_original():
    c = _cmp(P("Keep") + P("Gone away", rpr='<w:u w:val="single"/>'), P("Keep"))
    row = c.rows[1]
    assert row.type == "deleted"
    (p,) = row_pieces(c, row, LayoutOptions())
    assert p.mode == "del" and p.underline and p.text == "Gone away"


def test_equal_row_with_a_formatting_change_flags_the_range():
    c = _cmp(P("Bold words appear here"), PR(R("Bold ") + R("words", "<w:b/>") + R(" appear here")))
    (row,) = c.rows
    assert row.fmt_changed
    ps = row_pieces(c, row, LayoutOptions())
    assert [(p.text, p.bold, p.fmt) for p in ps] == [("Bold ", False, False), ("words", True, True),
                                                     (" appear here", False, False)]
    off = row_pieces(c, row, LayoutOptions(show_formatting=False))
    assert not any(p.fmt for p in off) and [p.bold for p in off] == [False, True, False]


def test_hidden_modes_drop_their_pieces():
    c = _cmp(P("alpha beta gamma"), P("alpha delta gamma"))
    (row,) = c.rows
    no_del = row_pieces(c, row, LayoutOptions(show_deletions=False))
    assert _text(no_del, {"del"}) == "" and _text(no_del, {"ins", "eq"}) == "alpha delta gamma"
    no_ins = row_pieces(c, row, LayoutOptions(show_insertions=False))
    assert _text(no_ins, {"ins"}) == "" and _text(no_ins, {"del", "eq"}) == "alpha beta gamma"


def test_size_font_and_colour_ride_on_pieces():
    c = _cmp(P("x"), P("x") + P("Big red", rpr='<w:sz w:val="28"/><w:color w:val="FF0000"/><w:rFonts w:ascii="Arial"/>'))
    (p,) = row_pieces(c, c.rows[1], LayoutOptions())
    assert (p.mode, p.size, p.color, p.font) == ("ins", 14.0, "ff0000", "Arial")


def test_merge_pieces_joins_same_style_neighbours():
    a = Piece("ab", "eq", cid=1)
    b = Piece("cd", "eq", cid=1)
    other = Piece("ef", "ins", cid=1)
    assert [p.text for p in merge_pieces([a, b, other])] == ["abcd", "ef"]


def test_visible_follows_the_show_toggles():
    c = _cmp(P("same") + P("gone") + P("old text here"), P("same") + P("new text here") + P("added"))
    eq, dele, chg, ins = c.rows
    assert (eq.type, dele.type, chg.type, ins.type) == ("equal", "deleted", "changed", "inserted")
    assert visible(eq, LayoutOptions()) and not visible(eq, LayoutOptions(show_equal=False))
    assert not visible(dele, LayoutOptions(show_deletions=False))
    assert not visible(ins, LayoutOptions(show_insertions=False))
    assert visible(chg, LayoutOptions(show_insertions=False))
    assert not visible(chg, LayoutOptions(show_insertions=False, show_deletions=False))


def test_numbering_or_formatting_change_keeps_an_equal_row_visible_under_hide_unchanged():
    c = _cmp(P("Bold words appear here"), PR(R("Bold ") + R("words", "<w:b/>") + R(" appear here")))
    (row,) = c.rows
    assert visible(row, LayoutOptions(show_equal=False))
    assert not visible(row, LayoutOptions(show_equal=False, show_formatting=False))
