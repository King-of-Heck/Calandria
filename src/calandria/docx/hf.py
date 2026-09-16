"""Which header and footer Word shows on a page, and the "as displayed" streams the diff runs
over.

Word links every variant (default / first / even) of every kind (header / footer) to the previous
section on its own when the section names no part for it; the first section with none shows
nothing. The first-page variant shows only on the first page of a section with a title page, the
even variant only on even pages when the document uses even and odd headers; every other page
shows the default. The displayed stream of a kind is what a reader turns the pages and sees: the
distinct non-blank contents, in document order, each once.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..model import Document, Section, iter_paragraphs

KINDS = ("header", "footer")
VARIANTS = ("default", "first", "even")


@dataclass(frozen=True)
class SectionHf:
    header: dict          # variant -> part name (resolved through the previous sections) or None
    footer: dict

    def part(self, kind: str, variant: str) -> str | None:
        return (self.header if kind == "header" else self.footer)[variant]


def resolve(doc: Document) -> list[SectionHf]:
    prev = {k: {v: None for v in VARIANTS} for k in KINDS}
    out: list[SectionHf] = []
    for sec in doc.sections:
        cur = {}
        for kind in KINDS:
            cur[kind] = {}
            for v in VARIANTS:
                own = getattr(sec, f"{kind}_{v}")
                cur[kind][v] = own if own is not None else prev[kind][v]
        out.append(SectionHf(cur["header"], cur["footer"]))
        prev = cur
    return out


def variant_for(sec: Section, doc: Document, first_page: bool, page_number: int) -> str:
    if first_page and sec.title_pg:
        return "first"
    if doc.even_and_odd and page_number % 2 == 0:
        return "even"
    return "default"


def shown_variants(sec: Section, doc: Document) -> list[str]:
    """The variants a section can show, in the order a reader meets them."""
    out = ["first"] if sec.title_pg else []
    out.append("default")
    if doc.even_and_odd:
        out.append("even")
    return out


def _has_content(p) -> bool:
    return not p.is_empty or any(r.props.field is not None or r.props.image_w_pt for r in p.runs)


def is_blank(blocks: list) -> bool:
    return not any(_has_content(p) for p in iter_paragraphs(blocks))


def _content_key(blocks: list) -> tuple:
    """The content two parts must share to be one displayed entry: each paragraph's text and the
    boxes of its inline images (an image-only paragraph has no text, so its logo's size is all
    that tells two such parts apart)."""
    return tuple((p.text, tuple((r.props.image_w_pt, r.props.image_h_pt)
                                for r in p.runs if r.props.image_w_pt))
                 for p in iter_paragraphs(blocks) if _has_content(p))


def displayed(doc: Document, kind: str) -> tuple[list[tuple[str, list]], dict[str, str | None]]:
    """(entries, alias): entries = (part name, blocks) per distinct displayed content in document
    order; alias = every resolved part name of the kind -> the entry name carrying its content, or
    None when the part is blank (an image-only paragraph counts as content: it is not blank, and it
    keys by its image boxes)."""
    entries: list[tuple[str, list]] = []
    alias: dict[str, str | None] = {}
    by_key: dict[tuple, str] = {}
    for sec, sh in zip(doc.sections, resolve(doc)):
        for v in shown_variants(sec, doc):
            name = sh.part(kind, v)
            if name is None or name in alias:
                continue
            blocks = doc.parts.get(name, [])
            if is_blank(blocks):
                alias[name] = None
                continue
            key = _content_key(blocks)
            if key not in by_key:
                by_key[key] = name
                entries.append((name, blocks))
            alias[name] = by_key[key]
    # parts a section names for a variant it never shows are aliases too (the layout may ask)
    for sec, sh in zip(doc.sections, resolve(doc)):
        for v in VARIANTS:
            name = sh.part(kind, v)
            if name is not None and name not in alias:
                alias[name] = None
    return entries, alias


def page_number(sec: Section, index_in_section: int, prev: int) -> int:
    """The Word page number of the index_in_section-th page of `sec`, `prev` being the number of the
    page before it (0 before the first page)."""
    if index_in_section == 0 and sec.page_start is not None:
        return sec.page_start
    return prev + 1


_ROMAN = ((1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"), (50, "l"), (40, "xl"),
          (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i"))


def _roman(n: int) -> str:
    out = ""
    for v, s in _ROMAN:
        while n >= v:
            out += s
            n -= v
    return out


def _letters(n: int) -> str:
    # Word: a..z, then aa..zz (the same letter repeated), so 27 -> "aa"
    return chr(ord("a") + (n - 1) % 26) * ((n - 1) // 26 + 1)


def format_number(n: int, fmt: str) -> str:
    if n <= 0 or fmt in (None, "decimal"):
        return str(n)
    if fmt == "lowerRoman":
        return _roman(n)
    if fmt == "upperRoman":
        return _roman(n).upper()
    if fmt == "lowerLetter":
        return _letters(n)
    if fmt == "upperLetter":
        return _letters(n).upper()
    return str(n)
