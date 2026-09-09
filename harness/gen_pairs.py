"""Synthetic regression pairs for the change-list gate (formatting, tables, punctuation, dense
rewrites, the inline token cap). Written into tests/corpus/ (git-ignored) with manifest.gen.json.

Usage: uv run python harness/gen_pairs.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from calandria.testing.makedocx import DOC, P, PR, R, STYLES, TBL, make_docx  # noqa: E402

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

PAIRS = {
    "fmt": _pair(_FMT_A, _FMT_B),
    "table": _pair(_TABLE_A, _TABLE_B),
    "punct": _pair(_PUNCT_A, _PUNCT_B),
    "dense": _pair(_DENSE_A, _DENSE_B),
    "longcap": _pair(_LONGCAP_A, _LONGCAP_B),
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
