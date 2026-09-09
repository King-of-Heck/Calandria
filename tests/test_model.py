from calandria.model import (Run, RunProps, Paragraph, ParaProps, Table, Row, Cell,
                             Document, Section, collapse_ws)


def test_paragraph_text_collapses_whitespace():
    p = Paragraph([Run("alpha    beta\t", RunProps()), Run(" gamma ", RunProps())], ParaProps())
    assert p.text == "alpha beta gamma"
    assert not p.is_empty
    assert Paragraph([Run("  \n ", RunProps())], ParaProps()).is_empty


def test_document_paragraphs_walks_tables():
    inner = Paragraph([Run("cell", RunProps())], ParaProps())
    t = Table([Row([Cell([inner])])], grid_pt=[100.0])
    body = Paragraph([Run("body", RunProps())], ParaProps())
    d = Document([body, t], [Section()])
    assert [p.text for p in d.paragraphs()] == ["body", "cell"]


def test_collapse_ws():
    assert collapse_ws(" a \r\n b ") == "a b"


def test_collapse_ws_uses_the_reference_whitespace_class():
    assert collapse_ws("x" + chr(0xfeff) + chr(0xfeff) + "y") == "x y"
