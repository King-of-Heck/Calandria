import os

import pytest

from calandria.diff.compare import compare
from calandria.model import Table
from calandria.pdfread import parse_pdf
from calandria.pdfread.extract import NO_TEXT
from calandria.pdfread.types import PdfRefused
from calandria.testing.makepdf import make_pdf

ARIAL = r"C:\Windows\Fonts\arial.ttf"
pytestmark = pytest.mark.skipif(not os.path.isfile(ARIAL), reason="needs a system TrueType font for real glyph widths")

FULL = "The Supplier shall deliver the Goods to the Buyer at the Delivery Point on the agreed date."
END = "and not later."


def para(y, last=END):
    return [("text", 72, y, 11, FULL), ("text", 72, y + 13, 11, FULL), ("text", 72, y + 26, 11, last)]


def contract(word="Goods", pages=4):
    out = []
    for i in range(pages):
        items = [("text", 72, 40, 9, "Acme Supply Agreement"), ("text", 280, 760, 9, f"Page {i + 1} of {pages}")]
        items += para(100) + para(160, last=f"These {word} are described in Schedule {i + 1}.")
        if i == 1:
            items += [("rect", 72, 300, 400, 40), ("line", 272, 300, 272, 340), ("line", 72, 320, 472, 320),
                      ("text", 78, 314, 11, "Item"), ("text", 278, 314, 11, "Price"),
                      ("text", 78, 334, 11, "Bolt"), ("text", 278, 334, 11, "1.00")]
        out.append(items)
    return make_pdf(out, ttf=ARIAL)


def test_a_contract_reads_as_paragraphs_a_table_and_no_furniture():
    doc = parse_pdf(contract())
    texts = [b.text for b in doc.blocks if not isinstance(b, Table)]
    assert len(texts) == 8 and all(t.startswith("The Supplier shall") for t in texts)
    assert not any("Acme" in t or "Page " in t for t in texts)
    (table,) = [b for b in doc.blocks if isinstance(b, Table)]
    assert [[c.blocks[0].text for c in r.cells] for r in table.rows] == [["Item", "Price"], ["Bolt", "1.00"]]
    assert (doc.source_kind, doc.source_pages, doc.skipped_pages) == ("pdf", 4, ())
    assert doc.default_font == "Arial"


def test_two_versions_compare_to_the_edited_words_and_a_pdf_equals_itself():
    assert compare(parse_pdf(contract()), parse_pdf(contract())).summary["total"] == 0
    cmp = compare(parse_pdf(contract("Goods")), parse_pdf(contract("Services")))
    assert 1 <= cmp.summary["total"] <= 8           # one word on each of four pages, however a replacement is counted


def test_a_paragraph_running_over_a_page_break_is_one_paragraph():
    # Below the header band: an identical line at an identical height on every page is furniture.
    p1 = [("text", 72, 200 + 13 * i, 11, FULL) for i in range(3)]
    p2 = [("text", 72, 200, 11, FULL), ("text", 72, 213, 11, END)]
    doc = parse_pdf(make_pdf([p1, p2], ttf=ARIAL))
    assert len(doc.blocks) == 1 and doc.blocks[0].text.count("The Supplier") == 4


def test_a_scanned_page_is_skipped_and_named_and_an_all_scanned_pdf_is_refused():
    doc = parse_pdf(make_pdf([para(100), [("image", 0, 0, 612, 792)], para(100)], ttf=ARIAL))
    assert doc.skipped_pages == (2,) and doc.source_pages == 3 and len(doc.blocks) == 2
    with pytest.raises(PdfRefused) as e:
        parse_pdf(make_pdf([[("image", 0, 0, 612, 792)]]))
    assert str(e.value) == NO_TEXT


def test_progress_reaches_the_caller():
    seen = []
    parse_pdf(contract(pages=3), lambda done, total: seen.append((done, total)))
    assert seen[-1] == (3, 3)
