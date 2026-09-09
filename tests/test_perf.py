"""The performance bar (spec §3.6): a 100-page pair compares in under 30 s on the work laptop.
Here: a 3000-paragraph pair with five scattered edits, parse included, must stay well under it."""
import io
import time

from calandria.diff.compare import compare
from calandria.docx.parser import parse_docx
from calandria.testing.makedocx import DOC, P, make_docx

_WORDS = "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor".split()


def _para(i, swap=None):
    words = [_WORDS[(i + k) % len(_WORDS)] for k in range(40)]
    if swap:
        words = [swap if w == "dolor" else w for w in words]
    return P(f"Clause {i}. " + " ".join(words))


def test_three_thousand_paragraph_pair_under_budget():
    edits = {5, 900, 1500, 2200, 2990}
    a = "".join(_para(i) for i in range(3000))
    b = "".join(_para(i, "colour" if i in edits else None) for i in range(3000))
    t0 = time.perf_counter()
    c = compare(parse_docx(io.BytesIO(make_docx({"word/document.xml": DOC(a)}))),
                parse_docx(io.BytesIO(make_docx({"word/document.xml": DOC(b)}))))
    elapsed = time.perf_counter() - t0
    assert c.summary["amendments"] == 5 and c.summary["total"] == 5
    assert elapsed < 20, f"{elapsed:.1f}s"
