"""Zip container access for a .docx and its relationship parts."""
from __future__ import annotations

import io
import posixpath
import re
import zipfile
from lxml import etree

from .ns import PKG_RELS, W

_XMLNS_W = f' xmlns:w="{W}"'.encode("ascii")
_ROOT_TAG = re.compile(rb"<w:[A-Za-z][\w.-]*")


def _ensure_w_namespace(data: bytes) -> bytes:
    """Some producers (incl. SorkWhare's own synthetic test fixtures) emit WordprocessingML
    parts that use the `w:` prefix on every element but never bind it via `xmlns:w=...` on
    the root. That is not valid XML a real Word install would ever write, but the reference
    engine's regex-based reader does not care -- it never resolves namespaces at all. Calandria
    parses with a proper namespace-aware XML library, so an unbound prefix means every lookup
    silently finds nothing (0 paragraphs). Inject the binding onto the root element when it is
    missing; real, correctly-namespaced parts (xmlns:w already present) are returned untouched.
    """
    if b"xmlns:w=" in data or b"xmlns:w =" in data:
        return data
    m = _ROOT_TAG.search(data)
    if m is None:
        return data
    end = m.end()
    return data[:end] + _XMLNS_W + data[end:]


class Package:
    def __init__(self, zf: zipfile.ZipFile):
        self._zf = zf
        self._names = set(zf.namelist())

    @classmethod
    def open(cls, src) -> "Package":
        if isinstance(src, (bytes, bytearray)):
            src = io.BytesIO(src)
        return cls(zipfile.ZipFile(src))

    def close(self) -> None:
        """Release the zip (and, for a path or file input, the underlying file handle)."""
        self._zf.close()

    def __enter__(self) -> "Package":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def has(self, name: str) -> bool:
        return name in self._names

    def part(self, name: str):
        if name not in self._names:
            return None
        return self._zf.read(name)

    def xml(self, name: str):
        data = self.part(name)
        if data is None:
            return None
        return etree.fromstring(_ensure_w_namespace(data), parser=etree.XMLParser(huge_tree=True, recover=True))

    def rels(self, part_name: str) -> dict[str, str]:
        d, f = posixpath.split(part_name)
        root = self.xml(posixpath.join(d, "_rels", f + ".rels"))
        if root is None:
            return {}
        out = {}
        for rel in root.iter(f"{{{PKG_RELS}}}Relationship"):
            rid, target = rel.get("Id"), rel.get("Target")
            if not rid or not target:
                continue
            out[rid] = posixpath.basename(target)
        return out
