"""A PDF font's /BaseFont name -> the family, bold and italic it names."""
from __future__ import annotations

import re

_SUBSET = re.compile(r"^[A-Z]{6}\+")
_STYLE_TAIL = re.compile(r"^(.+?)(BoldItalic|BoldOblique|Bold|Italic|Oblique)$")
_WORDS = re.compile(r"[A-Z][a-z]+|[A-Z]+(?![a-z])|[a-z]+|\d+")
_STYLE_WORDS = {"bold", "italic", "oblique", "regular", "roman", "mt", "ps", "psmt"}
_CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z])")


def split_font(name: str) -> tuple[str, bool, bool]:
    """'ABCDEF+TimesNewRomanPS-BoldItalicMT' -> ('Times New Roman', True, True)."""
    base = _SUBSET.sub("", name)
    head, tail = (re.split(r"[,-]", base, maxsplit=1) + [""])[:2]
    head = re.sub(r"(PSMT|PS|MT)$", "", head)
    m = _STYLE_TAIL.match(head)
    if m:
        head, tail = m.group(1), m.group(2) + tail
    words = _WORDS.findall(tail)                     # 'BoldItalicMT' -> Bold, Italic, MT; 'Semibold' stays one word
    low = [w.lower() for w in words]
    bold, italic = "bold" in low, "italic" in low or "oblique" in low
    rest = [w for w in words if w.lower() not in _STYLE_WORDS]
    family = " ".join([_CAMEL.sub(" ", head.replace("_", " ")).strip(), *rest]).strip()
    return family or "Unknown", bold, italic
