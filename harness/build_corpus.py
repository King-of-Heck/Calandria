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
    # A pair with a missing side is left OUT of the written manifest: half a pair would make the
    # gate fail on a file that was never there, which reads as a parity regression. Report the
    # missing files and exit non-zero so the omission is not mistaken for a clean build.
    kept, missing = [], []
    for p in pairs:
        gaps = [src / p[key] for key in ("a", "b") if not (src / p[key]).exists()]
        if gaps:
            missing.extend(gaps)
            continue
        for key in ("a", "b"):
            shutil.copyfile(src / p[key], CORPUS / p[key])
        kept.append(p)
    (CORPUS / "manifest.json").write_text(json.dumps({"pairs": kept}, indent=1), "utf8")
    print(f"corpus: {len(kept)} pairs -> {CORPUS}")
    if missing:
        for m in missing:
            print(f"MISSING {m}")
        print(f"{len(pairs) - len(kept)} pair(s) excluded from the manifest")
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv)
