"""Guardrail: an allow entry can never silence a whole pair (count) or every pair (wildcard alias)."""
import json

import pytest

from .common import load_allow


def _write(tmp_path, entries):
    (tmp_path / "allow.json").write_text(json.dumps(entries), encoding="utf8")


def test_load_allow_rejects_wildcard_alias(tmp_path):
    _write(tmp_path, [{"alias": "*", "field": "indLeftPt", "reason": "x"}])
    with pytest.raises(AssertionError):
        load_allow("allow.json", directory=tmp_path)


def test_load_allow_rejects_count_field(tmp_path):
    _write(tmp_path, [{"alias": "spacing", "field": "count", "reason": "x"}])
    with pytest.raises(AssertionError):
        load_allow("allow.json", directory=tmp_path)


def test_load_allow_accepts_a_well_formed_entry(tmp_path):
    _write(tmp_path, [{"alias": "spacing", "field": "indLeftPt", "reason": "KNOWN_DIVERGENCES (d)"}])
    assert load_allow("allow.json", directory=tmp_path) == [
        {"alias": "spacing", "field": "indLeftPt", "reason": "KNOWN_DIVERGENCES (d)"}]
