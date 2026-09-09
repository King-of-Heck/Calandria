"""Copy the regression pairs into tests/corpus/ (git-ignored).

Usage: uv run python harness/build_corpus.py [manifest]
  manifest defaults to harness/corpus.template.json; pass tests/corpus/manifest.local.json
  to include local-only pairs (real documents). Source dir: $SORKWHARE_DIR/tests/fixtures.
Set SORKWHARE_DIR or defaults to the sibling folder ../SorkWhare.
"""
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SORKWHARE = ROOT.parent / "SorkWhare"
CORPUS = ROOT / "tests" / "corpus"


def main(argv):
    src = Path(os.environ.get("SORKWHARE_DIR", DEFAULT_SORKWHARE)) / "tests" / "fixtures"
    manifest = Path(argv[1]) if len(argv) > 1 else ROOT / "harness" / "corpus.template.json"
    pairs = json.loads(manifest.read_text("utf8"))["pairs"]
    CORPUS.mkdir(parents=True, exist_ok=True)
    for p in pairs:
        for key in ("a", "b"):
            s = src / p[key]
            if not s.exists():
                print(f"MISSING {s}")
                continue
            shutil.copyfile(s, CORPUS / p[key])
    (CORPUS / "manifest.json").write_text(json.dumps({"pairs": pairs}, indent=1), "utf8")
    print(f"corpus: {len(pairs)} pairs -> {CORPUS}")


if __name__ == "__main__":
    main(sys.argv)
