"""The drawing operators of one page -> its text runs and border segments. A small PDF content
interpreter: the graphics matrix stack, the text state, path painting. It knows nothing of pypdf;
`ops` holds plain Python operands (extract.py converts them)."""
from __future__ import annotations

from .pdffonts import REPLACEMENT, PdfFont
from .types import PageData, Seg, TextRun

IDENT = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
THIN = 3.0            # pt: a filled rectangle no thicker than this is a drawn border, not shading
_STROKE = {b"S", b"s", b"B", b"B*", b"b", b"b*"}
_FILL = {b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*"}
_CLOSE = {b"s", b"b", b"b*"}


def mul(a, b):
    """The matrix that applies `a` first, then `b`."""
    return (a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3],
            a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3],
            a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5])


def apply(m, x, y):
    return (x * m[0] + y * m[2] + m[4], x * m[1] + y * m[3] + m[5])


def base_matrix(box, rotation: int):
    """PDF user space (origin bottom-left, y up, the page shown turned by `rotation` degrees
    clockwise) -> page space (origin top-left of the page as shown, y down)."""
    llx, lly, urx, ury = box
    r = rotation % 360
    if r == 90:
        return (0.0, 1.0, 1.0, 0.0, -lly, -llx)
    if r == 180:
        return (-1.0, 0.0, 0.0, 1.0, urx, -lly)
    if r == 270:
        return (0.0, -1.0, -1.0, 0.0, ury, urx)
    return (1.0, 0.0, 0.0, -1.0, -llx, ury)


class _State:
    def __init__(self):
        self.ctm = IDENT
        self.font_name, self.size = None, 0.0
        self.tc = self.tw = self.rise = self.leading = 0.0
        self.th = 1.0

    def copy(self):
        s = _State()
        s.__dict__.update(self.__dict__)
        return s


def interpret(ops, fonts: dict[str, PdfFont], xobjects: dict[str, str], base, page: PageData) -> None:
    st, stack = _State(), []
    tm = tlm = IDENT
    subpaths: list[list] = []        # each: a list of (x, y) in user space; closed ones repeat the first point
    unknown = PdfFont("Unknown")

    def full():
        return mul(st.ctm, base)

    def show(raw: bytes):
        nonlocal tm
        if not isinstance(raw, bytes):
            return                # a malformed operand: nothing shown, nothing moved
        no_font = st.font_name not in fonts
        font = fonts.get(st.font_name, unknown)
        m = mul(tm, full())
        x_start, y_start = apply(m, 0.0, st.rise)
        pieces = []
        for code, text, w in font.decode(raw):
            pieces.append(text)
            tx = (w / 1000.0 * st.size + st.tc + (st.tw if font.nbytes == 1 and code == 32 else 0.0)) * st.th
            tm = mul((1.0, 0.0, 0.0, 1.0, tx, 0.0), tm)
        x_end, _ = apply(mul(tm, full()), 0.0, st.rise)
        text = "".join(pieces).replace("\x00", "")
        upright = m[0] > 0 and m[3] < 0 and abs(m[1]) < 0.01 * abs(m[0]) and abs(m[2]) < 0.01 * abs(m[3])
        if text and upright:
            page.chars += len(text)
            page.bad_chars += text.count(REPLACEMENT)
            if no_font:
                page.bad_chars += len(text)
            page.runs.append(TextRun(text, x_start, x_end, y_start, st.size * abs(m[3]), font.name))

    def newline(tx: float, ty: float):
        nonlocal tm, tlm
        tlm = mul((1.0, 0.0, 0.0, 1.0, tx, ty), tlm)
        tm = tlm

    def seg(p, q, m):
        (x0, y0), (x1, y1) = apply(m, *p), apply(m, *q)
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        if max(dx, dy) <= 1.0 or min(dx, dy) > 0.5:
            return                                       # a dot, or a diagonal
        if dx >= dy:
            y = (y0 + y1) / 2
            page.segs.append(Seg(min(x0, x1), y, max(x0, x1), y))
        else:
            x = (x0 + x1) / 2
            page.segs.append(Seg(x, min(y0, y1), x, max(y0, y1)))

    def paint(op: bytes):
        m = full()
        for pts in subpaths:
            if op in _CLOSE and len(pts) > 2 and pts[0] != pts[-1]:
                pts = pts + [pts[0]]
            if op in _STROKE:
                for p, q in zip(pts, pts[1:]):
                    seg(p, q, m)
            elif op in _FILL and len(pts) >= 4:
                dev = [apply(m, *p) for p in pts]
                xs, ys = [p[0] for p in dev], [p[1] for p in dev]
                x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
                on_corner = all(min(abs(x - x0), abs(x - x1)) < 0.01 and min(abs(y - y0), abs(y - y1)) < 0.01
                                for x, y in dev)
                if not on_corner:
                    continue
                if (y1 - y0) <= THIN < (x1 - x0):
                    page.segs.append(Seg(x0, (y0 + y1) / 2, x1, (y0 + y1) / 2))
                elif (x1 - x0) <= THIN < (y1 - y0):
                    page.segs.append(Seg((x0 + x1) / 2, y0, (x0 + x1) / 2, y1))

    for operands, op in ops:
        try:
            if op == b"q":
                stack.append(st.copy())
            elif op == b"Q":
                if stack:
                    st = stack.pop()
            elif op == b"cm":
                st.ctm = mul(tuple(float(v) for v in operands[:6]), st.ctm)
            elif op == b"BT":
                tm = tlm = IDENT
            elif op == b"Tf":
                st.font_name, st.size = operands[0], float(operands[1])
            elif op == b"Tc":
                st.tc = float(operands[0])
            elif op == b"Tw":
                st.tw = float(operands[0])
            elif op == b"Tz":
                st.th = float(operands[0]) / 100.0
            elif op == b"TL":
                st.leading = float(operands[0])
            elif op == b"Ts":
                st.rise = float(operands[0])
            elif op == b"Td":
                newline(float(operands[0]), float(operands[1]))
            elif op == b"TD":
                st.leading = -float(operands[1])
                newline(float(operands[0]), float(operands[1]))
            elif op == b"Tm":
                tm = tlm = tuple(float(v) for v in operands[:6])
            elif op == b"T*":
                newline(0.0, -st.leading)
            elif op == b"Tj":
                show(operands[0])
            elif op == b"'":
                newline(0.0, -st.leading)
                show(operands[0])
            elif op == b'"':
                st.tw, st.tc = float(operands[0]), float(operands[1])
                newline(0.0, -st.leading)
                show(operands[2])
            elif op == b"TJ":
                for item in operands[0]:
                    if isinstance(item, bytes):
                        show(item)
                    else:
                        tm = mul((1.0, 0.0, 0.0, 1.0, -float(item) / 1000.0 * st.size * st.th, 0.0), tm)
            elif op == b"m":
                subpaths.append([(float(operands[0]), float(operands[1]))])
            elif op == b"l":
                if subpaths:
                    subpaths[-1].append((float(operands[0]), float(operands[1])))
            elif op == b"h":
                if subpaths and subpaths[-1][0] != subpaths[-1][-1]:
                    subpaths[-1].append(subpaths[-1][0])
            elif op == b"re":
                x, y, w, h = (float(v) for v in operands[:4])
                subpaths.append([(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)])
            elif op in (b"c", b"v", b"y"):
                if subpaths:
                    subpaths[-1].append((float(operands[-2]), float(operands[-1])))   # a curve: keep the path going
            elif op in _STROKE or op in _FILL:
                paint(op)
                subpaths = []
            elif op == b"n":
                subpaths = []
            elif op == b"Do":
                kind = xobjects.get(operands[0])
                if kind == "image":
                    page.images += 1
                elif kind == "form":
                    page.forms += 1
            elif op == b"INLINE IMAGE":
                page.images += 1
        except (IndexError, TypeError, ValueError):
            continue                                     # a malformed operator: skip it, keep the page
