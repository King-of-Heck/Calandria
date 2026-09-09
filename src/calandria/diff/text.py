"""Tokenizer, normalization and similarity for the paragraph and inline diffs.

The word class is ASCII on purpose: the reference engine's regexes use JavaScript's \\w and \\d,
which are ASCII-only, and the change-list gate compares tokens through the rendered rows. Numbers
with internal , . - / : stay one token so money and dates replace as a whole.
"""
from __future__ import annotations

import re

from ..model import WS_CHARS
from .lcs import lcs_ops

_TOKEN = re.compile(rf"[0-9][0-9,.\-/:]*[0-9]|[A-Za-z0-9_]+|[^A-Za-z0-9_{WS_CHARS}]|[{WS_CHARS}]+")
_WORD = re.compile(r"[A-Za-z0-9_]+")
_WS = re.compile(f"[{WS_CHARS}]+")


def tokenize(t: str) -> list[str]:
    return _TOKEN.findall(t or "")


def words_only(t: str) -> list[str]:
    return _WORD.findall((t or "").lower())


def content_tokens(t: str) -> list[str]:
    return [x for x in tokenize(t) if not _WS.fullmatch(x)]


def norm(t: str, ignore_case: bool = False) -> str:
    t = _WS.sub(" ", t or "").strip()
    return t.lower() if ignore_case else t


def sim(a: str, b: str) -> float:
    ta, tb = content_tokens(a), content_tokens(b)
    if not ta and not tb:
        return 1.0
    c = sum(1 for tag, _i, _j in lcs_ops(ta, tb) if tag == "equal")
    return (2 * c) / (len(ta) + len(tb))


def sim_upper(ta: list[str], tb: list[str]) -> float:
    """Cheap upper bound on sim(): the multiset intersection and the length ratio both bound
    the LCS, so a pair that cannot reach a threshold is skipped without the full DP."""
    la, lb = len(ta), len(tb)
    if not la and not lb:
        return 1.0
    if not la or not lb:
        return 0.0
    ratio = (2 * min(la, lb)) / (la + lb)
    counts: dict[str, int] = {}
    for w in ta:
        counts[w] = counts.get(w, 0) + 1
    inter = 0
    for w in tb:
        k = counts.get(w, 0)
        if k > 0:
            inter += 1
            counts[w] = k - 1
    return min(ratio, (2 * inter) / (la + lb))


def categorize(o: str, n: str) -> str:
    wa, wb = " ".join(words_only(o)), " ".join(words_only(n))
    return "punctuation" if wa == wb and o != n else "content"
