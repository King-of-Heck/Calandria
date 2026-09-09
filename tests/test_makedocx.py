import zipfile, io
from calandria.testing.makedocx import make_docx, DOC, P


def test_make_docx_roundtrip():
    data = make_docx({"word/document.xml": DOC(P("Hello world"))})
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        assert z.namelist() == ["word/document.xml"]
        xml = z.read("word/document.xml").decode("utf8")
    assert "<w:t xml:space=\"preserve\">Hello world</w:t>" in xml
    assert xml.startswith("<w:document")


def test_p_with_props():
    xml = P("x", ppr="<w:jc w:val=\"center\"/>", rpr="<w:b/>")
    assert xml == ('<w:p><w:pPr><w:jc w:val="center"/></w:pPr>'
                   '<w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">x</w:t></w:r></w:p>')


from calandria.testing.makedocx import PR, R, STYLES, TBL


def test_run_and_paragraph_helpers():
    assert R("x") == '<w:r><w:t xml:space="preserve">x</w:t></w:r>'
    assert R("x", "<w:b/>") == '<w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">x</w:t></w:r>'
    assert PR(R("a") + R("b"), '<w:jc w:val="center"/>') == (
        '<w:p><w:pPr><w:jc w:val="center"/></w:pPr>' + R("a") + R("b") + "</w:p>")
    assert PR(R("a")) == "<w:p>" + R("a") + "</w:p>"


def test_table_and_styles_helpers():
    assert TBL([["a", "b"], ["c"]]) == ("<w:tbl><w:tr><w:tc>" + P("a") + "</w:tc><w:tc>" + P("b")
                                        + "</w:tc></w:tr><w:tr><w:tc>" + P("c") + "</w:tc></w:tr></w:tbl>")
    s = STYLES('<w:rFonts w:ascii="Calibri"/><w:sz w:val="22"/>')
    assert s.startswith('<w:styles xmlns:w="') and "<w:docDefaults><w:rPrDefault><w:rPr>" in s
    assert '<w:rFonts w:ascii="Calibri"/><w:sz w:val="22"/></w:rPr></w:rPrDefault>' in s
