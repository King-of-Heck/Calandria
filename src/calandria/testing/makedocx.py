"""In-memory .docx builder for tests (STORED zip entries, no compression)."""
import io
import zipfile
from xml.sax.saxutils import escape

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def make_docx(parts: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as z:
        for name, text in parts.items():
            z.writestr(name, text.encode("utf8"))
    return buf.getvalue()


def DOC(body: str) -> str:
    return f'<w:document xmlns:w="{W_NS}"><w:body>{body}</w:body></w:document>'


def P(text: str, ppr: str = "", rpr: str = "") -> str:
    p = f"<w:pPr>{ppr}</w:pPr>" if ppr else ""
    r = f"<w:rPr>{rpr}</w:rPr>" if rpr else ""
    return (f"<w:p>{p}<w:r>{r}<w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r></w:p>")
