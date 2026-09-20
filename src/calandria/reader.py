"""One seam for reading a source file: the reader is picked from the file's first bytes, never
from its name. Both readers return the same Document. The PDF reader is imported on first use."""
from __future__ import annotations

from .model import Document


class UnknownKind(ValueError):
    """Neither a Word document nor a PDF."""


def kind_of(data: bytes) -> str | None:
    if b"%PDF-" in data[:1024]:            # the header may follow a few stray bytes
        return "pdf"
    if data[:4] == b"PK\x03\x04":
        return "docx"
    return None


def read_document(data: bytes, progress=None) -> Document:
    kind = kind_of(data)
    if kind == "pdf":
        from .pdfread import parse_pdf
        return parse_pdf(data, progress)
    if kind == "docx":
        from .docx.parser import parse_docx
        return parse_docx(data)
    raise UnknownKind("not a Word document or a PDF")
