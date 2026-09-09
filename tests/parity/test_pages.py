"""Golden page-count gate: the layout of every corpus pair (each side alone and the redline)
must reproduce the page counts in golden-pages.json. Page counts are never compared with the
reference engine (its DOM/PDF pagination is not the model); the golden file pins OUR pagination
so that a change to it is deliberate: regenerate with `uv run python harness/golden_pages.py`,
review the diff, commit it with the change that caused it."""
import json

import pytest

from calandria.diff.compare import compare
from calandria.layout.engine import layout, layout_document

from .common import CORPUS, HERE, pairs, parse_cached

GOLDEN = HERE / "golden-pages.json"


def _golden() -> dict:
    assert GOLDEN.exists(), "tests/parity/golden-pages.json is missing: run `uv run python harness/golden_pages.py`"
    return json.loads(GOLDEN.read_text("utf8"))


def counts(pair: dict) -> dict:
    a, b = parse_cached(CORPUS / pair["a"]), parse_cached(CORPUS / pair["b"])
    return {"a": layout_document(a).page_count, "b": layout_document(b).page_count,
            "redline": layout(compare(a, b)).page_count}


@pytest.mark.parametrize("pair", pairs(), ids=lambda p: p["alias"])
def test_page_counts_match_golden(pair):
    golden = _golden()
    assert pair["alias"] in golden, f"{pair['alias']} is not in golden-pages.json: regenerate it"
    assert counts(pair) == golden[pair["alias"]], pair["alias"]


@pytest.mark.parametrize("pair", pairs(), ids=lambda p: p["alias"])
def test_redline_has_at_least_as_many_pages_as_the_revised_document(pair):
    c = counts(pair)
    assert c["redline"] >= c["b"], c
