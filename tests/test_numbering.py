from lxml import etree
from calandria.docx.numbering import Numbering, NumberingCounter, fmt_num, BULLETS
from calandria.docx.ns import W

NUM = f'''<w:numbering xmlns:w="{W}">
<w:abstractNum w:abstractNumId="0">
 <w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl>
 <w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="lowerLetter"/><w:lvlText w:val="(%2)"/><w:pStyle w:val="ListSub"/></w:lvl>
 <w:lvl w:ilvl="2"><w:start w:val="1"/><w:numFmt w:val="lowerRoman"/><w:lvlText w:val="%1.%2.%3"/></w:lvl>
</w:abstractNum>
<w:abstractNum w:abstractNumId="1">
 <w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="&#xF0B7;"/></w:lvl>
</w:abstractNum>
<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>
<w:num w:numId="2"><w:abstractNumId w:val="0"/><w:lvlOverride w:ilvl="0"><w:startOverride w:val="1"/></w:lvlOverride></w:num>
<w:num w:numId="3"><w:abstractNumId w:val="1"/></w:num>
</w:numbering>'''


def test_fmt_num():
    assert [fmt_num(n, "lowerLetter") for n in (1, 26, 27)] == ["a", "z", "aa"]
    assert fmt_num(4, "upperRoman") == "IV" and fmt_num(1999, "lowerRoman") == "mcmxcix"
    assert fmt_num(7, "decimalZero") == "07" and fmt_num(12, "decimal") == "12"
    assert fmt_num(3, "weird") == "3"


def test_parse():
    n = Numbering.parse(etree.fromstring(NUM))
    assert n.num_to_abs == {1: 0, 2: 0, 3: 1}
    lv = n.level(1, 0)
    assert lv.fmt == "decimal" and lv.text == "%1." and lv.ind_left_pt == 36.0 and lv.ind_hanging_pt == 18.0
    assert n.style_to_num == {"ListSub": (1, 1)}
    assert n.overrides == {2: {0: 1}}
    assert n.level(9, 0) is None and Numbering.parse(None).level(1, 0) is None


def test_counter_cascade_and_multilevel_text():
    c = NumberingCounter(Numbering.parse(etree.fromstring(NUM)))
    assert c.next(1, 0).marker == "1."
    assert c.next(1, 1).marker == "(a)"
    assert c.next(1, 1).marker == "(b)"
    assert c.next(1, 2).marker == "1.b.i"  # each placeholder uses its own level's numFmt (Word; matches the reference engine)
    assert c.next(1, 0).marker == "2."
    assert c.next(1, 1).marker == "(a)"      # reset by the shallower increment


def test_counter_shared_abstract_continues_and_override_restarts():
    c = NumberingCounter(Numbering.parse(etree.fromstring(NUM)))
    c.next(1, 0); c.next(1, 0)
    assert c.next(2, 0).marker == "1."       # numId 2 overrides start on first use
    assert c.next(2, 0).marker == "2."
    assert c.next(1, 0).marker == "3."       # same abstract list, counter continued through the override


def test_bullets():
    c = NumberingCounter(Numbering.parse(etree.fromstring(NUM)))
    info = c.next(3, 0)
    assert info.is_bullet and info.marker == BULLETS[0]
