import io

import pytest

from calandria.diff.compare import compare, compare_units
from calandria.diff.units import Loc, table_by_ti, units, walk
from calandria.docx.parser import parse_docx
from calandria.layout.merged import merged_items
from calandria.testing.makedocx import DOC, P, TBL, make_docx


def _doc(body):
    return parse_docx(io.BytesIO(make_docx({"word/document.xml": DOC(body)})))


def _cmp(a, b):
    return compare(_doc(a), _doc(b))


def _shape(items):
    return [(it.side, it.row.type if it.row else "empty", it.para.text) for it in items]


def test_walk_includes_empties_and_matches_units_order():
    d = _doc(P("a") + P("") + TBL([["c", ""], ["e", "f"]]) + P("g"))
    w = list(walk(d))
    assert [(p.text, loc) for p, loc in w] == [
        ("a", None), ("", None), ("c", Loc(0, 0, 0, 2)), ("", Loc(0, 0, 1, 2)),
        ("e", Loc(0, 1, 0, 2)), ("f", Loc(0, 1, 1, 2)), ("g", None)]
    assert [u.text for u in units(d)] == ["a", "c", "e", "f", "g"]
    assert [u.loc for u in units(d)] == [None, Loc(0, 0, 0, 2), Loc(0, 1, 0, 2), Loc(0, 1, 1, 2), None]


def test_table_by_ti():
    d = _doc(P("a") + TBL([["x"]]) + P("b") + TBL([["y", "z"]]))
    assert len(table_by_ti(d, 1).rows[0].cells) == 2
    with pytest.raises(IndexError):
        table_by_ti(d, 2)


def test_deleted_paragraph_is_placed_where_it_stood():
    items = merged_items(_cmp(P("One") + P("Two") + P("Three"), P("One") + P("") + P("Three") + P("Four")))
    assert _shape(items) == [("b", "equal", "One"), ("b", "empty", ""), ("a", "deleted", "Two"),
                             ("b", "equal", "Three"), ("b", "inserted", "Four")]
    assert [it.row_index for it in items] == [0, None, 1, 2, 3]


def test_trailing_deletions_come_last():
    items = merged_items(_cmp(P("One") + P("Two") + P("Three"), P("One")))
    assert _shape(items) == [("b", "equal", "One"), ("a", "deleted", "Two"), ("a", "deleted", "Three")]


def test_leading_deletion_precedes_the_first_kept_paragraph():
    items = merged_items(_cmp(P("Gone") + P("Kept"), P("Kept")))
    assert _shape(items) == [("a", "deleted", "Gone"), ("b", "equal", "Kept")]


def test_changed_rows_paired_out_of_order_keep_revised_document_order():
    # dels [0,1] pair with ins [1,0] -> rows: changed(0,1), changed(1,0); the walk is B order.
    a = P("alpha one two three four") + P("beta one two three four")
    b = P("beta one two three five") + P("alpha one two three five")
    items = merged_items(_cmp(a, b))
    assert [it.para.text for it in items] == ["beta one two three five", "alpha one two three five"]
    assert all(it.row.type == "changed" for it in items)


def test_section_index_increments_after_the_closing_paragraph():
    b = (P("cover", ppr='<w:sectPr><w:pgSz w:w="12240" w:h="15840"/></w:sectPr>') + P("body") + P("more"))
    a = P("cover") + P("body") + P("gone") + P("more")
    items = merged_items(_cmp(a, b))
    assert [(it.para.text, it.section) for it in items] == [("cover", 0), ("body", 1), ("gone", 1), ("more", 1)]


def test_table_items_carry_their_side_location():
    # "old value" / "new value" share one of two tokens: similarity 0.5, exactly the pairing threshold.
    a = P("intro") + TBL([["h1", "h2"], ["old value", "x"]]) + P("outro")
    b = P("intro") + TBL([["h1", "h2"], ["new value", "x"]]) + P("outro")
    items = merged_items(_cmp(a, b))
    locs = [(it.side, it.para.text, it.loc) for it in items if it.loc]
    assert locs == [("b", "h1", Loc(0, 0, 0, 2)), ("b", "h2", Loc(0, 0, 1, 2)),
                    ("b", "new value", Loc(0, 1, 0, 2)), ("b", "x", Loc(0, 1, 1, 2))]
    assert items[3].row.type == "changed"


def test_deleted_table_rows_keep_the_original_side_location():
    a = P("intro") + TBL([["h"], ["gone"]]) + P("outro")
    b = P("intro") + TBL([["h"]]) + P("outro")
    items = merged_items(_cmp(a, b))
    gone = next(it for it in items if it.para.text == "gone")
    assert gone.side == "a" and gone.loc == Loc(0, 1, 0, 1) and gone.row.type == "deleted"


def test_requires_the_documents():
    d = _doc(P("x"))
    c = compare_units(units(d), units(d))
    with pytest.raises(ValueError):
        merged_items(c)
