"""How long does reading a PDF take? Times extract_pages on (1) the hundred-page redline this
repo can write by itself and (2) any PDFs named on the command line.

    uv run python harness/pdf_timing.py [file.pdf ...]
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

LAPTOP_FACTOR = 6.5      # the work laptop against this desktop, measured for v2.4.3


def own_pdf() -> bytes:
    from calandria.diff.compare import compare
    from calandria.docx.parser import parse_docx
    from calandria.layout.engine import layout
    from calandria.pdf.draw import PdfOptions
    from calandria.pdf.report import report_info
    from calandria.pdf.writer import render
    from calandria.testing.makedocx import DOC, make_docx
    from calandria.testing.perfdoc import hundred_page_pair
    a, b = hundred_page_pair()
    docs = [parse_docx(io.BytesIO(make_docx({"word/document.xml": DOC(x)}))) for x in (a, b)]
    cmp = compare(*docs)
    data, _ = render(layout(cmp), report_info(cmp, "a.docx", "b.docx", "Standard"), PdfOptions())
    return data


def measure(label: str, data: bytes) -> None:
    from calandria.pdfread.extract import extract_pages
    t0 = time.perf_counter()
    pages = extract_pages(data)
    secs = time.perf_counter() - t0
    runs = sum(len(p.runs) for p in pages)
    print(f"{label}: pages={len(pages)} runs={runs} seconds={secs:.2f} per_page_ms={1000 * secs / max(1, len(pages)):.1f} "
          f"laptop_estimate_s={secs * LAPTOP_FACTOR:.1f}")


def main(argv) -> int:
    measure("own-hundred-pages", own_pdf())
    for path in argv:
        measure(Path(path).name.encode("ascii", "replace").decode("ascii"), Path(path).read_bytes())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
