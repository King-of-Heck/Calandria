"""Synthetic regression pairs for the change-list gate (formatting, tables, punctuation, dense
rewrites, the inline token cap). Written into tests/corpus/ (git-ignored) with manifest.gen.json.

Usage: uv run python harness/gen_pairs.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from calandria.testing.makedocx import (DOC, ENDNOTES, ENREF, FLD, FNREF, FOOTNOTES, FTR, HDR, P, PR, R, RELS, SECT,
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
