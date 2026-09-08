from lxml import etree
from calandria.docx.package import Package
from calandria.docx.ns import W, wq, wval, wbool, twips_to_pt, half_pt
from calandria.testing.makedocx import make_docx, DOC, P

RELS = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId3" Type="x/header" Target="header1.xml"/>'
        '<Relationship Id="rId9" Type="x/footer" Target="/word/footer2.xml"/>'
        '</Relationships>')


def test_part_and_xml():
    pkg = Package.open(make_docx({"word/document.xml": DOC(P("hi"))}))
    assert pkg.has("word/document.xml") and not pkg.has("word/styles.xml")
    assert pkg.part("word/styles.xml") is None and pkg.xml("word/styles.xml") is None
    root = pkg.xml("word/document.xml")
    assert root.tag == wq("document")
    assert root.find(f".//{wq('t')}").text == "hi"


def test_rels_targets_normalized():
    pkg = Package.open(make_docx({"word/document.xml": DOC(""), "word/_rels/document.xml.rels": RELS}))
    assert pkg.rels("word/document.xml") == {"rId3": "header1.xml", "rId9": "footer2.xml"}
    assert pkg.rels("word/header1.xml") == {}


def test_ns_helpers():
    el = etree.fromstring(f'<w:jc xmlns:w="{W}" w:val="center"/>')
    assert wval(el) == "center" and wval(None, "left") == "left"
    b = etree.fromstring(f'<w:b xmlns:w="{W}"/>')
    off = etree.fromstring(f'<w:b xmlns:w="{W}" w:val="0"/>')
    assert wbool(b) is True and wbool(off) is False and wbool(None) is False
    assert twips_to_pt("1440") == 72.0 and twips_to_pt(None) is None
    assert half_pt("22") == 11.0 and half_pt("x") is None
