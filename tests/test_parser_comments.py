import io

from calandria.docx.parser import parse_docx
from calandria.testing.makedocx import (COMMENTS, COMMENTS_EX, CRANGE, CREF, CRELS, DOC, P, PEOPLE, PR, R,
                                        make_docx)


def _doc(body, comments=None, comments_ex=None, people=None):
    files = {"word/document.xml": DOC(body)}
    files["word/_rels/document.xml.rels"] = CRELS(comments=comments is not None,
                                                  comments_ex=comments_ex is not None,
                                                  people=people is not None)
    if comments is not None:
        files["word/comments.xml"] = COMMENTS(comments)
    if comments_ex is not None:
        files["word/commentsExtended.xml"] = COMMENTS_EX(comments_ex)
    if people is not None:
        files["word/people.xml"] = PEOPLE(people)
    return parse_docx(io.BytesIO(make_docx(files)))


def test_comment_metadata_and_body_are_read():
    body = PR(R("The ") + CRANGE("0", "quick brown") + R(" fox."))
    d = _doc(body, comments=[{"id": "0", "author": "Ada L", "initials": "AL", "date": "2026-09-16T10:00:00Z",
                              "paras": [("p1", "Is this right?")]}])
    c = d.comments["0"]
    assert (c.author, c.initials, c.date) == ("Ada L", "AL", "2026-09-16T10:00:00Z")
    assert [p.text for p in c.paras] == ["Is this right?"]
    assert c.para_ids == ["p1"] and c.parent_id is None and c.done is False


def test_no_comments_part_leaves_the_maps_empty_and_is_empty_unchanged():
    d = _doc(P("Plain paragraph."))
    assert d.comments == {} and d.comment_anchors == {}


def test_comment_marker_does_not_make_a_paragraph_non_empty_or_add_text():
    body = PR(CREF("0"))                      # a paragraph holding only a comment reference
    d = _doc(body, comments=[{"id": "0", "author": "X", "paras": [("p1", "note")]}])
    assert d.blocks[0].is_empty is True and d.blocks[0].text == ""


def test_anchor_start_end_and_ref_offsets_are_captured_on_the_paragraph():
    body = PR(R("The ") + CRANGE("0", "quick brown") + R(" fox."))
    d = _doc(body, comments=[{"id": "0", "author": "X", "paras": [("p1", "n")]}])
    a = d.comment_anchors["0"]
    para = d.blocks[0]
    assert a.start[0] is para and a.start[1] == len("The ")
    assert a.end[0] is para and a.end[1] == len("The quick brown")
    assert a.ref[0] is para and a.ref[1] == len("The quick brown")


def test_point_anchor_has_ref_but_no_range():
    d = _doc(PR(R("Point here") + CREF("7")), comments=[{"id": "7", "author": "X", "paras": [("p1", "n")]}])
    a = d.comment_anchors["7"]
    assert a.start is None and a.end is None and a.ref[1] == len("Point here")


def test_threading_and_done_join_by_paraid():
    body = PR(CRANGE("0", "text")) + PR(CRANGE("1", "more"))
    d = _doc(body,
             comments=[{"id": "0", "author": "A", "paras": [("pa", "parent")]},
                       {"id": "1", "author": "B", "paras": [("pb", "reply")]}],
             comments_ex=[{"paraId": "pa", "done": True}, {"paraId": "pb", "parent": "pa"}])
    assert d.comments["0"].done is True and d.comments["0"].parent_id is None
    assert d.comments["1"].parent_id == "pa" and d.comments["1"].done is False


def test_multi_paragraph_comment_keeps_all_paras_and_ids():
    d = _doc(PR(CRANGE("0", "x")),
             comments=[{"id": "0", "author": "A", "paras": [("p1", "line one"), ("p2", "line two")]}])
    c = d.comments["0"]
    assert [p.text for p in c.paras] == ["line one", "line two"] and c.para_ids == ["p1", "p2"]
