"""OOXML namespace constants and small attribute helpers."""
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_RELS = "http://schemas.openxmlformats.org/package/2006/relationships"


def wq(tag: str) -> str:
    return f"{{{W}}}{tag}"


def wval(el, default=None):
    if el is None:
        return default
    v = el.get(wq("val"))
    return default if v is None else v


def wbool(el) -> bool:
    """A toggle property element: present means on unless w:val says off."""
    if el is None:
        return False
    v = el.get(wq("val"))
    return v is None or v not in ("0", "false", "off")


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def twips_to_pt(s):
    n = _num(s)
    return None if n is None else n / 20.0


def half_pt(s):
    n = _num(s)
    return None if n is None else n / 2.0
