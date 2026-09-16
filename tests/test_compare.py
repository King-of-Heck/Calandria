from calandria.diff.compare import compare, compare_units
from calandria.diff.inline import Seg
from calandria.diff.units import Loc, units
from calandria.docx.parser import parse_docx
from calandria.testing.makedocx import DOC, P, W_NS, make_docx


def _doc(body, **parts):
    return parse_docx(make_docx({"word/document.xml": DOC(body), **parts}))


def _flat(row):
    out = []
    for s in row.segments:
        if out and out[-1][0] == s.m:
            out[-1] = (s.m, out[-1][1] + s.t)
        else:
            out.append((s.m, s.t))
    return out


def test_insert_change_and_equal_rows_with_cids():
    a = _doc(P("Alpha") + P("Beta") + P("Gamma"))
    b = _doc(P("Alpha") + P("Beta two") + P("Gamma") + P("Delta"))
    c = compare(a, b)
    assert [(r.type, r.oi, r.ni, r.cids) for r in c.rows] == [
        ("equal", 0, 0, []), ("changed", 1, 1, [1]), ("equal", 2, 2, []), ("inserted", None, 3, [2])]
    assert _flat(c.rows[1]) == [("eq", "Beta"), ("ins", " two")] and c.rows[1].cat == "content"
    assert _flat(c.rows[3]) == [("ins", "Delta")]
    assert c.summary == {"insertions": 2, "deletions": 0, "moves": 0, "content": 2,
                         "numbering": 0, "punctuation": 0, "total": 2, "formatting": 0, "splits": 0,
                         "merges": 0, "numbering_changes": 0}
    assert c.passages[0].category == "insertion" and c.passages[1].category == "insertion"


def test_unpaired_delete_below_threshold_and_row_order():
    a = _doc(P("one two three four") + P("keep"))
    b = _doc(P("completely different words here") + P("keep"))
    c = compare(a, b)
    assert [(r.type, r.cids) for r in c.rows] == [("deleted", [1]), ("inserted", [2]), ("equal", [])]
    assert c.summary["deletions"] == 1 and c.summary["insertions"] == 1 and c.summary["total"] == 2


def test_punctuation_and_case_categories():
    a = _doc(P("Hello, world.") + P("The Provider shall deliver."))
    b = _doc(P("Hello world") + P("The provider shall deliver."))
    c = compare(a, b)
    assert [r.cat for r in c.rows] == ["punctuation", "punctuation"]
    assert c.summary["punctuation"] == 2 and c.summary["content"] == 0
    s = c.summary
    assert s["deletions"] == 3 and s["insertions"] == 1 and s["insertions"] + s["deletions"] == s["total"]


def test_ignore_case_pairs_at_paragraph_level_but_renders_raw_text():
    a = _doc(P("Hello World"))
    b = _doc(P("hello world"))
    c = compare(a, b, ignore_case=True)
    assert [r.type for r in c.rows] == ["equal"] and c.summary["total"] == 0
    assert c.rows[0].segments == [Seg("eq", "hello world")]     # the revised text
    d = compare(_doc(P("Alpha beta gamma delta")), _doc(P("alpha beta gamma delta")), ignore_case=True)
    assert d.rows[0].type == "equal"


def test_formatting_only_change_is_uncounted():
    a = _doc(P("Bold me"))
    b = _doc(P("Bold me", rpr="<w:b/>"))
    c = compare(a, b)
    r = c.rows[0]
    assert r.cids == [] and r.type == "equal" and r.fmt_changed
    assert [(x.s, x.e, x.desc) for x in r.fmt_ranges] == [(0, 7, "bold added")]
    assert c.summary["formatting"] == 1 and c.summary["total"] == 0


_NUMBERING = (f'<w:numbering xmlns:w="{W_NS}"><w:abstractNum w:abstractNumId="0">'
              '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/></w:lvl>'
              '</w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>')
_NUM_PPR = '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>'


def _item(t):
    return P(t, ppr=_NUM_PPR)


def test_renumbering_is_a_marker_meta_compare():
    a = _doc(_item("first") + _item("second") + _item("third"), **{"word/numbering.xml": _NUMBERING})
    b = _doc(_item("new") + _item("first") + _item("second") + _item("third"),
             **{"word/numbering.xml": _NUMBERING})
    c = compare(a, b)
    assert [(r.type, r.num_changed, r.old_marker, r.cids) for r in c.rows] == [
        ("inserted", False, None, [1]), ("equal", True, "1.", [2]), ("equal", True, "2.", [3]), ("equal", True, "3.", [4])]
    assert c.passages[1].category == "numbering" and c.rows[1].num_cid == 2 and c.b_units[1].marker == "2."
    assert c.summary["numbering"] == 3 and c.summary["total"] == 4 and c.summary["insertions"] == 1
    u = compare(a, b, count_numbering=False)
    assert [r.cids for r in u.rows] == [[1], [], [], []]
    assert u.summary["numbering"] == 3 and u.summary["total"] == 1


def test_changed_row_that_also_renumbers_carries_a_numbering_passage_and_a_text_passage():
    a = _doc(_item("first item") + _item("second item"), **{"word/numbering.xml": _NUMBERING})
    b = _doc(_item("zero") + _item("first item") + _item("second item edited"),
             **{"word/numbering.xml": _NUMBERING})
    c = compare(a, b)
    ch = [r for r in c.rows if r.type == "changed"][0]
    assert ch.num_changed and ch.old_marker == "2." and ch.cids == [3, 4] and ch.num_cid == 3
    assert c.summary["numbering"] == 2 and c.summary["insertions"] == 2 \
        and c.summary["numbering_changes"] == 2 and c.summary["total"] == 4


def test_table_cells_diff_as_units_with_locations():
    tbl = lambda rows: "<w:tbl>" + "".join(
        "<w:tr>" + "".join(f"<w:tc>{P(c)}</w:tc>" for c in r) + "</w:tr>" for r in rows) + "</w:tbl>"
    # "10 units" -> "12 units" pairs (sim 0.5); a bare "10" -> "12" would not (single differing
    # tokens have similarity 0) and would render as a delete + insert, exactly as in the reference.
    a = _doc(P("Intro") + tbl([["Item", "Qty"], ["Bolt", "10 units"]]))
    b = _doc(P("Intro") + tbl([["Item", "Qty"], ["Bolt", "12 units"], ["Nut", "5"]]))
    c = compare(a, b)
    types = [(r.type, c.unit_for(r).loc) for r in c.rows]
    assert types[:4] == [("equal", None), ("equal", Loc(0, 0, 0, 2)), ("equal", Loc(0, 0, 1, 2)),
                         ("equal", Loc(0, 1, 0, 2))]
    assert types[4] == ("changed", Loc(0, 1, 1, 2))
    assert [t for t, _ in types].count("inserted") == 2
    assert c.summary["total"] == 4   # "10 units" -> "12 units" numbers the deletion then the insertion


def test_compare_carries_both_documents_but_compare_units_does_not():
    a = _doc(P("Alpha"))
    b = _doc(P("Alpha two"))
    c = compare(a, b)
    assert c.a_doc is a and c.b_doc is b
    cu = compare_units(units(a), units(b))
    assert cu.a_doc is None and cu.b_doc is None


def test_delete_group_without_inserts():
    a = _doc(P("one") + P("two") + P("three"))
    b = _doc(P("one") + P("three"))
    c = compare(a, b)
    assert [r.type for r in c.rows] == ["equal", "deleted", "equal"]
    assert (c.summary["deletions"], c.summary["insertions"], c.summary["total"]) == (1, 0, 1)


def test_all_deleted_document():
    a = _doc(P("one") + P("two"))
    b = _doc("")
    c = compare(a, b)
    assert [r.type for r in c.rows] == ["deleted", "deleted"]
    assert (c.summary["deletions"], c.summary["total"], c.rows[1].cids) == (2, 2, [2])


def test_all_inserted_document():
    a = _doc("")
    b = _doc(P("one") + P("two"))
    c = compare(a, b)
    assert [r.type for r in c.rows] == ["inserted", "inserted"]
    assert (c.summary["insertions"], c.summary["total"], c.rows[1].cids) == (2, 2, [2])


def test_note_rows_are_counted_and_never_pair_with_body_text():
    from calandria.model import NoteRef
    from calandria.testing.makedocx import FNREF, FOOTNOTES, PR, R
    a = _doc(PR(R("Body text") + FNREF(1)) + P("Same words here"),
             **{"word/footnotes.xml": FOOTNOTES({1: "Invoice date."})})
    b = _doc(PR(R("Body text") + FNREF(1)) + PR(R("Other") + FNREF(2)),
             **{"word/footnotes.xml": FOOTNOTES({1: "Invoice date, not delivery.", 2: "Same words here"})})
    c = compare(a, b)
    kinds = [(r.type, c.unit_for(r).stream) for r in c.rows]
    # the edited note is a changed row right after its anchor; the body paragraph whose text moved
    # into a note is a deletion plus an insertion, never an equal pair across streams
    assert kinds == [("equal", "body"), ("changed", "footnote"), ("deleted", "body"), ("inserted", "body"),
                     ("inserted", "footnote")]
    assert c.summary["total"] == 4 and c.summary["insertions"] == 3 and c.summary["deletions"] == 1
    d = c.to_dict()["changes"]
    assert d[1]["stream"] == "footnote" and d[1]["note"] == {"kind": "footnote", "id": 1}
    assert d[0]["stream"] == "body" and d[0]["note"] is None
