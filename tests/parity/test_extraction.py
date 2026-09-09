"""Gate: Calandria's extraction matches SorkWhare 1.16.0 on the corpus, modulo explained divergences."""
# Deliberate model-vs-reference differences (and the allow.json policy): KNOWN_DIVERGENCES.md.
import json

import pytest

from calandria.docx.parser import parse_docx
from calandria.harness.flatten import flatten

from .common import CORPUS, ORACLE, allowed, divergences, load_allow, pairs

ALLOW = load_allow("allow.json")
FIELDS = ["text", "marker", "isNumbered", "ilvl", "styleId", "align", "indLeftPt", "indHangingPt",
          "indFirstLinePt", "spaceBeforePt", "spaceAfterPt", "lineSpacing", "lineExactPt", "keepNext",
          "keepLines", "pageBreakBefore", "contextualSpacing", "heading", "boldRuns", "tbl"]


@pytest.mark.parametrize("pair", pairs(), ids=lambda p: p["alias"])
@pytest.mark.parametrize("side", ["a", "b"])
def test_extraction_parity(pair, side):
    oracle_file = ORACLE / f"{pair['alias']}.json"
    # A missing oracle FAILS rather than skips: a silently skipped gate is indistinguishable
    # from a passing one, and this is the only thing holding extraction to the reference.
    assert oracle_file.exists(), "run: node harness/oracle_export.mjs"
    ref = json.loads(oracle_file.read_text("utf8"))[side.upper()]["paras"]
    if ref:
        assert all(f in ref[0] for f in FIELDS), "stale oracle: run node harness/oracle_export.mjs"
    ours = flatten(parse_docx(CORPUS / pair[side]))
    divs = [d for d in divergences(ours, ref, FIELDS) if not allowed(d, pair["alias"], ALLOW)]
    if divs:
        lines = [f"[{d['i']}] {d['field']}: ours={d['ours']!r} ref={d['ref']!r}" for d in divs[:25]]
        pytest.fail(f"{pair['alias']}/{side}: {len(divs)} unexplained divergences\n" + "\n".join(lines))


def test_divergences_unit():
    assert divergences([{"text": "a"}], [{"text": "a"}], ["text"]) == []
    assert divergences([{"text": "a"}], [{"text": "b"}], ["text"]) == [{"i": 0, "field": "text", "ours": "a", "ref": "b"}]
    assert divergences([], [{"text": "a"}], ["text"])[0]["field"] == "count"
    assert divergences([{"indLeftPt": 36.0}], [{"indLeftPt": 36.04}], ["indLeftPt"]) == []
    assert allowed({"field": "marker"}, "x", [{"alias": "*", "field": "marker", "reason": "t"}])
    assert not allowed({"field": "text"}, "x", [])


def test_no_pairs_means_corpus_not_built():
    assert pairs(), "run: uv run python harness/build_corpus.py && node harness/oracle_export.mjs"


def test_missing_oracle_fails_rather_than_skips(tmp_path, monkeypatch):
    monkeypatch.setitem(globals(), "ORACLE", tmp_path)
    with pytest.raises(AssertionError, match="oracle_export"):
        test_extraction_parity({"alias": "absent", "a": "a.docx", "b": "b.docx"}, "a")
