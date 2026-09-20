"""Synthetic regression pairs for the change-list gate (formatting, tables, punctuation, dense
rewrites, the inline token cap). Written into tests/corpus/ (git-ignored) with manifest.gen.json.

Usage: uv run python harness/gen_pairs.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from calandria.testing.makedocx import (COMMENTS, COMMENTS_EX, CRANGE, CREF, CRELS, DOC, ENDNOTES, ENREF,
                                        FLD, FNREF, FOOTNOTES, FTR, HDR, NUMBERING, P, PR, R, RELS, SECT,
                                        SETTINGS, STYLES, TBL, make_docx)  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "corpus"
_DEFAULTS = STYLES('<w:rFonts w:ascii="Calibri"/><w:sz w:val="22"/>')


def _pair(body_a: str, body_b: str, styles: str = _DEFAULTS):
    return ({"word/document.xml": DOC(body_a), "word/styles.xml": styles},
            {"word/document.xml": DOC(body_b), "word/styles.xml": styles})


def build(parts: dict) -> bytes:
    return make_docx(parts)


_FMT_A = (P("Bold words appear here") + P("Italic clause") + P("Underlined clause") + P("Bigger clause")
          + P("Coloured clause") + P("Font clause") + P("Unchanged tail") + P("Content changes here"))
_FMT_B = (PR(R("Bold ") + R("words", "<w:b/>") + R(" appear here")) + P("Italic clause", rpr="<w:i/>")
          + P("Underlined clause", rpr='<w:u w:val="single"/>') + P("Bigger clause", rpr='<w:sz w:val="28"/>')
          + P("Coloured clause", rpr='<w:color w:val="FF0000"/>')
          + P("Font clause", rpr='<w:rFonts w:ascii="Arial"/>') + P("Unchanged tail")
          + P("Content changed here"))

_TABLE_A = P("Intro") + TBL([["Item", "Qty"], ["Bolt", "10 units"], ["Nut", "20 units"]]) + P("Outro")
_TABLE_B = P("Intro") + TBL([["Item", "Qty"], ["Bolt", "12 units"], ["Nut", "20 units"], ["Washer", "5"]]) + P("Outro")

_PUNCT_A = P("Hello, world.") + P("The Provider shall deliver.") + P("Same line")
_PUNCT_B = P("Hello world") + P("The provider shall deliver.") + P("Same line")

_DENSE_A = (P("Payment is due to the Contractor on the first day of each month by wire transfer.")
            + P("Red and blue cars are parked outside."))
_DENSE_B = (P("Payment is owed to the Supplier on the last day of each quarter by cheque.")
            + P("Green and yellow cars are parked outside."))

_LONG = " ".join(f"w{i}" for i in range(2100))
_LONGCAP_A = P(_LONG) + P("End")
_LONGCAP_B = P(_LONG.replace("w1000 ", "changed ")) + P("End")

_EMPTY_A = P("Only paragraph") + P("Second paragraph")
_EMPTY_B = ""
_LATIN1_A = P("Café résumé naïve façade") + P("Same line")
_LATIN1_B = P("Cafe resume naive facade") + P("Same line")

# Notes: an edited footnote, a note added with its reference, a note dropped with its paragraph,
# a shared note, an endnote, and a body paragraph whose text equals a note's (must not pair).
_NOTES_A = (PR(R("The Supplier delivers within thirty days") + FNREF(1) + R(" of the order."))
            + PR(R("Payment follows on receipt") + FNREF(2) + R("."))
            + PR(R("This clause goes away") + FNREF(3) + R("."))
            + P("Same words as a note")
            + PR(R("Governing law") + ENREF(1) + R(" applies.")))
_NOTES_B = (PR(R("The Supplier delivers within thirty days") + FNREF(1) + R(" of the order."))
            + PR(R("Payment follows on receipt") + FNREF(2) + R(" of a valid invoice") + FNREF(4) + R("."))
            + P("Same words as a note")
            + PR(R("Governing law") + ENREF(1) + R(" applies.")))
_NOTES_FA = FOOTNOTES({1: "Thirty calendar days.", 2: "Receipt means delivery to the registered office.",
                       3: "A note that goes away with its clause."})
_NOTES_FB = FOOTNOTES({1: "Thirty business days.", 2: "Receipt means delivery to the registered office.",
                       4: "Same words as a note"})
_NOTES_EN = ENDNOTES({1: "The law of Ontario."})


def _notes_pair():
    a = {"word/document.xml": DOC(_NOTES_A), "word/styles.xml": _DEFAULTS, "word/footnotes.xml": _NOTES_FA,
         "word/endnotes.xml": _NOTES_EN}
    b = {"word/document.xml": DOC(_NOTES_B), "word/styles.xml": _DEFAULTS, "word/footnotes.xml": _NOTES_FB,
         "word/endnotes.xml": _NOTES_EN}
    return a, b


# Headers and footers: three sections. 1: title page, cover header changed, running header shared,
# footer with a PAGE field. 2: no references (inherits); B adds an even header (even/odd is on).
# 3: a tall header that pushes the body, a blank footer part, numbering restarts.
_HF_BODY = "".join(P(f"Section one paragraph {i} with enough words to fill a line of the page.") for i in range(60))
_HF_S1 = "".join(PR(R(f"Section two paragraph {i}.")) for i in range(120))
_HF_S3 = "".join(P(f"Section three paragraph {i}.") for i in range(120))


def _hf_body(even_ref: dict) -> str:
    return (_HF_BODY
            + PR(R("End of section one."), ppr=SECT(hdr={"default": "rId1", "first": "rId2"}, ftr={"default": "rId3"},
                                                   title_pg=True, page_start=1))
            + _HF_S1 + PR(R("End of section two."), ppr=SECT(hdr=even_ref))
            + _HF_S3 + SECT(hdr={"default": "rId5"}, ftr={"default": "rId6"}, page_start=1))


_HF_RELS = RELS({"rId1": "header1.xml", "rId2": "header2.xml", "rId3": "footer1.xml", "rId4": "header3.xml",
                 "rId5": "header4.xml", "rId6": "footer2.xml"})
_HF_TALL = "".join(P(f"Tall header line {i}", ppr='<w:spacing w:after="120"/>') for i in range(4))


def _hf_pair():
    common = {"word/styles.xml": _DEFAULTS, "word/_rels/document.xml.rels": _HF_RELS,
              "word/settings.xml": SETTINGS(even_and_odd=True),
              "word/header1.xml": HDR(P("Running head")),
              "word/footer1.xml": FTR(PR(R("Page ") + FLD("PAGE"), ppr='<w:jc w:val="center"/>')),
              "word/header3.xml": HDR(P("Even side")),
              "word/header4.xml": HDR(_HF_TALL), "word/footer2.xml": FTR(P(""))}
    a = {**common, "word/document.xml": DOC(_hf_body({})), "word/header2.xml": HDR(P("Cover A"))}
    b = {**common, "word/document.xml": DOC(_hf_body({"even": "rId4"})), "word/header2.xml": HDR(P("Cover B"))}
    return a, b


# Comments: an edited + resolved comment, an added comment with a threaded reply, a comment on a
# clause that is deleted, a comment on inserted text, and two comments on one paragraph (packing).
_CM_A = (PR(R("The Supplier delivers the goods within ") + CRANGE("0", "thirty days") + R("."))
         + PR(R("Payment is due on receipt."))
         + PR(R("This clause ") + CRANGE("1", "will be removed") + R("."))
         + PR(R("Governing law applies.")))
_CM_B = (PR(R("The Supplier delivers the goods within ") + CRANGE("0", "thirty days") + R("."))
         + PR(R("Payment is due on ") + CRANGE("2", "receipt") + CREF("6") + R("."))
         + PR(R("Governing law applies. ") + CRANGE("3", "New inserted clause") + R("."))
         + PR(R("Two ") + CRANGE("4", "comments") + R(" on ") + CRANGE("5", "one line") + R(".")))
_CM_CA = COMMENTS([{"id": "0", "author": "Ada", "initials": "AL", "date": "2026-09-10T09:00:00Z",
                    "paras": [("a0", "Confirm the delivery window.")]},
                   {"id": "1", "author": "Ada", "initials": "AL", "date": "2026-09-10T09:05:00Z",
                    "paras": [("a1", "This clause is going.")]}])
_CM_CB = COMMENTS([{"id": "0", "author": "Ada", "initials": "AL", "date": "2026-09-10T09:00:00Z",
                    "paras": [("b0", "Confirm the delivery window is business days.")]},   # edited
                   {"id": "2", "author": "Bo", "initials": "BO", "date": "2026-09-11T10:00:00Z",
                    "paras": [("b2", "Define receipt.")]},
                   {"id": "6", "author": "Ada", "initials": "AL", "date": "2026-09-11T10:05:00Z",
                    "paras": [("b6", "Agreed - delivery to the office.")]},               # reply to 2
                   {"id": "3", "author": "Bo", "initials": "BO", "date": "2026-09-11T11:00:00Z",
                    "paras": [("b3", "New clause note.")]},
                   {"id": "4", "author": "Ada", "initials": "AL", "date": "2026-09-11T12:00:00Z",
                    "paras": [("b4", "First on line.")]},
                   {"id": "5", "author": "Ada", "initials": "AL", "date": "2026-09-11T12:01:00Z",
                    "paras": [("b5", "Second on line.")]}])
_CM_EXB = COMMENTS_EX([{"paraId": "b0", "done": True},      # the edited comment is resolved in B
                       {"paraId": "b6", "parent": "b2"}])    # the reply threads under comment 2


def _comments_pair():
    a = {"word/document.xml": DOC(_CM_A), "word/styles.xml": _DEFAULTS,
         "word/_rels/document.xml.rels": CRELS(comments=True), "word/comments.xml": _CM_CA}
    b = {"word/document.xml": DOC(_CM_B), "word/styles.xml": _DEFAULTS,
         "word/_rels/document.xml.rels": CRELS(comments=True, comments_ex=True),
         "word/comments.xml": _CM_CB, "word/commentsExtended.xml": _CM_EXB}
    return a, b


# Ruled tables: TBL() has no borders/gridSpan/vMerge/tblHeader, so these are built as raw XML in
# the style already used above for parts TBL() cannot express.
_BORDERS = "<w:tblBorders>" + "".join(
    f'<w:{side} w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
    for side in ("top", "left", "bottom", "right", "insideH", "insideV")) + "</w:tblBorders>"


def _ruled(rows_xml: str, grid: list[int]) -> str:
    g = "<w:tblGrid>" + "".join(f'<w:gridCol w:w="{w}"/>' for w in grid) + "</w:tblGrid>"
    return f"<w:tbl><w:tblPr>{_BORDERS}</w:tblPr>{g}{rows_xml}</w:tbl>"


def _cell(text: str = "", span: int | None = None, vmerge: str | None = None) -> str:
    pr = ""
    if span:
        pr += f'<w:gridSpan w:val="{span}"/>'
    if vmerge:
        pr += f'<w:vMerge w:val="{vmerge}"/>' if vmerge == "restart" else "<w:vMerge/>"
    tcpr = f"<w:tcPr>{pr}</w:tcPr>" if pr else ""
    return f"<w:tc>{tcpr}{P(text)}</w:tc>"


def _row(cells: str, header: bool = False) -> str:
    trpr = "<w:trPr><w:tblHeader/></w:trPr>" if header else ""
    return f"<w:tr>{trpr}{cells}</w:tr>"


# gen-grid: a 6 x 4 pricing grid, one cell merged across two columns, one merged down two rows.
def _grid_table(*, widget_b_q1: str, bundle_desc: str, bundle_total: str) -> str:
    rows = (
        _row(_cell("Item") + _cell("Description") + _cell("Q1 Price") + _cell("Q2 Price"), header=True)
        + _row(_cell("Widget A") + _cell("Standard widget") + _cell("10.00") + _cell("12.00"))
        + _row(_cell("Widget B") + _cell("Standard widget") + _cell(widget_b_q1) + _cell("15.00"))
        + _row(_cell("Bundle") + _cell(bundle_desc, span=2) + _cell(bundle_total))
        + _row(_cell("Widget C") + _cell("Limited edition", vmerge="restart") + _cell("20.00") + _cell("20.00"))
        + _row(_cell("Widget D") + _cell(vmerge="continue") + _cell("22.00") + _cell("22.00")))
    return _ruled(rows, grid=[2000, 4000, 1800, 1800])


_GRID_A = _grid_table(widget_b_q1="15.00", bundle_desc="Bundle covers both tiers", bundle_total="18.00")
_GRID_B = _grid_table(widget_b_q1="16.50", bundle_desc="Bundle covers three tiers", bundle_total="19.00")
_PAIR_GRID = _pair(P("Pricing Grid") + _GRID_A + P("End of grid"),
                   P("Pricing Grid") + _GRID_B + P("End of grid"))


# gen-longtable: a ruled 110-row x 3-column table with a repeating header row, long enough to run
# over three pages. B changes a cell near the start, middle and end (landing on three different
# pages), and inserts a row mid-table.
_LT_ROW_COUNT = 110


def _lt_row(i: int, value: str | None = None, note: str | None = None) -> str:
    return _row(_cell(f"Row {i}") + _cell(value or f"Value {i}") + _cell(note or f"Note {i}"))


def _lt_rows(overrides: dict | None = None, insert_after: int | None = None, insert_row: str = "") -> str:
    rows = _row(_cell("Row") + _cell("Value") + _cell("Note"), header=True)
    for i in range(1, _LT_ROW_COUNT):
        o = (overrides or {}).get(i, {})
        rows += _lt_row(i, **o)
        if i == insert_after:
            rows += insert_row
    return rows


_LONGTABLE_A = _ruled(_lt_rows(), grid=[2000, 2000, 4000])
_LONGTABLE_B = _ruled(_lt_rows(
    overrides={15: {"value": "Value 15 (updated)"}, 55: {"note": "Note 55 revised"},
               100: {"value": "Value 100 (updated)"}},
    insert_after=55, insert_row=_lt_row("55b")), grid=[2000, 2000, 4000])
_PAIR_LONGTABLE = _pair(P("Long Table") + _LONGTABLE_A + P("End of table"),
                        P("Long Table") + _LONGTABLE_B + P("End of table"))


# gen-schedule: numbered clauses, a "Schedule 1" heading, a ruled 8x3 table, two more paragraphs,
# then a second ruled 4x2 table. B edits a clause, a cell in each table, and the paragraph between them.
_SCHED_NUM = NUMBERING([("decimal", "%1.", 720, 360, "space")])
_SCHED_NUMPR = '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>'


def _sched_clause(text: str) -> str:
    return P(text, ppr=_SCHED_NUMPR)


def _sched_table_a(rows: int, cols: int, *, edit: str | None = None) -> str:
    body = _row("".join(_cell(f"H{c}") for c in range(cols)), header=True)
    for r in range(1, rows):
        cells = "".join(_cell(edit if (edit and r == 1 and c == 0) else f"R{r}C{c}") for c in range(cols))
        body += _row(cells)
    return _ruled(body, grid=[1800] * cols)


def _schedule_pair():
    clause_edit = "The Supplier shall deliver within thirty days."
    clause_edit_b = "The Supplier shall deliver within forty-five days."
    mid_para = "This schedule sets out the pricing and delivery terms."
    mid_para_b = "This schedule sets out the pricing, delivery and support terms."
    a = (_sched_clause("The parties agree to the terms below.")
         + _sched_clause(clause_edit)
         + _sched_clause("This agreement is governed by the laws of Ontario.")
         + P("Schedule 1")
         + _sched_table_a(8, 3)
         + P(mid_para) + P("See the table below for support tiers.")
         + _sched_table_a(4, 2, edit="X0Y0"))
    b = (_sched_clause("The parties agree to the terms below.")
         + _sched_clause(clause_edit_b)
         + _sched_clause("This agreement is governed by the laws of Ontario.")
         + P("Schedule 1")
         + _sched_table_a(8, 3, edit="R1C0-changed")
         + P(mid_para_b) + P("See the table below for support tiers.")
         + _sched_table_a(4, 2, edit="X0Y0-changed"))
    return a, b


_PAIR_SCHEDULE = _schedule_pair()


def _pair_with_numbering(body_a: str, body_b: str):
    a, b = _pair(body_a, body_b)
    a["word/numbering.xml"] = _SCHED_NUM
    b["word/numbering.xml"] = _SCHED_NUM
    return a, b


PAIRS = {
    "fmt": _pair(_FMT_A, _FMT_B),
    "table": _pair(_TABLE_A, _TABLE_B),
    "punct": _pair(_PUNCT_A, _PUNCT_B),
    "dense": _pair(_DENSE_A, _DENSE_B),
    "longcap": _pair(_LONGCAP_A, _LONGCAP_B),
    "empty": _pair(_EMPTY_A, _EMPTY_B),
    "latin1": _pair(_LATIN1_A, _LATIN1_B),
    "notes": _notes_pair(),
    "hf": _hf_pair(),
    "comments": _comments_pair(),
    "grid": _PAIR_GRID,
    "longtable": _PAIR_LONGTABLE,
    "schedule": _pair_with_numbering(*_PAIR_SCHEDULE),
}


def write_all(corpus: Path) -> list[dict]:
    corpus.mkdir(parents=True, exist_ok=True)
    out = []
    for name, (a, b) in PAIRS.items():
        fa, fb = f"gen-{name}-A.docx", f"gen-{name}-B.docx"
        (corpus / fa).write_bytes(build(a))
        (corpus / fb).write_bytes(build(b))
        out.append({"alias": f"gen-{name}", "a": fa, "b": fb})
    (corpus / "manifest.gen.json").write_text(json.dumps({"pairs": out}, indent=1), "utf8")
    return out


if __name__ == "__main__":
    pairs = write_all(CORPUS)
    print(f"generated: {len(pairs)} pairs -> {CORPUS}")
