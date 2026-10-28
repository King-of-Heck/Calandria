import json

from calandria.diff.compare import compare
from calandria.docx.parser import parse_docx
from calandria.testing.makedocx import DOC, P, make_docx


def _doc(body):
    return parse_docx(make_docx({"word/document.xml": DOC(body)}))


def test_to_dict_is_json_serializable_and_complete():
    c = compare(_doc(P("Alpha") + P("Beta")), _doc(P("Alpha") + P("Beta two", rpr="<w:i/>")))
    d = c.to_dict()
    json.dumps(d)
    assert d["options"] == {"ignore_case": False, "count_numbering": True}
    assert d["summary"] == c.summary
    ch = d["changes"][1]
    assert ch["type"] == "changed" and ch["cids"] == [1] and ch["num_cid"] is None
    assert ch["oi"] == 1 and ch["ni"] == 1 and ch["loc"] is None and ch["marker"] == ""
    assert ch["segments"] == [{"m": "eq", "t": "Beta", "b": False, "cid": None},
                              {"m": "ins", "t": " two", "b": False, "cid": 1}]
    assert ch["fmt_changed"] is False and ch["fmt_descs"] == [] and ch["num_changed"] is False
    assert ch["old_marker"] is None
    assert d["changes"][0] == {"type": "equal", "cids": [], "num_cid": None, "cat": None, "oi": 0, "ni": 0,
                               "loc": None, "marker": "", "old_marker": None, "num_changed": False,
                               "stream": "body", "note": None, "part": None,
                               "fmt_changed": False, "fmt_descs": [],
                               "segments": [{"m": "eq", "t": "Alpha", "b": False, "cid": None}]}
    assert d["passages"] == [{"cid": 1, "category": "insertion", "row": 1}]


def test_empty_documents():
    c = compare(_doc(P("")), _doc(P("")))
    assert c.rows == [] and c.summary["total"] == 0 and c.to_dict()["changes"] == []


def _toc(title, page):
    from calandria.model import Document, Paragraph, ParaProps, Run, RunProps, Section
    return Document(blocks=[Paragraph([Run(title + "\t", RunProps()),
                                       Run("{PAGEREF}", RunProps(field="PAGEREF", field_text=page))],
                                      ParaProps())], sections=[Section()])


def test_a_contents_line_shows_its_page_numbers_not_the_token():
    # the page number is compared as its token (an edit that moves pages changes no contents
    # line) but the change list and Copy show the number each side prints
    c = compare(_toc("1.1 Definitions", "7"), _toc("1.1 Defined terms", "9"))
    segs = c.to_dict()["changes"][0]["segments"]
    assert "".join(s["t"] for s in segs if s["m"] != "del") == "1.1 Defined terms 9"
    assert "".join(s.get("o", s["t"]) for s in segs if s["m"] != "ins") == "1.1 Definitions 7"
    assert all("o" not in s for s in c.to_dict()["changes"][0]["segments"] if s["m"] != "eq")
    assert c.rows[0].segments[-1].t.endswith("{PAGEREF}")          # the compared text keeps the token
