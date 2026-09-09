"""Smoke check, never a gate: our page count of a .docx next to the page count of the PDF that
Word exported from it.

Put Word's PDFs in tests/fixtures/wordpdf/<stem>.pdf, where <stem> is the .docx file name
without its extension (looked up in tests/corpus/ then tests/fixtures/). Word's PDFs often keep
their page objects in compressed object streams, where the byte scan finds nothing; put the
count in a sidecar tests/fixtures/wordpdf/<stem>.pages (one integer) in that case.

Usage: uv run python harness/word_pages.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from calandria.docx.parser import parse_docx                  # noqa: E402
from calandria.layout.engine import layout_document           # noqa: E402

PDF_DIR = ROOT / "tests" / "fixtures" / "wordpdf"
_PAGE = re.compile(rb"/Type\s*/Page(?![s/A-Za-z])")


def word_pages(pdf: Path) -> str:
    side = pdf.with_suffix(".pages")
    if side.exists():
        return side.read_text("utf8").strip()
    n = len(_PAGE.findall(pdf.read_bytes()))
    return str(n) if n else "?"


def main() -> int:
    pdfs = sorted(PDF_DIR.glob("*.pdf")) if PDF_DIR.exists() else []
    if not pdfs:
        print(f"no Word PDFs in {PDF_DIR}")
        return 0
    print(f"{'document':32s} {'word':>5s} {'ours':>5s}")
    for pdf in pdfs:
        docx = next((d for d in (ROOT / "tests" / "corpus" / f"{pdf.stem}.docx",
                                 ROOT / "tests" / "fixtures" / f"{pdf.stem}.docx") if d.exists()), None)
        if docx is None:
            print(f"{pdf.stem:32s} (no matching .docx)")
            continue
        ours = layout_document(parse_docx(docx)).page_count
        print(f"{pdf.stem:32s} {word_pages(pdf):>5s} {ours:5d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
