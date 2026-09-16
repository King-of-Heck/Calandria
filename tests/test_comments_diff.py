import io

from calandria.diff.compare import compare
from calandria.docx.parser import parse_docx
from calandria.testing.makedocx import COMMENTS, COMMENTS_EX, CRANGE, CRELS, DOC, P, PR, R, make_docx


def _doc(body, comments=None, comments_ex=None):
    files = {"word/document.xml": DOC(body),
             "word/_rels/document.xml.rels": CRELS(comments=comments is not None,
                                                   comments_ex=comments_ex is not None)}
    if comments is not None:
        files["word/comments.xml"] = COMMENTS(comments)
    if comments_ex is not None:
        files["word/commentsExtended.xml"] = COMMENTS_EX(comments_ex)
    return parse_docx(io.BytesIO(make_docx(files)))


def _cc(a, b):
    return compare(a, b).comments


def test_added_comment_only_in_the_revised_document():
    a = _doc(PR(R("The fox jumps.")))
    b = _doc(PR(R("The ") + CRANGE("0", "fox") + R(" jumps.")),
             comments=[{"id": "0", "author": "Ada", "initials": "AL", "paras": [("p1", "Which fox?")]}])
    (cc,) = _cc(a, b)
    assert cc.state == "added" and cc.author == "Ada" and cc.cid == 1
    assert "".join(s.t for s in cc.segments) == "Which fox?"
    assert all(s.m == "ins" for s in cc.segments)


def test_removed_comment_only_in_the_original_document():
    a = _doc(PR(R("The ") + CRANGE("0", "fox") + R(" jumps.")),
             comments=[{"id": "0", "author": "Ada", "paras": [("p1", "Which fox?")]}])
    b = _doc(PR(R("The fox jumps.")))
    (cc,) = _cc(a, b)
    assert cc.state == "removed" and cc.cid == 1 and all(s.m == "del" for s in cc.segments)


def test_matched_comment_with_identical_text_is_unchanged_and_unnumbered():
    a = _doc(PR(R("The ") + CRANGE("0", "fox") + R(".")), comments=[{"id": "0", "author": "A", "paras": [("p1", "Note")]}])
    b = _doc(PR(R("The ") + CRANGE("0", "fox") + R(".")), comments=[{"id": "0", "author": "A", "paras": [("p1", "Note")]}])
    (cc,) = _cc(a, b)
    assert cc.state == "unchanged" and cc.cid is None


def test_edited_comment_text_is_diffed_inside_the_change():
    a = _doc(PR(R("The ") + CRANGE("0", "fox") + R(".")), comments=[{"id": "0", "author": "A", "paras": [("p1", "Please check this")]}])
    b = _doc(PR(R("The ") + CRANGE("0", "fox") + R(".")), comments=[{"id": "0", "author": "A", "paras": [("p1", "Please verify this")]}])
    (cc,) = _cc(a, b)
    assert cc.state == "edited" and cc.cid == 1
    assert "".join(s.t for s in cc.segments if s.m in ("eq", "ins")) == "Please verify this"
    assert any(s.m == "del" and s.t.strip() == "check" for s in cc.segments)


def test_matching_uses_the_anchor_when_ids_differ():
    # ids renumber between versions but the anchored text is the same common span
    a = _doc(PR(R("Alpha ") + CRANGE("3", "beta") + R(" gamma.")), comments=[{"id": "3", "author": "A", "paras": [("p1", "Keep")]}])
    b = _doc(PR(R("Alpha ") + CRANGE("9", "beta") + R(" gamma.")), comments=[{"id": "9", "author": "A", "paras": [("p2", "Keep")]}])
    (cc,) = _cc(a, b)
    assert cc.state == "unchanged"


def test_anchor_on_deleted_text_is_flagged_on_deleted():
    a = _doc(PR(R("Keep ") + CRANGE("0", "remove me") + R(" end.")), comments=[{"id": "0", "author": "A", "paras": [("p1", "n")]}])
    b = _doc(PR(R("Keep  end.")))
    (cc,) = _cc(a, b)
    assert cc.state == "removed" and cc.anchor.on_deleted is True


def test_reply_thread_nests_under_its_parent():
    body = PR(R("The ") + CRANGE("0", "fox") + R(" and ") + CRANGE("1", "hound") + R("."))
    b = _doc(body,
             comments=[{"id": "0", "author": "A", "paras": [("pa", "Parent")]},
                       {"id": "1", "author": "B", "paras": [("pb", "Reply")]}],
             comments_ex=[{"paraId": "pb", "parent": "pa"}])
    a = _doc(PR(R("The fox and hound.")))
    ccs = _cc(a, b)
    assert [(c.author, c.depth) for c in ccs] == [("A", 0), ("B", 1)]
    assert [c.cid for c in ccs] == [1, 2]


def test_reading_order_follows_the_body_anchor_position():
    a = _doc(P("First para.") + P("Second para."))
    b = _doc(PR(CRANGE("1", "First") + R(" para.")) + PR(CRANGE("0", "Second") + R(" para.")),
             comments=[{"id": "0", "author": "Zed", "paras": [("p0", "on second")]},
                       {"id": "1", "author": "Amy", "paras": [("p1", "on first")]}])
    ccs = _cc(a, b)
    assert [c.author for c in ccs] == ["Amy", "Zed"]     # id 1 anchors first in the body


def test_a_removed_comment_on_an_unchanged_paragraph_sorts_at_its_body_position():
    # P1 is unchanged (an "equal" row) and carries a removed comment (original side only); P2 is
    # edited (a "changed" row) and carries an added comment (revised side only). The removed
    # comment's anchor sits on P1, so it must sort BEFORE the added comment on P2 -- not fall
    # through to the end-of-body fallback just because its row type isn't "deleted".
    a = _doc(PR(CRANGE("0", "Alpha") + R(" text.")) + PR(R("Beta original.")),
             comments=[{"id": "0", "author": "Amy", "paras": [("p0", "on first")]}])
    b = _doc(PR(R("Alpha text.")) + PR(CRANGE("1", "Beta") + R(" revised.")),
             comments=[{"id": "1", "author": "Zed", "paras": [("p1", "on second")]}])
    ccs = _cc(a, b)
    assert [c.author for c in ccs] == ["Amy", "Zed"]
    assert [c.state for c in ccs] == ["removed", "added"]


def test_matching_uses_the_shared_anchor_row_to_disambiguate_near_tie_text():
    # Two original comments by the same author with near-identical text, anchored on two
    # different (unchanged) paragraphs. The revised counterparts are textually CLOSER to the
    # other original comment than to their true anchor-paragraph partner, so plain text
    # similarity alone pairs them backwards. The anchor signal (same comparison row) must win.
    a = _doc(PR(CRANGE("0", "Para") + R(" one text.")) + PR(CRANGE("1", "Para") + R(" two text.")),
             comments=[{"id": "0", "author": "A", "paras": [("c0", "alpha bravo charlie delta echo")]},
                       {"id": "1", "author": "A", "paras": [("c1", "alpha bravo charlie golf india")]}])
    b = _doc(PR(CRANGE("10", "Para") + R(" one text.")) + PR(CRANGE("11", "Para") + R(" two text.")),
             comments=[{"id": "10", "author": "A", "paras": [("c10", "alpha bravo charlie golf hotel")]},
                       {"id": "11", "author": "A", "paras": [("c11", "alpha bravo charlie delta foxtrot")]}])
    ccs = _cc(a, b)
    assert [c.old_id for c in ccs] == ["0", "1"]
    assert [c.new_id for c in ccs] == ["10", "11"]
