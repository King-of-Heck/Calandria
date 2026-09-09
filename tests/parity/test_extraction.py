"""Gate: Calandria's extraction matches SorkWhare 1.16.0 on the corpus, modulo explained divergences."""
import json
import math
from pathlib import Path

import pytest

from calandria.docx.parser import parse_docx
from calandria.harness.flatten import flatten

HERE = Path(__file__).resolve().parent
CORPUS = HERE.parent / "corpus"
ORACLE = HERE.parent / "oracle"
ALLOW = json.loads((HERE / "allow.json").read_text("utf8"))
FIELDS = ["text", "marker", "isNumbered", "ilvl", "styleId", "align", "indLeftPt", "indHangingPt",
          "indFirstLinePt", "spaceBeforePt", "spaceAfterPt", "lineSpacing", "keepNext", "keepLines",
          "pageBreakBefore", "contextualSpacing", "heading", "tbl"]


def _eq(a, b):
    if isinstance(a, float) or isinstance(b, float):
        if a is None or b is None:
            return a == b
        return math.isclose(float(a), float(b), abs_tol=0.05)
    return a == b


def divergences(ours, ref):
    if len(ours) != len(ref):
        return [{"i": min(len(ours), len(ref)), "field": "count", "ours": len(ours), "ref": len(ref)}]
    out = []
    for i, (o, r) in enumerate(zip(ours, ref)):
        for f in FIELDS:
            if not _eq(o.get(f), r.get(f)):
                out.append({"i": i, "field": f, "ours": o.get(f), "ref": r.get(f)})
    return out


def allowed(div, alias, allow=ALLOW):
    return any(a["field"] == div["field"] and a["alias"] in ("*", alias) for a in allow)


def _pairs():
    m = CORPUS / "manifest.json"
    if not m.exists():
        return []
    return json.loads(m.read_text("utf8"))["pairs"]


@pytest.mark.parametrize("pair", _pairs(), ids=lambda p: p["alias"])
@pytest.mark.parametrize("side", ["a", "b"])
def test_extraction_parity(pair, side):
    oracle_file = ORACLE / f"{pair['alias']}.json"
    if not oracle_file.exists():
        pytest.skip("run: node harness/oracle_export.mjs")
    ref = json.loads(oracle_file.read_text("utf8"))[side.upper()]["paras"]
    ours = flatten(parse_docx(CORPUS / pair[side]))
    divs = [d for d in divergences(ours, ref) if not allowed(d, pair["alias"])]
    if divs:
        lines = [f"[{d['i']}] {d['field']}: ours={d['ours']!r} ref={d['ref']!r}" for d in divs[:25]]
        pytest.fail(f"{pair['alias']}/{side}: {len(divs)} unexplained divergences\n" + "\n".join(lines))


def test_divergences_unit():
    assert divergences([{"text": "a"}], [{"text": "a"}]) == []
    assert divergences([{"text": "a"}], [{"text": "b"}]) == [{"i": 0, "field": "text", "ours": "a", "ref": "b"}]
    assert divergences([], [{"text": "a"}])[0]["field"] == "count"
    assert divergences([{"indLeftPt": 36.0}], [{"indLeftPt": 36.04}]) == []
    assert allowed({"field": "marker"}, "anything") and not allowed({"field": "text"}, "anything")


def test_no_pairs_means_corpus_not_built():
    assert _pairs(), "run: uv run python harness/build_corpus.py && node harness/oracle_export.mjs"
