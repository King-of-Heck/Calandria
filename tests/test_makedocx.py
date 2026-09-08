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
