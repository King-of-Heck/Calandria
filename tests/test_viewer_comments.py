import io

from calandria.diff.compare import compare
from calandria.docx.parser import parse_docx
from calandria.testing.makedocx import COMMENTS, COMMENTS_EX, CRANGE, CRELS, DOC, PR, R, make_docx


def test_comment_dict_carries_everything_the_viewer_needs():
    b = parse_docx(io.BytesIO(make_docx({
        "word/document.xml": DOC(PR(R("The ") + CRANGE("0", "fox") + R(" and ") + CRANGE("1", "hound") + R("."))),
        "word/_rels/document.xml.rels": CRELS(comments=True, comments_ex=True),
        "word/comments.xml": COMMENTS([{"id": "0", "author": "Ada", "initials": "AL",
                                        "date": "2026-09-16T09:00:00Z", "paras": [("pa", "Parent note")]},
                                       {"id": "1", "author": "Bo", "initials": "BO",
                                        "date": "2026-09-16T10:00:00Z", "paras": [("pb", "A reply")]}]),
        "word/commentsExtended.xml": COMMENTS_EX([{"paraId": "pb", "parent": "pa"}])})))
    a = parse_docx(io.BytesIO(make_docx({"word/document.xml": DOC(PR(R("The fox and hound.")))})))
    cs = compare(a, b).to_dict()["comments"]
    assert [c["cid"] for c in cs] == [1, 2]
    assert [c["depth"] for c in cs] == [0, 1]
    assert [c["author"] for c in cs] == ["Ada", "Bo"]
    assert all(c["state"] == "added" for c in cs)
