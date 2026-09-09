"""Gate: Calandria's change list matches SorkWhare 1.16.0's compare() rows and summary on the
corpus, in the v2.0.0 scope (no moves, no split/merge), at both ignore-case settings."""
import json

import pytest

from calandria.diff.compare import compare
from calandria.harness.changes import records

from .common import CORPUS, ORACLE, allowed, divergences, load_allow, pairs, parse_cached

ALLOW = load_allow("allow-changes.json")
FIELDS = ["type", "cid", "cat", "oi", "ni", "html", "numChanged", "oldMarker", "fmtChanged", "fmtDescs", "tbl"]
VARIANTS = {"compare_v2": {"ignore_case": False}, "compare_v2_ic": {"ignore_case": True}}


def _first_mismatch(ours, ref):
    for i, (o, r) in enumerate(zip(ours, ref)):
        if (o["type"], o["html"]) != (r["type"], r["html"]):
            return f"first row mismatch at [{i}]: ours=({o['type']!r}, {o['html']!r}) ref=({r['type']!r}, {r['html']!r})"
    return "rows agree up to the shorter list"


@pytest.mark.parametrize("pair", pairs(), ids=lambda p: p["alias"])
@pytest.mark.parametrize("variant", list(VARIANTS))
def test_change_list_parity(pair, variant):
    oracle_file = ORACLE / f"{pair['alias']}.json"
    assert oracle_file.exists(), "run: node harness/oracle_export.mjs"
    oracle = json.loads(oracle_file.read_text("utf8"))
    assert variant in oracle, "stale oracle: run node harness/oracle_export.mjs"
    ref = oracle[variant]
    cmp = compare(parse_cached(CORPUS / pair["a"]), parse_cached(CORPUS / pair["b"]), **VARIANTS[variant])
    ours = records(cmp)
    if ref["rows"]:
        assert all(f in ref["rows"][0] for f in FIELDS), "stale oracle: run node harness/oracle_export.mjs"
    divs = [d for d in divergences(ours, ref["rows"], FIELDS) if not allowed(d, pair["alias"], ALLOW)]
    problems = []
    if divs:
        problems.append(f"{len(divs)} unexplained row divergences")
        if divs[0]["field"] == "count":
            problems.append(_first_mismatch(ours, ref["rows"]))
        problems += [f"[{d['i']}] {d['field']}: ours={d['ours']!r} ref={d['ref']!r}" for d in divs[:25]]
    if cmp.summary != ref["summary"]:
        problems.append(f"summary ours={cmp.summary} ref={ref['summary']}")
    if problems:
        pytest.fail(f"{pair['alias']}/{variant}:\n" + "\n".join(problems))


def test_missing_variant_fails_rather_than_skips(tmp_path, monkeypatch):
    (tmp_path / "x.json").write_text(json.dumps({"A": {}, "B": {}, "compare": {}}), "utf8")
    monkeypatch.setitem(globals(), "ORACLE", tmp_path)
    with pytest.raises(AssertionError, match="stale oracle"):
        test_change_list_parity({"alias": "x", "a": "a.docx", "b": "b.docx"}, "compare_v2")
