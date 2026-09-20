"""The PDF reader's judge: a corpus pair saved as PDF from Word must compare to the same changes
as the .docx pair it came from. Text and counts only, never geometry. A known difference is
written down in pdf-expected.json with its reason and its exact value, so a NEW difference fails.
Skips when the PDFs are not in the (git-ignored) corpus."""
import json

import pytest

from calandria.diff.compare import compare
from calandria.docx.parser import parse_docx
from calandria.model import collapse_ws
from calandria.pdfread import parse_pdf

from .common import CORPUS, HERE, pairs

FIELDS = ("insertions", "deletions", "ins_text", "del_text")
VARIANTS = {"save": ".pdf", "print": ".print.pdf"}
EXPECTED = json.loads((HERE / "pdf-expected.json").read_text("utf8"))


def signature(cmp) -> dict:
    texts = {"ins": [], "del": []}
    for row in cmp.rows:
        for seg in row.segments:
            if seg.m in texts:
                texts[seg.m].append(seg.t)
    return {"insertions": cmp.summary["insertions"], "deletions": cmp.summary["deletions"],
            "ins_text": collapse_ws(" ".join(texts["ins"])), "del_text": collapse_ws(" ".join(texts["del"]))}


def cases():
    out = []
    for pair in pairs():
        for variant, ext in VARIANTS.items():
            a = CORPUS / pair["a"].replace(".docx", ext)
            b = CORPUS / pair["b"].replace(".docx", ext)
            if a.exists() and b.exists():
                out.append(pytest.param(pair, variant, a, b, id=f"{pair['alias']}-{variant}"))
    return out


def test_the_expectations_file_is_well_formed():
    assert isinstance(EXPECTED, list)
    for e in EXPECTED:
        assert {"alias", "variant", "field", "reason", "pdf"} <= e.keys(), e
        assert e["field"] in FIELDS and e["variant"] in VARIANTS and e["reason"].strip(), e


@pytest.mark.skipif(not cases(), reason="no corpus PDFs present")
@pytest.mark.parametrize("pair, variant, a_pdf, b_pdf", cases())
def test_a_pdf_pair_compares_like_its_word_pair(pair, variant, a_pdf, b_pdf):
    word = signature(compare(parse_docx(CORPUS / pair["a"]), parse_docx(CORPUS / pair["b"])))
    pdf = signature(compare(parse_pdf(a_pdf.read_bytes()), parse_pdf(b_pdf.read_bytes())))
    known = {e["field"]: e for e in EXPECTED if e["alias"] == pair["alias"] and e["variant"] == variant}
    problems = []
    for f in FIELDS:
        if f in known:
            if pdf[f] != known[f]["pdf"]:
                problems.append(f"{f}: recorded {ascii(known[f]['pdf'])}, now {ascii(pdf[f])}")
        elif pdf[f] != word[f]:
            problems.append(f"{f}: word {ascii(word[f])}, pdf {ascii(pdf[f])}")
    assert not problems, "\n".join(problems)
