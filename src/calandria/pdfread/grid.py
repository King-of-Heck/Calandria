"""Ruled tables from the borders a page draws. Geometry, not guesswork: snap the segments, merge
collinear pieces, take each connected lattice, and read its cells off the lines that are there."""
from __future__ import annotations

from dataclasses import dataclass

from .types import Seg

TOL = 1.5             # pt: borders drawn cell by cell land within this of each other
COVER = 0.8           # an edge counts as drawn when this share of it is covered


@dataclass(frozen=True)
class GridCell:
    row: int
    col: int
    rowspan: int
    colspan: int
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass
class Grid:
    xs: list[float]
    ys: list[float]
    cells: list[GridCell]

    @property
    def x0(self) -> float:
        return self.xs[0]

    @property
    def x1(self) -> float:
        return self.xs[-1]

    @property
    def y0(self) -> float:
        return self.ys[0]

    @property
    def y1(self) -> float:
        return self.ys[-1]

    def cell_at(self, x: float, y: float) -> int | None:
        for i, c in enumerate(self.cells):
            if c.x0 <= x <= c.x1 and c.y0 <= y <= c.y1:
                return i
        return None


def _centers(values: list[float]) -> list[float]:
    out: list[list[float]] = []
    for v in sorted(values):
        if out and v - out[-1][-1] <= TOL:
            out[-1].append(v)
        else:
            out.append([v])
    return [sum(c) / len(c) for c in out]


def _snap(v: float, centers: list[float]) -> float:
    return min(centers, key=lambda c: abs(c - v))


def _merge(items: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    """(position, lo, hi) pieces -> the same with positions snapped and touching pieces joined."""
    if not items:
        return []
    centers = _centers([p for p, _lo, _hi in items])
    by_pos: dict[float, list[tuple[float, float]]] = {}
    for p, lo, hi in items:
        by_pos.setdefault(_snap(p, centers), []).append((lo, hi))
    out = []
    for p, spans in by_pos.items():
        spans.sort()
        lo, hi = spans[0]
        for a, b in spans[1:]:
            if a <= hi + TOL:
                hi = max(hi, b)
            else:
                out.append((p, lo, hi))
                lo, hi = a, b
        out.append((p, lo, hi))
    return out


def _covered(lines, pos: float, lo: float, hi: float) -> bool:
    need = hi - lo
    got = sum(max(0.0, min(hi, b) - max(lo, a)) for p, a, b in lines if abs(p - pos) <= TOL)
    return need > 0 and got >= COVER * need


class _Sets:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def join(self, i: int, j: int) -> None:
        self.parent[self.find(i)] = self.find(j)


def _grid(hs, vs) -> Grid | None:
    xs, ys = sorted({p for p, _a, _b in vs}), sorted({p for p, _a, _b in hs})
    if len(xs) < 2 or len(ys) < 2:
        return None
    rows, cols = len(ys) - 1, len(xs) - 1
    sets = _Sets(rows * cols)
    for i in range(rows):
        for j in range(cols):
            if j + 1 < cols and not _covered(vs, xs[j + 1], ys[i], ys[i + 1]):
                sets.join(i * cols + j, i * cols + j + 1)
            if i + 1 < rows and not _covered(hs, ys[i + 1], xs[j], xs[j + 1]):
                sets.join(i * cols + j, (i + 1) * cols + j)
    groups: dict[int, list[tuple[int, int]]] = {}
    for i in range(rows):
        for j in range(cols):
            groups.setdefault(sets.find(i * cols + j), []).append((i, j))
    cells = []
    for members in groups.values():
        r0, r1 = min(i for i, _ in members), max(i for i, _ in members)
        c0, c1 = min(j for _, j in members), max(j for _, j in members)
        cells.append(GridCell(r0, c0, r1 - r0 + 1, c1 - c0 + 1, xs[c0], ys[r0], xs[c1 + 1], ys[r1 + 1]))
    if len(cells) < 2:
        return None
    cells.sort(key=lambda c: (c.row, c.col))
    return Grid(xs, ys, cells)


def find_grids(segs: list[Seg]) -> list[Grid]:
    hs = _merge([(s.y0, s.x0, s.x1) for s in segs if s.horizontal and s.length > TOL])
    vs = _merge([(s.x0, s.y0, s.y1) for s in segs if not s.horizontal and s.length > TOL])
    sets = _Sets(len(hs) + len(vs))
    for i, (hy, hx0, hx1) in enumerate(hs):
        for j, (vx, vy0, vy1) in enumerate(vs):
            if hx0 - TOL <= vx <= hx1 + TOL and vy0 - TOL <= hy <= vy1 + TOL:
                sets.join(i, len(hs) + j)
    comps: dict[int, tuple[list, list]] = {}
    for i, h in enumerate(hs):
        comps.setdefault(sets.find(i), ([], []))[0].append(h)
    for j, v in enumerate(vs):
        comps.setdefault(sets.find(len(hs) + j), ([], []))[1].append(v)
    grids = [g for h, v in comps.values() if len(h) >= 2 and len(v) >= 2 and (g := _grid(h, v)) is not None]
    grids = [g for g in grids
             if not any(o is not g and o.x0 - TOL <= g.x0 and g.x1 <= o.x1 + TOL
                        and o.y0 - TOL <= g.y0 and g.y1 <= o.y1 + TOL for o in grids)]
    return sorted(grids, key=lambda g: (g.y0, g.x0))
