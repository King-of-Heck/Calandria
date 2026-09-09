"""Golden page-count gate: the layout of every corpus pair (each side alone and the redline)
must reproduce the page counts in golden-pages.json. Page counts are never compared with the
reference engine (its DOM/PDF pagination is not the model); the golden file pins OUR pagination
so that a change to it is deliberate: regenerate with `uv run python harness/golden_pages.py`,
review the diff, commit it with the change that caused it."""
import json
import os

import pytest

from calandria.diff.compare import compare
from calandria.layout.engine import layout, layout_document
from calandria.layout.fonts import default_dirs

from .common import CORPUS, HERE, page_digest, pairs, parse_cached

GOLDEN = HERE / "golden-pages.json"

# The golden numbers come from the metrics of the installed fonts: without a font directory there
# is nothing to reproduce them from.
pytestmark = pytest.mark.skipif(not any(os.path.isdir(d) for d in default_dirs()),
                                reason="no system font directory on this machine")

_CACHE: dict[str, dict] = {}


def _golden() -> dict:
    assert GOLDEN.exists(), "tests/parity/golden-pages.json is missing: run `uv run python harness/golden_pages.py`"
    return json.loads(GOLDEN.read_text("utf8"))


def counts(pair: dict) -> dict:
    """Page counts and the redline digest, computed once per pair."""
    alias = pair["alias"]
    if alias not in _CACHE:
        a, b = parse_cached(CORPUS / pair["a"]), parse_cached(CORPUS / pair["b"])
        red = layout(compare(a, b))
        _CACHE[alias] = {"a": layout_document(a).page_count, "b": layout_document(b).page_count,
                         "redline": red.page_count, "digest": page_digest(red)}
    return _CACHE[alias]


def _entry(pair: dict) -> dict:
    golden = _golden()
    assert pair["alias"] in golden, f"{pair['alias']} is not in golden-pages.json: regenerate it"
    return golden[pair["alias"]]


@pytest.mark.parametrize("pair", pairs(), ids=lambda p: p["alias"])
def test_page_counts_match_golden(pair):
    golden = _entry(pair)
    ours = counts(pair)
    assert {k: ours[k] for k in ("a", "b", "redline")} == {k: golden[k] for k in ("a", "b", "redline")},         pair["alias"]


@pytest.mark.parametrize("pair", pairs(), ids=lambda p: p["alias"])
def test_redline_layout_digest_matches_golden(pair):
    # A count failure says "the document got longer"; this one says "something moved on the page".
    assert counts(pair)["digest"] == _entry(pair)["digest"], (
        f"{pair['alias']}: the redline page model changed; review and regenerate golden-pages.json")


@pytest.mark.parametrize("pair", pairs(), ids=lambda p: p["alias"])
def test_redline_has_at_least_as_many_pages_as_the_revised_document(pair):
    c = counts(pair)
    assert c["redline"] >= c["b"], c
