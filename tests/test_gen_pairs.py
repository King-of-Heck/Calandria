import io
import json
import sys
from pathlib import Path

from calandria.diff.compare import compare
from calandria.docx.parser import parse_docx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "harness"))
import gen_pairs  # noqa: E402


def test_every_pair_parses_and_compares(tmp_path):
    pairs = gen_pairs.write_all(tmp_path)
    assert [p["alias"] for p in pairs] == ["gen-fmt", "gen-table", "gen-punct", "gen-dense", "gen-longcap",
                                           "gen-empty", "gen-latin1"]
    manifest = json.loads((tmp_path / "manifest.gen.json").read_text("utf8"))
    assert manifest["pairs"] == pairs
    for p in pairs:
        c = compare(parse_docx(tmp_path / p["a"]), parse_docx(tmp_path / p["b"]))
        assert c.rows, p["alias"]


def test_fmt_pair_exercises_every_formatting_attribute():
    a, b = gen_pairs.PAIRS["fmt"]
    c = compare(parse_docx(io.BytesIO(gen_pairs.build(a))), parse_docx(io.BytesIO(gen_pairs.build(b))))
    descs = sorted(d for r in c.rows for d in (x.desc for x in r.fmt_ranges))
    assert descs == ["bold added", "colour default → #ff0000", "font Calibri → Arial",
                     "italic added", "size 11 → 14", "underline added"]
    assert c.summary["formatting"] == 6 and c.summary["total"] == 1


def test_longcap_pair_is_above_the_inline_cap():
    from calandria.diff.inline import INLINE_TOKEN_CAP
    from calandria.diff.text import tokenize
    a, _b = gen_pairs.PAIRS["longcap"]
    d = parse_docx(io.BytesIO(gen_pairs.build(a)))
    assert len(tokenize(d.blocks[0].text)) > INLINE_TOKEN_CAP
