"""v2.5.0: a numbered change is a passage (spec section 14): inserted / deleted runs formed per
side, bridged by whitespace-only equal text and by the other side's segments, plus one numbering
passage per renumbered marker; numbered in reading order; the three counts add up to the total."""
import json
from pathlib import Path

import pytest

from calandria.diff.changes import SUMMARY_KEYS, Passage, Row, empty_summary, row_passages
from calandria.diff.compare import compare
from calandria.diff.inline import Seg
from calandria.docx.parser import parse_docx
from calandria.testing.makedocx import DOC, P, W_NS, make_docx

CORPUS = Path(__file__).parent / "corpus"


def _row(*segs, type="changed", num_changed=False):
    return Row(type, 0, 0, [Seg(m, t) for m, t in segs], cat="content",
               num_changed=num_changed, old_marker="1." if num_changed else None)


def _cats(ps):
    return [(p.cid, p.category) for p in ps]


def test_whitespace_only_equal_text_does_not_break_a_passage():
    r = _row(("eq", "Pro"), ("ins", ","), ("eq", " "), ("ins", "where applicable "), ("eq", "50"))
    assert _cats(row_passages(r, 0, 1, True)) == [(1, "insertion")]
    assert [s.cid for s in r.segments] == [None, 1, None, 1, None]
    assert r.cids == [1] and r.num_cid is None


def test_whitespace_only_equal_text_does_not_break_a_deleted_passage():
    r = _row(("eq", "Pro"), ("del", ","), ("eq", " "), ("del", "gone "), ("eq", "50"))
    assert _cats(row_passages(r, 0, 1, True)) == [(1, "deletion")]
    assert [s.cid for s in r.segments] == [None, 1, None, 1, None]


def test_the_other_sides_segment_does_not_break_a_passage():
    r = _row(("eq", "time"), ("ins", ","), ("eq", " "), ("del", "OPG"), ("ins", "where applicableOPG "), ("eq", "engaged"))
    assert _cats(row_passages(r, 0, 1, True)) == [(1, "insertion"), (2, "deletion")]
    assert [s.cid for s in r.segments] == [None, 1, None, 2, 1, None]
    assert r.cids == [1, 2]


def test_visible_equal_text_ends_both_passages():
    r = _row(("ins", "a"), ("del", "x"), ("eq", " and "), ("ins", "b"), ("del", "y"))
    assert _cats(row_passages(r, 0, 1, True)) == [(1, "insertion"), (2, "deletion"), (3, "insertion"), (4, "deletion")]


def test_a_replacement_numbers_the_deletion_then_the_insertion():
    r = _row(("del", "September"), ("ins", "October"), ("eq", " 1"))
    assert _cats(row_passages(r, 0, 7, True)) == [(7, "deletion"), (8, "insertion")]
    assert r.cids == [7, 8] and [s.cid for s in r.segments] == [7, 8, None]


def test_a_bold_split_continues_a_passage():
    r = Row("changed", 0, 0, [Seg("ins", "bold", True), Seg("ins", " plain")], cat="content")
    assert _cats(row_passages(r, 0, 1, True)) == [(1, "insertion")]


def test_a_whole_inserted_paragraph_is_one_passage_carrying_its_row_index():
    r = Row("inserted", None, 0, [Seg("ins", "New "), Seg("ins", "para", True)])
    (p,) = row_passages(r, 3, 5, True)
    assert p == Passage(5, "insertion", 3) and p.as_dict() == {"cid": 5, "category": "insertion", "row": 3}
    assert r.cids == [5]


def test_an_edited_and_renumbered_paragraph_yields_the_numbering_passage_first():
    r = _row(("eq", "second item"), ("ins", " edited"), num_changed=True)
    assert _cats(row_passages(r, 0, 4, True)) == [(4, "numbering"), (5, "insertion")]
    assert r.num_cid == 4 and r.cids == [4, 5] and r.segments[1].cid == 5
    assert _cats(row_passages(r, 0, 4, False)) == [(4, "insertion")]
    assert r.num_cid is None and r.cids == [4]


def test_a_renumbered_equal_row_yields_only_the_numbering_passage():
    r = Row("equal", 0, 0, [Seg("eq", "same")], num_changed=True, old_marker="2.")
    assert _cats(row_passages(r, 0, 9, True)) == [(9, "numbering")] and r.cids == [9] and r.num_cid == 9
    assert row_passages(r, 0, 9, False) == [] and r.cids == [] and r.num_cid is None


def test_a_changed_row_without_marked_text_has_no_passage():
    r = _row(("eq", "same"))
    assert row_passages(r, 0, 1, True) == [] and r.cids == [] and r.num_cid is None


def test_summary_keys_are_the_three_counts_plus_the_gate_keys():
    assert SUMMARY_KEYS == ("insertions", "deletions", "moves", "content", "numbering", "punctuation",
                            "total", "formatting", "splits", "merges", "numbering_changes")
    s = empty_summary()
    assert set(s) == set(SUMMARY_KEYS) and all(v == 0 for v in s.values())


def _doc(body, **parts):
    return parse_docx(make_docx({"word/document.xml": DOC(body), **parts}))


def test_compare_numbers_passages_in_reading_order_and_counts_them():
    c = compare(_doc(P("Alpha") + P("The old value here") + P("gone")),
                _doc(P("Alpha") + P("The new value there") + P("added")))
    assert [p.as_dict() for p in c.passages] == [
        {"cid": 1, "category": "deletion", "row": 1}, {"cid": 2, "category": "insertion", "row": 1},
        {"cid": 3, "category": "deletion", "row": 1}, {"cid": 4, "category": "insertion", "row": 1},
        {"cid": 5, "category": "deletion", "row": 2}, {"cid": 6, "category": "insertion", "row": 3}]
    assert [r.cids for r in c.rows] == [[], [1, 2, 3, 4], [5], [6]]
    s = c.summary
    assert (s["insertions"], s["deletions"], s["numbering_changes"], s["total"]) == (3, 3, 0, 6)
    assert (s["content"], s["punctuation"], s["numbering"], s["formatting"]) == (3, 0, 0, 0)
    d = c.to_dict()
    assert d["passages"] == [p.as_dict() for p in c.passages]
    assert d["changes"][1]["cids"] == [1, 2, 3, 4] and d["changes"][1]["num_cid"] is None
    segs = d["changes"][1]["segments"]                     # one segment per token: the equal text is several
    assert [s["cid"] for s in segs if s["m"] != "eq"] == [1, 2, 3, 4]
    assert all(s["cid"] is None for s in segs if s["m"] == "eq")
    assert "cid" not in d["changes"][1] and "category" not in d["changes"][1]
    json.dumps(d)


def test_a_case_only_change_under_ignore_case_is_not_a_passage():
    c = compare(_doc(P("Alpha") + P("Beta gamma")), _doc(P("Alpha") + P("beta gamma")), ignore_case=True)
    assert c.passages == [] and c.summary["total"] == 0
    assert all(r.cids == [] and r.num_cid is None for r in c.rows)
    assert all(s.cid is None for r in c.rows for s in r.segments)


_NUMBERING = (f'<w:numbering xmlns:w="{W_NS}"><w:abstractNum w:abstractNumId="0">'
              '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/></w:lvl>'
              '</w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>')
_NUM_PPR = '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>'


def _item(t):
    return P(t, ppr=_NUM_PPR)


def _numbered(body):
    return _doc(body, **{"word/numbering.xml": _NUMBERING})


def test_an_edited_and_renumbered_item_counts_both_passages():
    a = _numbered(_item("first item") + _item("second item"))
    b = _numbered(_item("zero") + _item("first item") + _item("second item edited"))
    c = compare(a, b)
    assert [p.as_dict() for p in c.passages] == [
        {"cid": 1, "category": "insertion", "row": 0}, {"cid": 2, "category": "numbering", "row": 1},
        {"cid": 3, "category": "numbering", "row": 2}, {"cid": 4, "category": "insertion", "row": 2}]
    s = c.summary
    assert (s["insertions"], s["deletions"], s["numbering_changes"], s["total"], s["numbering"]) == (2, 0, 2, 4, 2)
    u = compare(a, b, count_numbering=False)
    assert [p.cid for p in u.passages] == [1, 2] and u.summary["total"] == 2 and u.summary["numbering"] == 2
    assert u.rows[2].num_cid is None and u.rows[2].cids == [2]


@pytest.mark.skipif(not (CORPUS / "manifest.json").exists(), reason="corpus not present")
@pytest.mark.parametrize("pair", json.loads((CORPUS / "manifest.json").read_text("utf8"))["pairs"]
                         if (CORPUS / "manifest.json").exists() else [], ids=lambda p: p["alias"])
@pytest.mark.parametrize("count_numbering", [True, False])
def test_counts_add_up_and_numbers_are_dense_on_every_corpus_pair(pair, count_numbering):
    c = compare(parse_docx((CORPUS / pair["a"]).read_bytes()), parse_docx((CORPUS / pair["b"]).read_bytes()),
                count_numbering=count_numbering)
    s = c.summary
    assert s["insertions"] + s["deletions"] + s["numbering_changes"] == s["total"] == len(c.passages)
    assert [p.cid for p in c.passages] == list(range(1, s["total"] + 1))
    assert [c for r in c.rows for c in r.cids] == [p.cid for p in c.passages]
    for k, r in enumerate(c.rows):
        assert sorted({s.cid for s in r.segments if s.cid is not None} | ({r.num_cid} - {None})) == sorted(r.cids)
        assert all(p.row == k for p in c.passages if p.cid in r.cids)
    if not count_numbering:
        assert s["numbering_changes"] == 0
