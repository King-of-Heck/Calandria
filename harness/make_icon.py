"""Write Calandria.ico from the favicon embedded in the viewer page.

The page's `<link rel="icon">` data URI is the one drawing of the mark; this reads its geometry
back (a stroked triangle and filled bars) and rasterises it at every size a Windows icon wants,
supersampled so the edges are smooth. The tracked Calandria.ico must match this output
(tests/test_icon.py), so change the page and rerun this rather than editing the .ico.

    uv run python harness/make_icon.py
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path
from urllib.parse import unquote

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "src" / "calandria" / "viewer" / "index.html"
SIZES = (16, 24, 32, 48, 64, 128, 256)
BOX = 512            # the SVG viewBox is 0 0 512 512
OVERSAMPLE = 8


def favicon_svg(html: str) -> str:
    return unquote(re.search(r'href="data:image/svg\+xml,([^"]+)"', html).group(1))


def shapes(svg: str) -> dict:
    """The triangle's three points, its (stroke colour, width) and the [(x, y, w, h), fill] bars."""
    path = re.search(r'<path d="M(\d+) (\d+)L(\d+) (\d+)H(\d+)Z" fill="(#[0-9A-Fa-f]+)" '
                     r'stroke="(#[0-9A-Fa-f]+)" stroke-width="(\d+)"', svg)
    x0, y0, x1, y1, x2 = (int(v) for v in path.groups()[:5])
    rects = [((int(x), int(y), int(w), int(h)), fill) for x, y, w, h, fill in re.findall(
        r'<rect x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)" fill="(#[0-9A-Fa-f]+)"', svg)]
    return {"triangle": ((x0, y0), (x1, y1), (x2, y1)), "fill": path.group(6),
            "stroke": (path.group(7), int(path.group(8))), "rects": rects}


def render(s: dict, size: int) -> Image.Image:
    """The mark on a transparent square, drawn OVERSAMPLE times larger and reduced."""
    big = size * OVERSAMPLE
    k = big / BOX
    im = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pts = [(x * k, y * k) for x, y in s["triangle"]]
    colour, width = s["stroke"]
    w = width * k
    d.polygon(pts, fill=s["fill"])
    # a round-joined stroke centred on the edge: the line plus a disc at each corner
    d.line(pts + [pts[0]], fill=colour, width=round(w))
    for x, y in pts:
        d.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=colour)
    for (x, y, rw, rh), fill in s["rects"]:
        d.rectangle([x * k, y * k, (x + rw) * k, (y + rh) * k], fill=fill)
    return im.resize((size, size), Image.LANCZOS)


def ico_bytes(svg: str) -> bytes:
    s = shapes(svg)
    frames = [render(s, n) for n in SIZES]
    out = io.BytesIO()
    frames[-1].save(out, format="ICO", sizes=[(n, n) for n in SIZES], append_images=frames[:-1])
    return out.getvalue()


def main() -> int:
    data = ico_bytes(favicon_svg(INDEX.read_text("utf-8")))
    (ROOT / "Calandria.ico").write_bytes(data)
    print(f"Calandria.ico  {len(data)} bytes, sizes {', '.join(map(str, SIZES))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
