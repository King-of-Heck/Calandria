import io

import pytest

from calandria.docx.hf import (SectionHf, displayed, format_number, is_blank, page_number, resolve,
                               variant_for)
from calandria.docx.parser import parse_docx
from calandria.model import Section
from calandria.testing.makedocx import DOC, FLD, HDR, FTR, IMG, P, PR, R, RELS, SECT, SETTINGS, make_docx


def _doc(body, parts=None, even_and_odd=False):
    files = {"word/document.xml": DOC(body), "word/settings.xml": SETTINGS(even_and_odd)}
    parts = parts or {}
    files["word/_rels/document.xml.rels"] = RELS({f"rId{i}": name for i, name in enumerate(parts, 1)})
    for name, xml in parts.items():
        files["word/" + name] = xml
    return parse_docx(io.BytesIO(make_docx(files)))


def _rid(parts, name):
    return f"rId{list(parts).index(name) + 1}"


PARTS = {"header1.xml": HDR(P("Running")), "header2.xml": HDR(P("Cover")), "header3.xml": HDR(P("Even")),
         "footer1.xml": FTR(PR(R("Page ") + FLD("PAGE"))), "header4.xml": HDR(P("")),
         "header5.xml": HDR(P("Running")), "header6.xml": HDR(PR(IMG(914400, 914400)))}


def test_resolve_inherits_each_variant_from_the_previous_section():
    body = (PR(R("s1"), ppr=SECT(hdr={"default": _rid(PARTS, "header1.xml"), "first": _rid(PARTS, "header2.xml")},
                                 ftr={"default": _rid(PARTS, "footer1.xml")}, title_pg=True))
            + PR(R("s2"), ppr=SECT(hdr={"even": _rid(PARTS, "header3.xml")}))
            + P("s3") + SECT(hdr={"default": _rid(PARTS, "header5.xml")}))
    d = _doc(body, PARTS)
    r = resolve(d)
    assert r[0] == SectionHf({"default": "header1.xml", "first": "header2.xml", "even": None},
                             {"default": "footer1.xml", "first": None, "even": None})
    assert r[1].header == {"default": "header1.xml", "first": "header2.xml", "even": "header3.xml"}
    assert r[1].footer["default"] == "footer1.xml"
    assert r[2].header == {"default": "header5.xml", "first": "header2.xml", "even": "header3.xml"}


def test_first_section_without_references_is_blank():
    d = _doc(P("x") + SECT())
    assert resolve(d) == [SectionHf({"default": None, "first": None, "even": None},
                                    {"default": None, "first": None, "even": None})]


def test_variant_for_follows_title_page_and_even_odd():
    sec = Section(title_pg=True)
    d = _doc(P("x") + SECT(), even_and_odd=True)
    assert variant_for(sec, d, True, 1) == "first"
    assert variant_for(sec, d, False, 2) == "even"
    assert variant_for(sec, d, False, 3) == "default"
    assert variant_for(Section(), d, True, 1) == "default"        # no titlePg: the first page is an odd page
    assert variant_for(Section(), d, True, 2) == "even"
    d2 = _doc(P("x") + SECT(), even_and_odd=False)
    assert variant_for(Section(), d2, False, 2) == "default"


def test_is_blank_sees_text_fields_and_images():
    d = _doc(P("x") + SECT(hdr={"default": _rid(PARTS, "header4.xml"), "first": _rid(PARTS, "header6.xml"),
                                "even": _rid(PARTS, "header1.xml")},
                           ftr={"default": _rid(PARTS, "footer1.xml")}), PARTS)
    assert is_blank(d.parts["header4.xml"]) is True
    assert is_blank(d.parts["header6.xml"]) is False        # an image
    assert is_blank(d.parts["footer1.xml"]) is False        # a field
    assert is_blank(d.parts["header1.xml"]) is False
    assert is_blank([]) is True


def test_displayed_drops_blank_parts_and_repeated_content_and_keeps_document_order():
    body = (PR(R("s1"), ppr=SECT(hdr={"default": _rid(PARTS, "header1.xml"), "first": _rid(PARTS, "header2.xml")},
                                 title_pg=True))
            + PR(R("s2"), ppr=SECT(hdr={"default": _rid(PARTS, "header4.xml"), "even": _rid(PARTS, "header3.xml")}))
            + P("s3") + SECT(hdr={"default": _rid(PARTS, "header5.xml")}))
    d = _doc(body, PARTS, even_and_odd=True)
    entries, alias = displayed(d, "header")
    assert [name for name, _ in entries] == ["header2.xml", "header1.xml", "header3.xml"]
    assert entries[1][1][0].text == "Running"
    assert alias == {"header1.xml": "header1.xml", "header2.xml": "header2.xml", "header3.xml": "header3.xml",
                     "header4.xml": None, "header5.xml": "header1.xml"}
    assert displayed(d, "footer") == ([], {})


def test_displayed_omits_first_and_even_when_word_would_not_show_them():
    body = P("s1") + SECT(hdr={"default": _rid(PARTS, "header1.xml"), "first": _rid(PARTS, "header2.xml"),
                               "even": _rid(PARTS, "header3.xml")})
    entries, alias = displayed(_doc(body, PARTS), "header")
    assert [name for name, _ in entries] == ["header1.xml"]
    assert alias == {"header1.xml": "header1.xml", "header2.xml": None, "header3.xml": None}


def test_page_number_restarts_and_continues():
    assert page_number(Section(page_start=1), 0, 12) == 1
    assert page_number(Section(page_start=1), 3, 12) == 13
    assert page_number(Section(), 0, 12) == 13
    assert page_number(Section(page_start=7), 0, 0) == 7


@pytest.mark.parametrize("n, fmt, out", [(4, "decimal", "4"), (4, "lowerRoman", "iv"), (14, "upperRoman", "XIV"),
                                         (1, "lowerLetter", "a"), (27, "upperLetter", "AA"), (3, "weird", "3"),
                                         (0, "lowerRoman", "0")])
def test_format_number(n, fmt, out):
    assert format_number(n, fmt) == out


def test_displayed_keys_an_image_only_part_by_its_image_boxes():
    parts = {"header1.xml": HDR(PR(IMG(914400, 914400))),      # a logo
             "header2.xml": HDR(PR(IMG(914400, 914400))),      # the same logo again: one entry
             "header3.xml": HDR(PR(IMG(457200, 914400)))}      # a narrower logo: its own entry
    body = (PR(R("s1"), ppr=SECT(hdr={"default": _rid(parts, "header1.xml")}))
            + PR(R("s2"), ppr=SECT(hdr={"default": _rid(parts, "header2.xml")}))
            + P("s3") + SECT(hdr={"default": _rid(parts, "header3.xml")}))
    entries, alias = displayed(_doc(body, parts), "header")
    assert [name for name, _ in entries] == ["header1.xml", "header3.xml"]
    assert alias == {"header1.xml": "header1.xml", "header2.xml": "header1.xml",
                     "header3.xml": "header3.xml"}
