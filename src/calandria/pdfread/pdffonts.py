"""A PDF font resource as the reader needs it: the bytes of a shown string -> characters and
their widths. It takes pypdf's dictionary objects but imports nothing from pypdf: they behave as
dict / list / str / int, and anything with get_object() is an indirect reference."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from fontTools.agl import toUnicode

REPLACEMENT = "�"
_HEX = re.compile(rb"<([0-9A-Fa-f\s]*)>")
_BFCHAR = re.compile(rb"beginbfchar(.*?)endbfchar", re.S)
_BFRANGE = re.compile(rb"beginbfrange(.*?)endbfrange", re.S)
_RANGE_ITEM = re.compile(rb"<([0-9A-Fa-f\s]+)>\s*<([0-9A-Fa-f\s]+)>\s*(\[[^\]]*\]|<[0-9A-Fa-f\s]*>)", re.S)
_BASE = {"/WinAnsiEncoding": "cp1252", "/MacRomanEncoding": "mac_roman"}


def _obj(x):
    return x.get_object() if hasattr(x, "get_object") else x


def _hex(b: bytes) -> bytes:
    digits = re.sub(rb"\s", b"", b).decode("ascii")
    return bytes.fromhex(digits if len(digits) % 2 == 0 else digits + "0")


def _u16(b: bytes) -> str:
    try:
        return b.decode("utf-16-be")
    except UnicodeDecodeError:
        return REPLACEMENT


def parse_tounicode(data: bytes) -> tuple[dict[int, str], int]:
    """(code -> text, bytes per code) of a ToUnicode CMap. Bytes per code comes from the width of
    the source codes; 0 when the map has no entries."""
    out: dict[int, str] = {}
    nbytes = 0
    for block in _BFCHAR.findall(data):
        toks = _HEX.findall(block)
        for src, dst in zip(toks[0::2], toks[1::2]):
            s = _hex(src)
            nbytes = max(nbytes, len(s))
            out[int.from_bytes(s, "big")] = _u16(_hex(dst))
    for block in _BFRANGE.findall(data):
        for lo, hi, dst in _RANGE_ITEM.findall(block):
            lo_b = _hex(lo)
            nbytes = max(nbytes, len(lo_b))
            a, z = int.from_bytes(lo_b, "big"), int.from_bytes(_hex(hi), "big")
            if z < a or z - a > 0xFFFF:
                continue
            if dst.startswith(b"["):
                for i, d in enumerate(_HEX.findall(dst)):
                    if a + i <= z:
                        out[a + i] = _u16(_hex(d))
            else:
                base = _u16(_hex(_HEX.match(dst).group(1)))
                if not base:
                    continue
                for i in range(z - a + 1):
                    out[a + i] = base[:-1] + chr(min(ord(base[-1]) + i, 0x10FFFF))
    return out, nbytes


@dataclass
class PdfFont:
    name: str
    nbytes: int = 1
    to_unicode: dict[int, str] = field(default_factory=dict)
    widths: dict[int, float] = field(default_factory=dict)
    default_width: float = 500.0
    codec: str | None = "cp1252"          # a one-byte font's base encoding, for codes ToUnicode lacks
    differences: dict[int, str] = field(default_factory=dict)

    def decode(self, raw: bytes) -> list[tuple[int, str, float]]:
        n = self.nbytes
        out = []
        for i in range(0, len(raw) - n + 1, n):
            code = int.from_bytes(raw[i:i + n], "big")
            out.append((code, self._text(code), self.widths.get(code, self.default_width)))
        return out

    def _text(self, code: int) -> str:
        t = self.to_unicode.get(code)
        if t is not None:
            return t
        if self.nbytes != 1:
            return REPLACEMENT
        if code in self.differences:
            return self.differences[code]
        if self.codec and code >= 32:
            try:
                return bytes([code]).decode(self.codec)
            except UnicodeDecodeError:
                pass
        return REPLACEMENT


def _cid_widths(w) -> dict[int, float]:
    out: dict[int, float] = {}
    w = [_obj(x) for x in w]
    i = 0
    while i < len(w):
        first = int(w[i])
        if i + 1 < len(w) and isinstance(w[i + 1], list):
            for k, x in enumerate(w[i + 1]):
                out[first + k] = float(_obj(x))
            i += 2
        elif i + 2 < len(w):
            last = min(int(w[i + 1]), first + 0xFFFF)
            for c in range(first, last + 1):
                out[c] = float(w[i + 2])
            i += 3
        else:
            break
    return out


def load_font(res) -> PdfFont:
    """Never raises: a resource it cannot read gives a font that decodes to replacements (Type0)
    or through cp1252 (the rest), so one odd font cannot sink the document."""
    res = _obj(res)
    font = PdfFont(str(res.get("/BaseFont", "/Unknown")).lstrip("/"))
    type0 = str(res.get("/Subtype")) == "/Type0"
    if type0:
        font.nbytes, font.codec, font.default_width = 2, None, 1000.0
    try:
        tu = res.get("/ToUnicode")
        if tu is not None:
            font.to_unicode, _n = parse_tounicode(_obj(tu).get_data())
        if type0:
            desc = _obj(_obj(res["/DescendantFonts"])[0])
            font.default_width = float(desc.get("/DW", 1000))
            font.widths = _cid_widths(_obj(desc.get("/W", [])))
        else:
            first = int(res.get("/FirstChar", 0))
            for i, w in enumerate(_obj(res.get("/Widths", []))):
                font.widths[first + i] = float(_obj(w))
            fd = _obj(res.get("/FontDescriptor")) if res.get("/FontDescriptor") is not None else {}
            if "/MissingWidth" in fd:
                font.default_width = float(fd["/MissingWidth"])
            enc = _obj(res.get("/Encoding")) if res.get("/Encoding") is not None else None
            if isinstance(enc, str):
                font.codec = _BASE.get(str(enc), "cp1252")
            elif enc is not None:
                font.codec = _BASE.get(str(enc.get("/BaseEncoding")), "cp1252")
                code = 0
                for item in _obj(enc.get("/Differences", [])):
                    item = _obj(item)
                    if isinstance(item, str):
                        text = toUnicode(item.lstrip("/"))
                        if text:
                            font.differences[code] = text
                        code += 1
                    else:
                        code = int(item)
    except Exception:
        pass
    return font
