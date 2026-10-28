"""The hundred-page document pair the performance tests share: 1500 paragraphs of 40 words each,
with the word "dolor" swapped in four of them (near the start, twice in the middle, near the end)."""
from __future__ import annotations

from .makedocx import P

_WORDS = "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor".split()
PARAGRAPHS = 1500
EDITS = {5, 400, 900, 1400}


def _para(i: int, swap: str | None = None) -> str:
    words = [_WORDS[(i + k) % len(_WORDS)] for k in range(40)]
    if swap:
        words = [swap if w == "dolor" else w for w in words]
    return P(f"Clause {i}. " + " ".join(words))


def hundred_page_pair() -> tuple[str, str]:
    """The (original, modified) document bodies, ready to wrap in DOC()."""
    a = "".join(_para(i) for i in range(PARAGRAPHS))
    b = "".join(_para(i, "colour" if i in EDITS else None) for i in range(PARAGRAPHS))
    return a, b
