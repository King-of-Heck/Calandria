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
    assert ch["type"] == "changed" and ch["category"] == "amendment" and ch["cid"] == 1
    assert ch["oi"] == 1 and ch["ni"] == 1 and ch["loc"] is None and ch["marker"] == ""
    assert ch["segments"] == [{"m": "eq", "t": "Beta", "b": False}, {"m": "ins", "t": " two", "b": False}]
    assert ch["fmt_changed"] is False and ch["fmt_descs"] == [] and ch["num_changed"] is False
    assert ch["old_marker"] is None
    assert d["changes"][0] == {"type": "equal", "category": None, "cid": None, "cat": None, "oi": 0, "ni": 0,
                               "loc": None, "marker": "", "old_marker": None, "num_changed": False,
                               "fmt_changed": False, "fmt_descs": [],
                               "segments": [{"m": "eq", "t": "Alpha", "b": False}]}


def test_empty_documents():
    c = compare(_doc(P("")), _doc(P("")))
    assert c.rows == [] and c.summary["total"] == 0 and c.to_dict()["changes"] == []
