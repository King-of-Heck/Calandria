import io

from calandria.diff.compare import compare
from calandria.docx.parser import parse_docx
from calandria.layout.comments import COLUMN_GAP, COLUMN_W, reserved_width
from calandria.layout.engine import layout
from calandria.layout.pieces import LayoutOptions
from calandria.testing.fakefonts import FakeResolver
from calandria.testing.makedocx import (COMMENTS, CRANGE, DOC, HDR, P, PKG_RELS, PR, R, REL_COMMENTS, REL_HDR,
                                        SECT, STYLES, make_docx)

# FakeResolver: 5 pt per character at size 10, line height 12 (see tests/test_engine_hf.py).
STY = STYLES('<w:rFonts w:ascii="Fake"/><w:sz w:val="20"/>')
OPTS = lambda: LayoutOptions(fonts=FakeResolver())

# Page content width is 468 pt (Letter, 1 in margins). The comment column + gap reserve 162 pt,
# but they are added to the sheet (which widens to 774 pt), NOT carved out of the body: the body and
# the header both keep the full 468 pt, so a document paginates the same with or without comments.
HEADER_TEXT = "This header line is long enough to wrap only when the column narrows the body width"
BODY_TEXT = "Body content wraps only when the comment column narrows the page width here"


def _doc(commented: bool):
    body = (PR(R("Body content wraps only when the comment ") + CRANGE("0", "column")
               + R(" narrows the page width here"))
            if commented else P(BODY_TEXT))
    rels_body = f'<Relationship Id="rId1" Type="{REL_HDR}" Target="header1.xml"/>'
    if commented:
        rels_body += f'<Relationship Id="rId2" Type="{REL_COMMENTS}" Target="comments.xml"/>'
    files = {
        "word/document.xml": DOC(body + SECT(hdr={"default": "rId1"})),
        "word/styles.xml": STY,
        "word/_rels/document.xml.rels": f'<Relationships xmlns="{PKG_RELS}">{rels_body}</Relationships>',
        "word/header1.xml": HDR(P(HEADER_TEXT)),
    }
    if commented:
        files["word/comments.xml"] = COMMENTS(
            [{"id": "0", "author": "Ada", "initials": "AL", "paras": [("p1", "Which column?")]}])
    return parse_docx(io.BytesIO(make_docx(files)))


def _lines(lay, stream):
    return [ln for pg in lay.pages for ln in pg.lines if ln.stream == stream]


def _signature(ln):
    return (ln.x, ln.top, [(g.text, g.x, g.w) for g in ln.runs])


def test_body_and_header_stay_full_width_and_the_sheet_widens_for_comments():
    baseline = _doc(False)
    commented = _doc(True)

    cmp_without = compare(baseline, baseline)
    cmp_with = compare(baseline, commented)
    assert reserved_width(cmp_without) == 0.0
    assert reserved_width(cmp_with) == COLUMN_W + COLUMN_GAP

    lay_without = layout(cmp_without, OPTS())
    lay_with = layout(cmp_with, OPTS())

    h_without = _lines(lay_without, "header")
    h_with = _lines(lay_with, "header")
    # the header wraps the same way (same x, same line widths) whether or not the document has
    # comments -- the header is never narrowed by the comment column
    assert len(h_without) == len(h_with) == 1
    assert _signature(h_without[0]) == _signature(h_with[0])
    assert "".join(g.text for g in h_with[0].runs) == HEADER_TEXT

    b_without = _lines(lay_without, "body")
    b_with = _lines(lay_with, "body")
    # the body is NOT narrowed either: same wrap, same right edge, with or without comments
    assert len(b_without) == len(b_with) == 1
    body_right_without = max(g.x + g.w for ln in b_without for g in ln.runs)
    body_right_with = max(g.x + g.w for ln in b_with for g in ln.runs)
    assert body_right_with == body_right_without

    # the comment column is added to the sheet instead: the commented page is wider by exactly the
    # reserved width, and the extra space is all to the right of the (unchanged) right margin
    assert lay_with.pages[0].w == lay_without.pages[0].w + reserved_width(cmp_with)
    assert lay_with.pages[0].margin_right == lay_without.pages[0].margin_right
