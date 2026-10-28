"""Small PDFs for the tests, written with fpdf2 (already a runtime dependency). Coordinates are
points from the page's top-left corner; a text item's y is its baseline."""
from __future__ import annotations

import io

from fpdf import FPDF


def make_pdf(pages, size=(612, 792), ttf=None, user_password=None, owner_password=None) -> bytes:
    pdf = FPDF(unit="pt", format=size)
    pdf.set_auto_page_break(False)
    pdf.set_margin(0)
    family = "Helvetica"
    if ttf is not None:
        pdf.add_font("T", "", ttf)
        pdf.add_font("T", "B", ttf)
        family = "T"
    if owner_password is not None or user_password is not None:
        pdf.set_encryption(owner_password=owner_password or "owner", user_password=user_password)
    pdf.set_line_width(0.5)
    for items in pages:
        pdf.add_page()
        for item in items:
            kind = item[0]
            if kind == "text":
                _, x, y, pt, string, *style = item
                pdf.set_font(family, style[0] if style else "", pt)
                pdf.text(x, y, string)
            elif kind == "line":
                pdf.line(*item[1:5])
            elif kind == "rect":
                pdf.rect(*item[1:5], style="D")
            elif kind == "fill":
                pdf.set_fill_color(0, 0, 0)
                pdf.rect(*item[1:5], style="F")
            elif kind == "image":
                from PIL import Image
                buf = io.BytesIO()
                Image.new("RGB", (8, 8), (200, 200, 200)).save(buf, "PNG")
                buf.seek(0)
                pdf.image(buf, item[1], item[2], item[3], item[4])
            else:
                raise ValueError(f"unknown item {kind!r}")
    return bytes(pdf.output())
