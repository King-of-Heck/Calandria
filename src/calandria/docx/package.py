"""Zip container access for a .docx and its relationship parts."""
from __future__ import annotations

import io
import posixpath
import zipfile
from lxml import etree

from .ns import PKG_RELS


class Package:
    def __init__(self, zf: zipfile.ZipFile):
        self._zf = zf
        self._names = set(zf.namelist())

    @classmethod
    def open(cls, src) -> "Package":
        if isinstance(src, (bytes, bytearray)):
            src = io.BytesIO(src)
        return cls(zipfile.ZipFile(src))

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
        return etree.fromstring(data, parser=etree.XMLParser(huge_tree=True, recover=True))

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
