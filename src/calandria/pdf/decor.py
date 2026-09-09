"""Effects -> rule geometry. Offsets are fractions of the font size, below the baseline positive;
the single place that knows where an underline or a strike sits."""
from __future__ import annotations

UNDERLINE_Y, UNDERLINE_T = 0.11, 0.06
DOUBLE_UNDERLINE_Y, DOUBLE_T = (0.08, 0.20), 0.045
STRIKE_Y, STRIKE_T = -0.26, 0.06
DOUBLE_STRIKE_Y = (-0.31, -0.21)


def run_effects(style_effects, doc_underline: bool) -> frozenset:
    """The category's effects plus the document's own underline (a single one, unless the
    category already draws a double underline; it replaces a dotted one)."""
    eff = set(style_effects)
    if doc_underline and "double-underline" not in eff:
        eff.discard("dotted-underline")
        eff.add("underline")
    return frozenset(eff)


def decorations(effects, x1: float, x2: float, baseline: float, size: float) -> list[tuple]:
    """(x1, x2, y, thickness, dotted) for every rule the effects draw. bold / italic draw none."""
    out: list[tuple] = []
    if "underline" in effects:
        out.append((x1, x2, baseline + UNDERLINE_Y * size, UNDERLINE_T * size, False))
    elif "dotted-underline" in effects:
        out.append((x1, x2, baseline + UNDERLINE_Y * size, UNDERLINE_T * size, True))
    if "double-underline" in effects:
        for f in DOUBLE_UNDERLINE_Y:
            out.append((x1, x2, baseline + f * size, DOUBLE_T * size, False))
    if "strikethrough" in effects:
        out.append((x1, x2, baseline + STRIKE_Y * size, STRIKE_T * size, False))
    if "double-strikethrough" in effects:
        for f in DOUBLE_STRIKE_Y:
            out.append((x1, x2, baseline + f * size, DOUBLE_T * size, False))
    return out
