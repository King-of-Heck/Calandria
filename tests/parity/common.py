"""Shared pieces of the parity gates: corpus/oracle paths, manifests, divergence lists, allow policy."""
import functools
import hashlib
import json
import math
from pathlib import Path

from calandria.docx.parser import parse_docx

HERE = Path(__file__).resolve().parent
CORPUS = HERE.parent / "corpus"
ORACLE = HERE.parent / "oracle"


def load_allow(name: str, directory: Path | None = None) -> list:
    entries = json.loads(((directory or HERE) / name).read_text("utf8"))
    for entry in entries:
        assert {"alias", "field", "reason"} <= entry.keys(), (
            f"allow entry missing a required key (alias/field/reason): {entry!r}")
        assert entry["alias"] != "*", f"allow entry uses a wildcard alias, silencing every pair: {entry!r}"
        assert entry["field"] != "count", (
            f"allow entry targets the count field, silencing a whole pair: {entry!r}")
    return entries


def pairs() -> list[dict]:
    out = []
    for name in ("manifest.json", "manifest.gen.json"):
        m = CORPUS / name
        if m.exists():
            out.extend(json.loads(m.read_text("utf8"))["pairs"])
    return out


def _eq(a, b):
    if isinstance(a, float) or isinstance(b, float):
        if a is None or b is None:
            return a == b
        return math.isclose(float(a), float(b), abs_tol=0.05)
    return a == b


def divergences(ours, ref, fields):
    if len(ours) != len(ref):
        return [{"i": min(len(ours), len(ref)), "field": "count", "ours": len(ours), "ref": len(ref)}]
    out = []
    for i, (o, r) in enumerate(zip(ours, ref)):
        for f in fields:
            if not _eq(o.get(f), r.get(f)):
                out.append({"i": i, "field": f, "ours": o.get(f), "ref": r.get(f)})
    return out


def allowed(div, alias, allow):
    return any(a["field"] == div["field"] and a["alias"] in ("*", alias) for a in allow)


@functools.lru_cache(maxsize=None)
def parse_cached(path: Path):
    return parse_docx(path)


def page_digest(lay) -> str:
    """A stable fingerprint of a whole page model: page counts alone cannot see a line that moved.
    Written into golden-pages.json by harness/golden_pages.py and checked by test_pages.py, so both
    sides must compute it the same way -- hence one definition here."""
    blob = json.dumps(lay.to_dict(), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()[:16]
