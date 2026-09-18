"""Counting the tracked revisions still inside a .docx (read as accepted; the count only feeds
the notice)."""
import io

from calandria.docx.package import Package
from calandria.docx.parser import parse_docx
from calandria.docx.revisions import REVISION_TAGS, count_revisions, revision_parts
from calandria.testing.makedocx import DOC, HDR, P, R, RELS, SECT, make_docx

INS = '<w:ins w:id="1" w:author="A" w:date="2026-09-17T00:00:00Z"><w:r><w:t>new</w:t></w:r></w:ins>'
DEL = '<w:del w:id="2" w:author="A" w:date="2026-09-17T00:00:00Z"><w:r><w:delText>old</w:delText></w:r></w:del>'
MARK_DEL = '<w:p><w:pPr><w:rPr><w:del w:id="3" w:author="A"/></w:rPr></w:pPr>' + R("joined") + "</w:p>"
ROW_INS = ('<w:tbl><w:tr><w:trPr><w:ins w:id="4" w:author="A"/></w:trPr><w:tc>' + P("cell") +
           "</w:tc></w:tr></w:tbl>")
RPR_CHANGE = ('<w:p><w:r><w:rPr><w:b/><w:rPrChange w:id="5" w:author="A"><w:rPr/></w:rPrChange></w:rPr>'
              "<w:t>bold now</w:t></w:r></w:p>")
MOVE = ('<w:p><w:moveFrom w:id="6" w:author="A"><w:r><w:t>x</w:t></w:r></w:moveFrom>'
        '<w:moveTo w:id="7" w:author="A"><w:r><w:t>x</w:t></w:r></w:moveTo></w:p>')


def _count(parts):
    with Package.open(io.BytesIO(make_docx(parts))) as pkg:
        return count_revisions(pkg)


def test_clean_document_counts_zero():
    assert _count({"word/document.xml": DOC(P("plain") + P("text"))}) == 0


def test_run_insertion_and_deletion_count_one_each():
    assert _count({"word/document.xml": DOC("<w:p>" + R("kept ") + INS + DEL + "</w:p>")}) == 2


def test_tracked_paragraph_mark_counts():
    assert _count({"word/document.xml": DOC(MARK_DEL + P("next"))}) == 1


def test_tracked_table_row_counts():
    assert _count({"word/document.xml": DOC(ROW_INS)}) == 1


def test_run_formatting_change_counts():
    assert _count({"word/document.xml": DOC(RPR_CHANGE)}) == 1


def test_move_pair_counts_two():
    assert _count({"word/document.xml": DOC(MOVE)}) == 2


def test_revision_in_a_header_part_counts():
    parts = {"word/document.xml": DOC(P("body") + SECT(hdr={"default": "rId1"})),
             "word/_rels/document.xml.rels": RELS({"rId1": "header1.xml"}),
             "word/header1.xml": HDR("<w:p>" + INS + "</w:p>")}
    assert _count(parts) == 1


def test_revision_in_notes_counts():
    fn = (f'<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
          f'<w:footnote w:id="1"><w:p>{DEL}</w:p></w:footnote></w:footnotes>')
    assert _count({"word/document.xml": DOC(P("body")), "word/footnotes.xml": fn}) == 1


def test_mixed_document_sums_every_kind():
    parts = {"word/document.xml": DOC("<w:p>" + INS + DEL + "</w:p>" + MARK_DEL + ROW_INS + RPR_CHANGE + MOVE
                                      + SECT(hdr={"default": "rId1"})),
             "word/_rels/document.xml.rels": RELS({"rId1": "header1.xml"}),
             "word/header1.xml": HDR("<w:p>" + INS + "</w:p>")}
    assert _count(parts) == 2 + 1 + 1 + 1 + 2 + 1


def test_revision_parts_lists_only_present_parts_once():
    parts = {"word/document.xml": DOC(P("b") + SECT(hdr={"default": "rId1"}, ftr={"default": "rId1"})),
             "word/_rels/document.xml.rels": RELS({"rId1": "header1.xml", "rId2": "footer9.xml"}),
             "word/header1.xml": HDR(P("h"))}
    with Package.open(io.BytesIO(make_docx(parts))) as pkg:
        assert revision_parts(pkg) == ["word/document.xml", "word/header1.xml"]


def test_revision_tags_are_the_wordprocessingml_revision_elements():
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    assert {t[len(ns):] for t in REVISION_TAGS} == {
        "ins", "del", "moveFrom", "moveTo", "rPrChange", "pPrChange", "tblPrChange", "trPrChange",
        "tcPrChange", "sectPrChange", "tblGridChange", "numberingChange"}


def test_parsed_document_carries_the_count_and_still_reads_as_accepted():
    d = parse_docx(io.BytesIO(make_docx({"word/document.xml": DOC("<w:p>" + R("kept ") + INS + DEL + "</w:p>")})))
    assert d.tracked_changes == 2
    assert d.blocks[0].text == "kept new"          # accept-all reading is unchanged


def test_clean_parsed_document_reads_zero():
    assert parse_docx(io.BytesIO(make_docx({"word/document.xml": DOC(P("x"))}))).tracked_changes == 0
