import io

from calandria.docx.parser import parse_docx
from calandria.testing.makedocx import (DOC, FLD, FLDC, FTR, HDR, IMG, P, PR, R, RELS, SECT, SETTINGS,
                                        make_docx)


def _doc(body, **parts):
    return parse_docx(io.BytesIO(make_docx({"word/document.xml": DOC(body), **parts})))


def test_section_references_resolve_through_rels_and_parts_are_parsed():
    body = P("one") + SECT(hdr={"default": "rId1", "first": "rId2"}, ftr={"default": "rId3"}, title_pg=True,
                           page_start=5, page_fmt="lowerRoman")
    d = _doc(body, **{"word/_rels/document.xml.rels": RELS({"rId1": "header1.xml", "rId2": "header2.xml",
                                                              "rId3": "footer1.xml"}),
                      "word/header1.xml": HDR(P("Running head")),
                      "word/header2.xml": HDR(P("Cover head")),
                      "word/footer1.xml": FTR(P("Foot"))})
    s = d.sections[0]
    assert (s.header_default, s.header_first, s.header_even) == ("header1.xml", "header2.xml", None)
    assert (s.footer_default, s.footer_first, s.footer_even) == ("footer1.xml", None, None)
    assert (s.title_pg, s.page_start, s.page_fmt) == (True, 5, "lowerRoman")
    assert sorted(d.parts) == ["footer1.xml", "header1.xml", "header2.xml"]
    assert d.parts["header1.xml"][0].text == "Running head"
    assert d.parts["footer1.xml"][0].text == "Foot"


def test_section_without_references_has_none_and_default_numbering():
    d = _doc(P("x") + SECT())
    s = d.sections[0]
    assert s.header_default is None and s.footer_default is None
    assert s.page_start is None and s.page_fmt == "decimal"
    assert d.parts == {}


def test_missing_part_is_not_in_parts_but_the_reference_stays():
    d = _doc(P("x") + SECT(hdr={"default": "rId1"}),
             **{"word/_rels/document.xml.rels": RELS({"rId1": "header9.xml"})})
    assert d.sections[0].header_default == "header9.xml" and d.parts == {}


def test_unresolvable_rid_is_none():
    d = _doc(P("x") + SECT(hdr={"default": "rId7"}))
    assert d.sections[0].header_default is None


def test_paragraph_level_sectpr_also_carries_references():
    body = PR(R("cover"), ppr=SECT(hdr={"first": "rId1"}, title_pg=True)) + P("body") + SECT()
    d = _doc(body, **{"word/_rels/document.xml.rels": RELS({"rId1": "header1.xml"}),
                      "word/header1.xml": HDR(P("Cover"))})
    assert d.sections[0].header_first == "header1.xml" and d.sections[1].header_first is None


def test_simple_page_field_is_a_tagged_token_run():
    d = _doc(PR(R("Page ") + FLD("PAGE", "7") + R(" of ") + FLD("NUMPAGES", "9")))
    runs = d.blocks[0].runs
    assert [(r.text, r.props.field) for r in runs] == [("Page ", None), ("{PAGE}", "PAGE"), (" of ", None),
                                                       ("{NUMPAGES}", "NUMPAGES")]
    assert d.blocks[0].text == "Page {PAGE} of {NUMPAGES}"


def test_complex_page_field_is_one_token_run_in_the_result_formatting():
    d = _doc(PR(R("- ") + FLDC("PAGE", "6", rpr="<w:b/>") + R(" -")))
    runs = d.blocks[0].runs
    assert [(r.text, r.props.field, r.props.bold) for r in runs] == [("- ", None, False), ("{PAGE}", "PAGE", True),
                                                                     (" -", None, False)]


def test_page_field_without_cached_result_still_yields_the_token():
    d = _doc(PR('<w:fldSimple w:instr=" PAGE "/>'))
    assert [(r.text, r.props.field) for r in d.blocks[0].runs] == [("{PAGE}", "PAGE")]


def test_other_fields_keep_their_cached_text():
    d = _doc(PR(FLD("DATE", "2026-09-15") + FLDC("REF x", " see 1.2")))
    assert d.blocks[0].text == "2026-09-15 see 1.2"
    assert all(r.props.field is None for r in d.blocks[0].runs)


def test_inline_image_is_an_empty_run_with_its_box():
    d = _doc(PR(IMG(2254250, 730250)))
    (r,) = d.blocks[0].runs
    assert r.text == "" and (round(r.props.image_w_pt, 2), round(r.props.image_h_pt, 2)) == (177.5, 57.5)
    assert d.blocks[0].is_empty


def test_even_and_odd_setting_helper():
    assert _doc(P("x"), **{"word/settings.xml": SETTINGS(even_and_odd=True)}).even_and_odd is True


def test_a_page_field_keeps_its_cached_result_as_field_text():
    d = _doc(PR(R("Page ") + FLD("PAGE", "7")) + PR(FLDC("NUMPAGES", "9")) + PR('<w:fldSimple w:instr=" PAGE "/>'))
    simple, complex_, empty = (b.runs[-1] for b in d.blocks[:3])
    assert (simple.text, simple.props.field, simple.props.field_text) == ("{PAGE}", "PAGE", "7")
    assert (complex_.text, complex_.props.field, complex_.props.field_text) == ("{NUMPAGES}", "NUMPAGES", "9")
    assert (empty.text, empty.props.field, empty.props.field_text) == ("{PAGE}", "PAGE", "")
    assert d.blocks[0].text == "Page {PAGE}"          # the compared text keeps the token


def test_a_section_break_inside_a_header_part_is_not_a_section():
    body = P("one") + P("two") + SECT(hdr={"default": "rId1"})
    d = _doc(body, **{"word/_rels/document.xml.rels": RELS({"rId1": "header1.xml"}),
                      "word/header1.xml": HDR(PR(R("Head"), ppr=SECT()) + P("more"))})
    assert len(d.sections) == 1                        # the body's own section, and no phantom
    assert d.parts["header1.xml"][0].text == "Head"
    assert d.parts["header1.xml"][0].props.section_break is False
