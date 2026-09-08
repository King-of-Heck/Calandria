from lxml import etree
from calandria.docx.styles import Styles
from calandria.docx.ns import W

STYLES = f'''<w:styles xmlns:w="{W}">
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri"/><w:sz w:val="22"/></w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:after="160" w:line="259" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:styleId="Normal"><w:name w:val="Normal"/><w:rPr><w:i/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/>
  <w:pPr><w:keepNext/><w:jc w:val="center"/><w:outlineLvl w:val="0"/><w:numPr><w:numId w:val="3"/><w:ilvl w:val="1"/></w:numPr></w:pPr>
  <w:rPr><w:b/><w:sz w:val="32"/><w:color w:val="1F3864"/><w:i w:val="0"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="DocID"><w:name w:val="DocID"/><w:basedOn w:val="Normal"/>
  <w:pPr><w:rPr><w:sz w:val="99"/></w:rPr></w:pPr><w:rPr><w:sz w:val="16"/><w:u w:val="none"/></w:rPr></w:style>
</w:styles>'''


def test_defaults():
    s = Styles.parse(etree.fromstring(STYLES))
    assert s.defaults == {"font": "Calibri", "size_pt": 11.0, "space_after_pt": 8.0, "line_spacing": 259 / 240}


def test_absent_styles_part():
    s = Styles.parse(None)
    assert s.get("Normal") is None
    assert s.defaults == {"font": None, "size_pt": 11.0, "space_after_pt": None, "line_spacing": None}
    assert s.resolved_rpr("Nope") == {} and s.resolved_ppr("Nope") == {}


def test_chain_resolution_child_wins():
    s = Styles.parse(etree.fromstring(STYLES))
    h = s.resolved_rpr("Heading1")
    assert h == {"italic": False, "bold": True, "size_pt": 16.0, "color": "1f3864"}
    p = s.resolved_ppr("Heading1")
    assert p["keep_next"] is True and p["align"] == "center" and p["outline_level"] == 0
    assert p["num_id"] == 3 and p["ilvl"] == 1


def test_paragraph_mark_rpr_inside_ppr_is_ignored():
    s = Styles.parse(etree.fromstring(STYLES))
    d = s.resolved_rpr("DocID")
    assert d["size_pt"] == 8.0 and d["underline"] is False and d["italic"] is True
