import io

from calandria.diff.compare import compare
from calandria.docx.parser import parse_docx
from calandria.layout.comments import COLUMN_GAP, COLUMN_W, reserved_width
from calandria.layout.engine import layout
from calandria.layout.pieces import LayoutOptions
from calandria.testing.fakefonts import FakeResolver
from calandria.testing.makedocx import COMMENTS, COMMENTS_EX, CRANGE, CRELS, DOC, P, PR, R, make_docx

OPTS = lambda: LayoutOptions(fonts=FakeResolver())


def _doc(body, comments=None, comments_ex=None):
    files = {"word/document.xml": DOC(body),
             "word/_rels/document.xml.rels": CRELS(comments=comments is not None,
                                                   comments_ex=comments_ex is not None)}
    if comments is not None:
        files["word/comments.xml"] = COMMENTS(comments)
    if comments_ex is not None:
        files["word/commentsExtended.xml"] = COMMENTS_EX(comments_ex)
    return parse_docx(io.BytesIO(make_docx(files)))


def test_no_comments_reserves_no_column_and_keeps_content_width():
    a = b = _doc(P("Plain text here."))
    assert reserved_width(compare(a, b)) == 0.0
    lay = layout(compare(a, b), OPTS())
    plain = layout(compare(_doc(P("Plain text here.")), _doc(P("Plain text here."))), OPTS())
    # a comment-free document is byte-for-byte what it was (no page.comments key)
    assert all(not getattr(p, "comments", []) for p in lay.pages)


def test_a_commented_document_reserves_the_column_and_narrows_the_body():
    a = _doc(P("The fox jumps over the lazy dog again and again and again."))
    b = _doc(PR(R("The ") + CRANGE("0", "fox") + R(" jumps over the lazy dog again and again and again.")),
             comments=[{"id": "0", "author": "Ada", "initials": "AL", "paras": [("p1", "Which fox exactly?")]}])
    cmp = compare(a, b)
    assert reserved_width(cmp) == COLUMN_W + COLUMN_GAP
    lay = layout(cmp, OPTS())
    # the body content width is narrower than the un-commented same page
    body_runs_x = max(g.x + g.w for p in lay.pages for ln in p.lines for g in ln.runs)
    assert body_runs_x <= lay.pages[0].w - lay.pages[0].margin_right - COLUMN_W


def test_the_bubble_lands_on_the_page_of_its_anchor_with_a_connector():
    b = _doc(PR(R("The ") + CRANGE("0", "fox") + R(" jumps.")),
             comments=[{"id": "0", "author": "Ada", "initials": "AL", "date": "2026-09-16T00:00:00Z",
                        "paras": [("p1", "note")]}])
    a = _doc(PR(R("The fox jumps.")))
    lay = layout(compare(a, b), OPTS())
    placed = [pc for p in lay.pages for pc in p.comments]
    assert len(placed) == 1
    pc = placed[0]
    assert pc.bubble.state == "added" and pc.bubble.cid == 1
    assert pc.x >= lay.pages[0].w - lay.pages[0].margin_right - COLUMN_W - 1
    assert pc.anchor_y > 0 and pc.anchor_x > 0        # the connector has a real body endpoint


def test_two_bubbles_on_one_page_do_not_overlap():
    body = (PR(R("Line one ") + CRANGE("0", "here") + R("."))
            + PR(R("Line two ") + CRANGE("1", "there") + R(".")))
    b = _doc(body, comments=[{"id": "0", "author": "A", "initials": "A", "paras": [("p1", "first " * 20)]},
                             {"id": "1", "author": "B", "initials": "B", "paras": [("p2", "second")]}])
    a = _doc(P("Line one here.") + P("Line two there."))
    lay = layout(compare(a, b), OPTS())
    placed = sorted((pc for p in lay.pages for pc in p.comments), key=lambda p: p.y)
    assert len(placed) == 2
    assert placed[0].y + placed[0].bubble.height <= placed[1].y + 1e-6


def test_removed_comment_on_a_surviving_paragraph_resolves_to_its_real_anchor():
    # paragraph 1's text is unchanged across the two versions -- only its ORIGINAL-side comment
    # is dropped. The comment's anchor.para is the a-side Paragraph, so it must still resolve
    # through the row's a-side unit, not fall back to page 0 / margin_top / anchor_x=0.
    a = _doc(PR(R("First ") + CRANGE("0", "paragraph") + R(" text.")) + P("Second paragraph text."),
             comments=[{"id": "0", "author": "Ada", "initials": "AL", "paras": [("p1", "Why this word?")]}])
    b = _doc(P("First paragraph text.") + P("Second paragraph text."))
    cmp = compare(a, b)
    lay = layout(cmp, OPTS())
    placed = [pc for p in lay.pages for pc in p.comments]
    assert len(placed) == 1
    pc = placed[0]
    assert pc.bubble.state == "removed"
    body_line = next(ln for p in lay.pages for ln in p.lines if ln.stream == "body" and ln.row_index == 0)
    assert pc.anchor_y == body_line.baseline
    assert pc.anchor_x > 0


def test_reply_with_no_anchor_inherits_its_roots_page():
    # comment "1" is a reply threaded under root comment "0" but carries no commentRange/Reference
    # of its own (anchor.para is None) -- common for a Word reply. It must land on the root's
    # resolved page, not fall back to page 0.
    filler = "".join(P(f"p{i}") for i in range(54))       # exactly fills page 1 (54 x 12 = 648)
    b = _doc(filler + PR(R("p54 ") + CRANGE("0", "anchor") + R(" text.")),
             comments=[{"id": "0", "author": "A", "initials": "A", "paras": [("pa", "Root note")]},
                       {"id": "1", "author": "B", "initials": "B", "paras": [("pb", "Reply note")]}],
             comments_ex=[{"paraId": "pb", "parent": "pa"}])
    a = _doc(filler + P("p54 anchor text."))
    lay = layout(compare(a, b), OPTS())
    assert len(lay.pages) >= 2
    placed = {pc.bubble.cid: (pg.number, pc) for pg in lay.pages for pc in pg.comments}
    root_page, root = placed[1]
    reply_page, reply = placed[2]
    assert root.bubble.depth == 0 and reply.bubble.depth == 1
    assert root_page > 1                     # the anchored paragraph starts page 2
    assert reply_page == root_page
    assert reply.anchor_x == root.anchor_x and reply.anchor_y == root.anchor_y


def test_done_comment_bubble_header_starts_with_the_check_mark():
    b = _doc(PR(R("The ") + CRANGE("0", "fox") + R(" jumps.")),
             comments=[{"id": "0", "author": "Ada", "initials": "AL", "paras": [("p1", "note")]}],
             comments_ex=[{"paraId": "p1", "done": True}])
    a = _doc(PR(R("The fox jumps.")))
    lay = layout(compare(a, b), OPTS())
    placed = [pc for p in lay.pages for pc in p.comments]
    assert len(placed) == 1
    assert placed[0].bubble.header.startswith("✓")
