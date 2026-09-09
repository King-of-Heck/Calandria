"""Golden page counts for the corpus: each side laid out alone and the redline of the pair.

Usage: uv run python harness/golden_pages.py      -> writes tests/parity/golden-pages.json

Counts depend on the fonts installed on the machine (metrics come from the system font files),
so regenerate on the machine the gate runs on, review the diff, and commit an accepted change
together with the layout change that caused it.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from calandria.diff.compare import compare            # noqa: E402
from calandria.docx.parser import parse_docx          # noqa: E402
from calandria.layout.engine import layout, layout_document   # noqa: E402
from parity.common import CORPUS, pairs               # noqa: E402

OUT = ROOT / "tests" / "parity" / "golden-pages.json"


def counts(pair: dict) -> dict:
    a, b = parse_docx(CORPUS / pair["a"]), parse_docx(CORPUS / pair["b"])
    return {"a": layout_document(a).page_count, "b": layout_document(b).page_count,
            "redline": layout(compare(a, b)).page_count}


def main() -> int:
    golden = {p["alias"]: counts(p) for p in pairs()}
    OUT.write_text(json.dumps(golden, indent=1, sort_keys=True) + "\n", "utf8")
    for alias, v in sorted(golden.items()):
        print(f"{alias:12s} a={v['a']:4d} b={v['b']:4d} redline={v['redline']:4d}")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
