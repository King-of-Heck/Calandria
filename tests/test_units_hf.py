import io

from calandria.diff.compare import compare
from calandria.diff.units import Loc, units, walk
from calandria.docx.parser import parse_docx
from calandria.layout.merged import merged_items
from calandria.testing.makedocx import DOC, FLD, FTR, HDR, P, PR, R, RELS, SECT, TBL, make_docx

RELS_ = RELS({"rId1": "header1.xml", "rId2": "header2.xml", "rId3": "footer1.xml"})


def _doc(body, header1=None, header2=None, footer1=None):
    files = {"word/document.xml": DOC(body), "word/_rels/document.xml.rels": RELS_}
    if header1 is not None:
        files["word/header1.xml"] = HDR(header1)
    if header2 is not None:
        files["word/header2.xml"] = HDR(header2)
    if footer1 is not None:
        files["word/footer1.xml"] = FTR(footer1)
    return parse_docx(io.BytesIO(make_docx(files)))


SECT1 = SECT(hdr={"default": "rId1", "first": "rId2"}, ftr={"default": "rId3"}, title_pg=True)


def test_walk_yields_header_then_footer_streams_after_the_body():
    d = _doc(P("body") + SECT1, header1=P("Running") + P(""), header2=P("Cover"), footer1=PR(R("p ") + FLD("PAGE")))
    out = [(p.text, where.stream, where.part) for p, _loc, where in walk(d)]
    assert out == [("body", "body", None), ("Cover", "header", "header2.xml"), ("Running", "header", "header1.xml"),
                   ("", "header", "header1.xml"), ("p {PAGE}", "footer", "footer1.xml")]
    us = units(d)
    assert [(u.text, u.stream, u.part) for u in us][1:] == [("Cover", "header", "header2.xml"),
                                                           ("Running", "header", "header1.xml"),
                                                           ("p {PAGE}", "footer", "footer1.xml")]


def test_header_table_cells_get_a_loc_counted_within_the_part():
    d = _doc(P("body") + SECT1, header1=P("x") + TBL([["a", "b"]]))
    locs = [(p.text, loc) for p, loc, where in walk(d) if where.stream == "header"]
    assert locs == [("x", None), ("a", Loc(0, 0, 0, 2)), ("b", Loc(0, 0, 1, 2))]


def test_header_units_never_pair_with_body_units():
    a = _doc(P("Same words") + SECT1, header1=P("Header text"))
    b = _doc(P("Header text") + SECT1, header1=P("Same words"))
    c = compare(a, b)
    assert [(r.type, c.unit_for(r).stream) for r in c.rows] == [("deleted", "body"), ("inserted", "body"),
                                                                ("deleted", "header"), ("inserted", "header")]


def test_a_changed_header_is_one_counted_passage_with_its_stream_in_the_row_dict():
    a = _doc(P("body") + SECT1, header1=P("Draft"))
    b = _doc(P("body") + SECT1, header1=P("Draft final"))
    c = compare(a, b)
    assert c.summary["total"] == 1
    rows = c.to_dict()["changes"]
    assert rows[1]["stream"] == "header" and rows[1]["part"] == "header1.xml" and rows[0]["part"] is None


def test_page_numbers_never_differ():
    a = _doc(P("body") + SECT1, footer1=PR(R("- ") + FLD("PAGE", "3") + R(" -")))
    b = _doc(P("body") + SECT1, footer1=PR(R("- ") + FLD("PAGE", "17") + R(" -")))
    assert compare(a, b).summary["total"] == 0


def test_merged_items_give_deleted_header_rows_the_neighbouring_revised_part():
    a = _doc(P("body") + SECT1, header1=P("Old head"), footer1=P("Old foot"))
    b = _doc(P("body") + SECT1, header1=P("New head"), footer1=P("New foot"))
    items = merged_items(compare(a, b))
    hf = [(it.side, it.stream, it.part, it.para.text) for it in items if it.stream != "body"]
    assert hf == [("a", "header", "header1.xml", "Old head"), ("b", "header", "header1.xml", "New head"),
                  ("a", "footer", "footer1.xml", "Old foot"), ("b", "footer", "footer1.xml", "New foot")]


def test_deleted_header_rows_with_no_revised_part_keep_their_stream_and_no_part():
    a = _doc(P("body") + SECT1, header1=P("Gone head"))
    b = _doc(P("body") + SECT1)
    items = merged_items(compare(a, b))
    assert [(it.side, it.stream, it.part) for it in items if it.stream != "body"] == [("a", "header", None)]
