import io

from calandria.diff.compare import compare
from calandria.docx.parser import parse_docx
from calandria.layout.engine import layout, layout_document
from calandria.layout.pieces import LayoutOptions
from calandria.pdf.draw import bar_intervals, changed_pages
from calandria.server.session import change_marks
from calandria.testing.fakefonts import FakeResolver
from calandria.testing.makedocx import (DOC, FLD, FTR, HDR, IMG, P, PR, R, RELS, SECT, SETTINGS, STYLES,
                                        make_docx)

FR = FakeResolver()                       # 5 pt per character at size 10, line height 12, ascent 8
STY = STYLES('<w:rFonts w:ascii="Fake"/><w:sz w:val="20"/>')
RELS_ = RELS({"rId1": "header1.xml", "rId2": "header2.xml", "rId3": "footer1.xml", "rId4": "header3.xml"})


def _doc(body, header1=None, header2=None, footer1=None, header3=None, even_and_odd=False):
    files = {"word/document.xml": DOC(body), "word/styles.xml": STY, "word/_rels/document.xml.rels": RELS_,
             "word/settings.xml": SETTINGS(even_and_odd)}
    for name, xml in (("header1.xml", header1), ("header2.xml", header2), ("header3.xml", header3)):
        if xml is not None:
            files["word/" + name] = HDR(xml)
    if footer1 is not None:
        files["word/footer1.xml"] = FTR(footer1)
    return parse_docx(io.BytesIO(make_docx(files)))


def _lay(a, b, **opts):
    return layout(compare(a, b), LayoutOptions(fonts=FR, **opts))


def _texts(page, stream):
    return ["".join(g.text for g in ln.runs) for ln in page.lines if ln.stream == stream]


BODY = "".join(P(f"p{i}") for i in range(100))          # 54 body lines per page at 12 pt


def test_header_and_footer_drawn_at_word_positions_on_every_page():
    d = _doc(BODY + SECT(hdr={"default": "rId1"}, ftr={"default": "rId3"}), header1=P("Head"), footer1=P("Foot"))
    L = layout_document(d, LayoutOptions(fonts=FR))
    assert L.page_count == 2
    for pg in L.pages:
        (h,) = [ln for ln in pg.lines if ln.stream == "header"]
        (f,) = [ln for ln in pg.lines if ln.stream == "footer"]
        assert (h.top, h.x, "".join(g.text for g in h.runs)) == (36, 72, "Head")
        assert (f.top + f.height, "".join(g.text for g in f.runs)) == (792 - 36, "Foot")
    body = [ln for ln in L.pages[0].lines if ln.stream == "body"]
    assert body[0].top == 72 and len(body) == 54          # a 12 pt header fits the 36 pt above the margin


def test_tall_header_pushes_the_body_down_and_the_planner_knows():
    head = "".join(P(f"h{i}") for i in range(5))         # 60 pt: header top 36 + 60 = 96 > margin 72
    d = _doc(BODY + SECT(hdr={"default": "rId1"}), header1=head)
    L = layout_document(d, LayoutOptions(fonts=FR))
    body0 = [ln for ln in L.pages[0].lines if ln.stream == "body"]
    assert body0[0].top == 96 and len(body0) == 52       # (720 - 96) / 12
    assert L.page_count == 2 and len([ln for ln in L.pages[1].lines if ln.stream == "body"]) == 48


def test_tall_footer_lifts_the_body_bottom():
    foot = "".join(P(f"f{i}") for i in range(5))         # 60 pt: footer top 756 - 60 = 696 < 720
    d = _doc(BODY + SECT(ftr={"default": "rId3"}), footer1=foot)
    L = layout_document(d, LayoutOptions(fonts=FR))
    body0 = [ln for ln in L.pages[0].lines if ln.stream == "body"]
    assert len(body0) == 52 and body0[-1].top + body0[-1].height <= 696
    foots = [ln for ln in L.pages[0].lines if ln.stream == "footer"]
    assert foots[0].top == 696 and foots[-1].top + foots[-1].height == 756


def test_title_page_and_even_odd_pick_the_variant_per_page():
    d = _doc(BODY + BODY + SECT(hdr={"default": "rId1", "first": "rId2", "even": "rId4"}, title_pg=True),
             header1=P("Odd"), header2=P("Cover"), header3=P("Even"), even_and_odd=True)
    L = layout_document(d, LayoutOptions(fonts=FR))
    assert [_texts(pg, "header") for pg in L.pages] == [["Cover"], ["Even"], ["Odd"], ["Even"]]


def test_page_field_fills_per_page_with_restart_and_format_and_numpages_with_the_total():
    body = BODY + PR(R("s2"), ppr=SECT(ftr={"default": "rId3"}, page_start=1, page_fmt="lowerRoman")) \
        + BODY + SECT(ftr={"default": "rId3"}, page_start=3)
    d = _doc(body, footer1=PR(R("Page ") + FLD("PAGE") + R(" of ") + FLD("NUMPAGES")))
    L = layout_document(d, LayoutOptions(fonts=FR))
    assert L.page_count == 4
    assert [_texts(pg, "footer") for pg in L.pages] == [["Page i of 4"], ["Page ii of 4"], ["Page 3 of 4"],
                                                        ["Page 4 of 4"]]
    assert [pg.label for pg in L.pages] == ["i", "ii", "3", "4"]


def test_second_section_inherits_the_header_and_a_blank_part_shows_nothing():
    body = (PR(R("one"), ppr=SECT(hdr={"default": "rId1"})) + PR(R("two"), ppr=SECT()) + P("three")
            + SECT(hdr={"default": "rId2"}))
    d = _doc(body, header1=P("Inherited"), header2=P(""))
    L = layout_document(d, LayoutOptions(fonts=FR))
    assert [_texts(pg, "header") for pg in L.pages] == [["Inherited"], ["Inherited"], []]


def test_changed_header_is_red_everywhere_but_marked_on_its_first_page_only():
    a = _doc(BODY + SECT(hdr={"default": "rId1"}), header1=P("Version A"))
    b = _doc(BODY + SECT(hdr={"default": "rId1"}), header1=P("Version B"))
    L = _lay(a, b)
    assert L.page_count == 2
    h0 = [ln for ln in L.pages[0].lines if ln.stream == "header"]
    h1 = [ln for ln in L.pages[1].lines if ln.stream == "header"]
    assert [g.mode for g in h0[0].runs] == [g.mode for g in h1[0].runs]      # the redline on both pages
    assert "del" in {g.mode for g in h1[0].runs} and "ins" in {g.mode for g in h1[0].runs}
    assert h0[0].changed and h0[0].cid_starts == [1, 2]        # the replacement: deletion 1, insertion 2
    assert not h1[0].changed and h1[0].cid_starts == [] and all(g.cid is None for g in h1[0].runs)
    assert changed_pages(L) == [1]
    assert bar_intervals(L.pages[0]) and not bar_intervals(L.pages[1])
    anchors, _marks = change_marks(L)
    assert anchors[1] == {"page": 1, "top": 36.0} and anchors[2] == {"page": 1, "top": 36.0}


def test_original_side_shows_the_original_header_text():
    a = _doc(P("body") + SECT(hdr={"default": "rId1"}), header1=P("Version A"))
    b = _doc(P("body") + SECT(hdr={"default": "rId1"}), header1=P("Version B"))
    orig = _lay(a, b, side="original")
    mod = _lay(a, b, side="modified")
    assert _texts(orig.pages[0], "header") == ["Version A"] and _texts(mod.pages[0], "header") == ["Version B"]


def test_deleted_header_with_no_revised_part_still_shows_struck_on_the_pages():
    a = _doc(P("body") + SECT(hdr={"default": "rId1"}), header1=P("Gone"))
    b = _doc(P("body") + SECT(hdr={"default": "rId1"}), header1=P(""))
    L = _lay(a, b)
    (h,) = [ln for ln in L.pages[0].lines if ln.stream == "header"]
    assert "".join(g.text for g in h.runs) == "Gone" and {g.mode for g in h.runs} == {"del"}


def test_image_only_header_paragraph_holds_its_box():
    d = _doc(BODY + SECT(hdr={"default": "rId1"}), header1=PR(IMG(914400, 914400)))   # 72 x 72 pt
    L = layout_document(d, LayoutOptions(fonts=FR))
    (h,) = [ln for ln in L.pages[0].lines if ln.stream == "header"]
    assert h.height == 72 and h.runs[0].text == "" and h.runs[0].w == 72
    body0 = [ln for ln in L.pages[0].lines if ln.stream == "body"]
    assert body0[0].top == 36 + 72


def test_footnote_reserve_comes_off_the_footer_lifted_bottom():
    from calandria.testing.makedocx import FNREF, FOOTNOTES
    foot = "".join(P(f"f{i}") for i in range(5))                 # bottom 696
    body = "".join(P(f"p{i}") for i in range(45)) + PR(R("ref") + FNREF(1)) + "".join(P(f"q{i}") for i in range(10))
    files = {"word/document.xml": DOC(body + SECT(ftr={"default": "rId3"})), "word/styles.xml": STY,
             "word/_rels/document.xml.rels": RELS_, "word/footer1.xml": FTR(foot),
             "word/footnotes.xml": FOOTNOTES({1: "note"})}
    d = parse_docx(io.BytesIO(make_docx(files)))
    L = layout_document(d, LayoutOptions(fonts=FR))
    notes = [ln for ln in L.pages[0].lines if ln.stream == "footnote"]
    assert notes and max(ln.top + ln.height for ln in notes) <= 696 + 1e-6


def _field_run(page, stream, name="PAGE"):
    return [g for ln in page.lines if ln.stream == stream for g in ln.runs if g.field == name]


def test_a_page_number_at_a_right_tab_stop_ends_at_the_stop():
    footer = PR(R("Confidential") + "<w:r><w:tab/></w:r>" + FLD("PAGE"),
                ppr='<w:tabs><w:tab w:val="right" w:pos="9360"/></w:tabs>')   # 9360 twips = 468 pt
    d = _doc(BODY + SECT(ftr={"default": "rId3"}), footer1=footer)
    L = layout_document(d, LayoutOptions(fonts=FR))
    assert L.page_count == 2
    for pg, text in zip(L.pages, ("1", "2")):
        (g,) = _field_run(pg, "footer")
        assert g.text == text and g.x + g.w == 540         # the right margin, 72 + 468


def test_a_centred_page_number_is_centred_on_its_own_width():
    d = _doc(BODY + SECT(ftr={"default": "rId3"}), footer1=PR(FLD("PAGE"), ppr='<w:jc w:val="center"/>'))
    L = layout_document(d, LayoutOptions(fonts=FR))
    (g,) = _field_run(L.pages[0], "footer")
    assert (g.text, g.x) == ("1", 72 + (468 - 5) / 2)
    d12 = _doc(BODY * 6 + SECT(ftr={"default": "rId3"}), footer1=PR(FLD("PAGE"), ppr='<w:jc w:val="center"/>'))
    L12 = layout_document(d12, LayoutOptions(fonts=FR))
    assert L12.page_count == 12
    (g12,) = _field_run(L12.pages[11], "footer")
    assert (g12.text, g12.x) == ("12", 72 + (468 - 10) / 2)


def test_only_a_numpages_document_is_laid_out_twice(monkeypatch):
    from calandria.layout import engine
    calls: list = []
    real = engine._layout

    def counted(cmp, opts, total):
        calls.append(total)
        return real(cmp, opts, total)

    monkeypatch.setattr(engine, "_layout", counted)
    d = _doc(BODY + SECT(ftr={"default": "rId3"}), footer1=PR(R("Page ") + FLD("PAGE")))
    engine.layout_document(d, LayoutOptions(fonts=FR))
    assert calls == [None]                               # no NUMPAGES: one pass, as before
    calls.clear()
    d2 = _doc(BODY + SECT(ftr={"default": "rId3"}), footer1=PR(R("of ") + FLD("NUMPAGES")))
    L = engine.layout_document(d2, LayoutOptions(fonts=FR))
    assert calls == [None, L.page_count]
    assert _texts(L.pages[0], "footer") == ["of 2"]


def test_an_empty_document_still_shows_its_header():
    # Nothing to place at all: the fallback page is the one a reader sees in Word, chrome included.
    d = _doc(SECT(hdr={"default": "rId1"}), header1=P("Head"))
    L = layout_document(d, LayoutOptions(fonts=FR))
    assert L.page_count == 1 and not [ln for ln in L.pages[0].lines if ln.stream == "body"]
    assert _texts(L.pages[0], "header") == ["Head"] and L.pages[0].label == "1"
    d1 = _doc(P("") + SECT(hdr={"default": "rId1"}), header1=P("Head"))     # one empty paragraph
    L1 = layout_document(d1, LayoutOptions(fonts=FR))
    assert L1.page_count == 1 and _texts(L1.pages[0], "header") == ["Head"]
