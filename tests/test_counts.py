"""v2.4.7: a numbered change is classified by its content; the summary counts per category and
tallies contiguous inserted / deleted runs (spec section 13)."""
import json
from pathlib import Path

import pytest

from calandria.diff.changes import SUMMARY_KEYS, Row, empty_summary, run_counts
from calandria.diff.compare import compare
from calandria.diff.inline import Seg
from calandria.docx.parser import parse_docx
from calandria.testing.makedocx import DOC, P, W_NS, make_docx

CORPUS = Path(__file__).parent / "corpus"


def _doc(body):
    return parse_docx(make_docx({"word/document.xml": DOC(body)}))


def _changed(*segs):
    return Row("changed", 0, 0, [Seg(m, t) for m, t in segs], cid=1, cat="content")


def test_changed_row_with_only_inserted_text_is_an_insertion():
    assert _changed(("eq", "Beta"), ("ins", " two")).category == "insertion"


def test_changed_row_with_only_deleted_text_is_a_deletion():
    assert _changed(("eq", "Hello"), ("del", ","), ("eq", " world")).category == "deletion"


def test_changed_row_with_both_is_an_amendment():
    assert _changed(("del", "September"), ("ins", "October"), ("eq", " 1")).category == "amendment"


def test_changed_row_without_marked_text_falls_back_to_amendment():
    assert _changed(("eq", "same"),).category == "amendment"


def test_inserted_and_deleted_rows_keep_their_category():
    assert Row("inserted", None, 0, [Seg("ins", "x")], cid=1).category == "insertion"
    assert Row("deleted", 0, None, [Seg("del", "x")], cid=1).category == "deletion"


def test_run_counts_count_maximal_runs():
    assert run_counts([Seg("ins", "Delta")]) == (1, 0)
    assert run_counts([Seg("del", "a"), Seg("del", "b", b=True)]) == (0, 1)       # a bold split is one run
    assert run_counts([Seg("ins", "a"), Seg("eq", " and "), Seg("ins", "b")]) == (2, 0)
    assert run_counts([Seg("del", "x"), Seg("ins", "y"), Seg("eq", " z")]) == (1, 1)
    assert run_counts([]) == (0, 0)


def test_summary_keys_include_the_run_tallies():
    assert "inserted_runs" in SUMMARY_KEYS and "deleted_runs" in SUMMARY_KEYS
    assert empty_summary()["inserted_runs"] == 0


def test_summary_counts_numbered_rows_per_category_and_tallies_runs():
    a = _doc(P("Alpha") + P("Hello, world.") + P("Beta") + P("Gamma") + P("Gone"))
    b = _doc(P("Alpha") + P("Hello world") + P("Beta two") + P("Gamma") + P("Delta"))
    c = compare(a, b)
    by_cid = [r for r in c.rows if r.cid is not None]
    cats = [r.category for r in by_cid]
    assert cats.count("insertion") == c.summary["insertions"]
    assert cats.count("deletion") == c.summary["deletions"]
    assert cats.count("amendment") == c.summary["amendments"]
    assert cats.count("numbering") == c.summary["numbering_changes"]
    s = c.summary
    assert (s["insertions"] + s["deletions"] + s["amendments"] + s["numbering_changes"]
            == s["total"])
    ins = sum(run_counts(r.segments)[0] for r in by_cid)
    dele = sum(run_counts(r.segments)[1] for r in by_cid)
    assert (c.summary["inserted_runs"], c.summary["deleted_runs"]) == (ins, dele)
    assert c.summary["inserted_runs"] >= c.summary["insertions"] + c.summary["amendments"]
    assert c.summary["deleted_runs"] >= c.summary["deletions"] + c.summary["amendments"]


@pytest.mark.skipif(not (CORPUS / "manifest.json").exists(), reason="corpus not present")
@pytest.mark.parametrize("pair", json.loads((CORPUS / "manifest.json").read_text("utf8"))["pairs"]
                         if (CORPUS / "manifest.json").exists() else [], ids=lambda p: p["alias"])
def test_tiles_sum_to_total_on_every_corpus_pair(pair):
    c = compare(parse_docx((CORPUS / pair["a"]).read_bytes()), parse_docx((CORPUS / pair["b"]).read_bytes()))
    s = c.summary
    numbering_only = sum(1 for r in c.rows if r.cid is not None and r.category == "numbering")
    assert numbering_only == s["numbering_changes"]
    assert s["insertions"] + s["deletions"] + s["amendments"] + s["numbering_changes"] == s["total"]
    assert s["inserted_runs"] >= s["insertions"] and s["deleted_runs"] >= s["deletions"]


_NUMBERING = (f'<w:numbering xmlns:w="{W_NS}"><w:abstractNum w:abstractNumId="0">'
              '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/></w:lvl>'
              '</w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>')
_NUM_PPR = '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>'


def _item(t):
    return P(t, ppr=_NUM_PPR)


def _numbered_doc(body):
    return parse_docx(make_docx({"word/document.xml": DOC(body), "word/numbering.xml": _NUMBERING}))


def test_changed_and_renumbered_row_counts_numbering_changes_once():
    a = _numbered_doc(_item("first item") + _item("second item"))
    b = _numbered_doc(_item("zero") + _item("first item") + _item("second item edited"))
    c = compare(a, b)
    s = c.summary
    assert s["numbering"] == 2
    assert s["numbering_changes"] == 1
    assert s["insertions"] + s["deletions"] + s["amendments"] + s["numbering_changes"] == s["total"] == 3


def test_changed_and_renumbered_row_with_numbering_uncounted():
    a = _numbered_doc(_item("first item") + _item("second item"))
    b = _numbered_doc(_item("zero") + _item("first item") + _item("second item edited"))
    c = compare(a, b, count_numbering=False)
    s = c.summary
    assert s["numbering"] == 2
    assert s["numbering_changes"] == 0
    assert s["insertions"] + s["deletions"] + s["amendments"] + s["numbering_changes"] == s["total"]
