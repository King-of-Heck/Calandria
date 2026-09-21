"""The PDF reader's judge: a corpus pair saved as PDF from Word must compare to the same changes
as the .docx pair it came from. Text and counts only, never geometry. A known difference is
written down in pdf-expected.json with its reason, so a NEW difference fails: a count by its
value, a text by the sha256 of its text, because the corpus is git-ignored to keep its text out
of a public repo and this file is tracked. Skips when the PDFs are not in the corpus."""
import hashlib
import json
from collections import Counter

import pytest

from calandria.diff.compare import compare
from calandria.docx.parser import parse_docx
from calandria.model import collapse_ws
from calandria.pdfread import parse_pdf

from .common import CORPUS, HERE, pairs

FIELDS = ("insertions", "deletions", "ins_text", "del_text")
TEXT_FIELDS = ("ins_text", "del_text")
VARIANTS = {"save": ".pdf", "print": ".print.pdf"}
EXPECTED = json.loads((HERE / "pdf-expected.json").read_text("utf8"))
PARA_COUNTS = json.loads((HERE / "pdf-paragraphs.json").read_text("utf8"))


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf8")).hexdigest()


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
        assert {"alias", "variant", "field", "reason"} <= e.keys(), e
        assert e["field"] in FIELDS and e["variant"] in VARIANTS and e["reason"].strip(), e
        assert e["alias"] != "real1", e          # the confidential pair is never written down here
        if e["field"] in TEXT_FIELDS:            # a text goes in by its hash, never by its content
            assert e.keys() <= {"alias", "variant", "field", "reason", "pdf_sha256", "kind"}, e
            assert "pdf_sha256" in e, e
            assert isinstance(e["pdf_sha256"], str) and len(e["pdf_sha256"]) == 64, e
            assert e.get("kind", "subset-of-word") == "subset-of-word", e
        else:
            assert e.keys() <= {"alias", "variant", "field", "reason", "pdf"}, e
            assert "pdf" in e, e
            assert isinstance(e["pdf"], int), e


@pytest.mark.skipif(not cases(), reason="no corpus PDFs present")
@pytest.mark.parametrize("pair, variant, a_pdf, b_pdf", cases())
def test_a_pdf_pair_compares_like_its_word_pair(pair, variant, a_pdf, b_pdf):
    word = signature(compare(parse_docx(CORPUS / pair["a"]), parse_docx(CORPUS / pair["b"])))
    pdf = signature(compare(parse_pdf(a_pdf.read_bytes()), parse_pdf(b_pdf.read_bytes())))
    known = {e["field"]: e for e in EXPECTED if e["alias"] == pair["alias"] and e["variant"] == variant}
    problems = []
    for f in FIELDS:
        e = known.get(f)
        if e is None:
            if pdf[f] != word[f]:
                if f in TEXT_FIELDS:            # no recorded entry: never print the text itself
                    problems.append(f"{f}: no recorded entry; word sha256 {sha(word[f])} len {len(word[f])}, "
                                     f"pdf sha256 {sha(pdf[f])} len {len(pdf[f])}")
                else:
                    problems.append(f"{f}: word {ascii(word[f])}, pdf {ascii(pdf[f])}")
        elif f not in TEXT_FIELDS:
            if pdf[f] != e["pdf"]:
                problems.append(f"{f}: recorded {ascii(e['pdf'])}, now {ascii(pdf[f])}")
        else:
            if sha(pdf[f]) != e["pdf_sha256"]:
                problems.append(f"{f}: recorded sha256 {e['pdf_sha256']}, now {ascii(pdf[f])}")
            # A difference whose only cause is text the PDF never sees can add nothing of its own.
            if e.get("kind") == "subset-of-word" and not Counter(pdf[f].split()) <= Counter(word[f].split()):
                problems.append(f"{f}: not a sub-multiset of the Word text, now {ascii(pdf[f])}")
    assert not problems, "\n".join(problems)


def corpus_pdfs() -> list:
    return sorted(CORPUS.glob("*.pdf")) if CORPUS.exists() else []


@pytest.mark.skipif(not corpus_pdfs(), reason="no corpus PDFs present")
@pytest.mark.parametrize("pdf_path", corpus_pdfs(), ids=lambda p: p.name)
def test_a_corpus_pdf_keeps_its_recorded_paragraph_count(pdf_path):
    """A text-free guard on paragraph structure: the four compared fields (insertions, deletions,
    ins_text, del_text) cannot see a paragraph rule that collapses a whole document into one
    paragraph, since a change list can end up identical either way. This counts paragraphs alone,
    against a number pinned in pdf-paragraphs.json -- no document text, just a filename and an
    integer, so it can stay in a public repo."""
    count = len(list(parse_pdf(pdf_path.read_bytes()).paragraphs()))
    assert pdf_path.name in PARA_COUNTS, (
        f"no recorded paragraph count for {pdf_path.name} (it parses to {count} now)")
    assert count == PARA_COUNTS[pdf_path.name]
