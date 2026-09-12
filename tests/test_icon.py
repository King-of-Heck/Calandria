"""Calandria.ico is generated from the favicon's geometry in index.html (one source of truth) and
the tracked file matches the generator, so the shortcut's icon and the window's icon never drift."""
import io
import re
import sys
from importlib import resources
from pathlib import Path
from urllib.parse import unquote

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))
import make_icon  # noqa: E402

SIZES = (16, 24, 32, 48, 64, 128, 256)


def _svg():
    html = resources.files("calandria.viewer").joinpath("index.html").read_text("utf-8")
    return unquote(re.search(r'href="data:image/svg\+xml,([^"]+)"', html).group(1))


def test_shapes_are_read_from_the_page_favicon():
    shapes = make_icon.shapes(_svg())
    assert shapes["triangle"] == ((256, 64), (464, 432), (48, 432))
    assert shapes["stroke"] == ("#111827", 32)
    assert shapes["rects"] == [((208, 256, 96, 32), "#FF0000"), ((176, 336, 160, 32), "#0000FF")]


def test_render_is_transparent_outside_the_mark_and_antialiased():
    im = make_icon.render(make_icon.shapes(_svg()), 64)
    assert im.mode == "RGBA" and im.size == (64, 64)
    assert im.getpixel((1, 1))[3] == 0                                     # a corner is transparent
    def near(px, rgb):                                                     # the Lanczos filter rings a little
        return max(abs(a - b) for a, b in zip(px[:3], rgb)) <= 4 and px[3] == 255

    assert near(im.getpixel((32, 40)), (255, 255, 255))                    # inside the triangle: white
    assert near(im.getpixel((32, 34)), (255, 0, 0))                        # the red bar
    assert near(im.getpixel((32, 44)), (0, 0, 255))                        # the blue bar
    alphas = {im.getpixel((x, y))[3] for x in range(64) for y in range(64)}
    assert alphas - {0, 255}                                               # edge pixels are partial


def test_ico_bytes_carry_every_size_and_are_deterministic():
    a = make_icon.ico_bytes(_svg())
    b = make_icon.ico_bytes(_svg())
    assert a == b
    ico = Image.open(io.BytesIO(a))
    assert ico.format == "ICO"
    assert sorted(s[0] for s in ico.info["sizes"]) == sorted(SIZES)


def test_tracked_ico_matches_the_generator():
    assert (ROOT / "Calandria.ico").read_bytes() == make_icon.ico_bytes(_svg())
