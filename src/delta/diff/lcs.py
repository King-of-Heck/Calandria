"""Longest-common-subsequence edit script.

Ops are ("equal" | "delete" | "insert", i, j) triples in the reference engine's exact order and
tie-breaking: a suffix-LCS table walked forward, preferring delete over insert on ties. difflib
was rejected on purpose -- SequenceMatcher is not an LCS (longest-block heuristic plus autojunk),
so its edit scripts differ from the reference's and the change-list gate could never hold.
Above DP_CELL_CAP cells the input is trimmed (common prefix/suffix) and split on patience
anchors (elements unique in both slices, chained by longest increasing subsequence).

word_ops is the inline word diff's own alignment: matches weighted (a long word outweighs a lone
connective plus spaces), then fewest change runs, then most matches, and a final
tie-break that does not depend on which side is the original -- so swapping the documents
mirrors the result.
"""
from __future__ import annotations

DP_CELL_CAP = 1_000_000  # max n*m cells the exact table may allocate
WORD_CELL_CAP = 250_000  # max n*m cells for word_ops's table; above it, plain lcs_ops

Op = tuple[str, int, int]


def lcs_ops(a, b) -> list[Op]:
    ops: list[Op] = []
    _diff(a, 0, len(a), b, 0, len(b), ops)
    return ops


def _dp_ops(a, a0, a1, b, b0, b1, ops):
    n, m = a1 - a0, b1 - b0
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        ai, row, nxt = a[a0 + i], dp[i], dp[i + 1]
        for j in range(m - 1, -1, -1):
            if ai == b[b0 + j]:
                row[j] = nxt[j + 1] + 1
            else:
                x, y = nxt[j], row[j + 1]
                row[j] = x if x >= y else y
    i = j = 0
    while i < n and j < m:
        if a[a0 + i] == b[b0 + j]:
            ops.append(("equal", a0 + i, b0 + j))
            i += 1
            j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            ops.append(("delete", a0 + i, b0 + j))
            i += 1
        else:
            ops.append(("insert", a0 + i, b0 + j))
            j += 1
    while i < n:
        ops.append(("delete", a0 + i, b0 + j))
        i += 1
    while j < m:
        ops.append(("insert", a0 + i, b0 + j))
        j += 1


def _diff(a, a0, a1, b, b0, b1, ops):
    # Untrimmed DP first: whenever the whole slice fits, the script is the plain DP's, byte for
    # byte (the reference guarantees this and the gate relies on it).
    if (a1 - a0) * (b1 - b0) <= DP_CELL_CAP:
        _dp_ops(a, a0, a1, b, b0, b1, ops)
        return
    while a0 < a1 and b0 < b1 and a[a0] == b[b0]:
        ops.append(("equal", a0, b0))
        a0 += 1
        b0 += 1
    suf = 0
    while a1 > a0 and b1 > b0 and a[a1 - 1] == b[b1 - 1]:
        a1 -= 1
        b1 -= 1
        suf += 1
    n, m = a1 - a0, b1 - b0
    if n == 0:
        ops.extend(("insert", a0, j) for j in range(b0, b1))
    elif m == 0:
        ops.extend(("delete", i, b0) for i in range(a0, a1))
    elif n * m <= DP_CELL_CAP:
        _dp_ops(a, a0, a1, b, b0, b1, ops)
    else:
        anchors = _unique_anchors(a, a0, a1, b, b0, b1)
        if not anchors:
            ops.extend(("delete", i, b0) for i in range(a0, a1))
            ops.extend(("insert", a1, j) for j in range(b0, b1))
        else:
            pa, pb = a0, b0
            for ai, bi in anchors:
                _diff(a, pa, ai, b, pb, bi, ops)
                ops.append(("equal", ai, bi))
                pa, pb = ai + 1, bi + 1
            _diff(a, pa, a1, b, pb, b1, ops)
    for k in range(suf):
        ops.append(("equal", a1 + k, b1 + k))


def _unique_anchors(a, a0, a1, b, b0, b1):
    """Elements occurring exactly once in each slice, chained by LIS of b-positions."""
    ca: dict = {}
    cb: dict = {}
    for i in range(a0, a1):
        v = a[i]
        ca[v] = -1 if v in ca else i
    for j in range(b0, b1):
        v = b[j]
        cb[v] = -1 if v in cb else j
    pairs = []
    for i in range(a0, a1):
        v = a[i]
        if ca[v] == i:
            j = cb.get(v)
            if j is not None and j >= 0:
                pairs.append((i, j))
    tails: list[int] = []
    tail_idx: list[int] = []
    prev = [-1] * len(pairs)
    for p, (_i, j) in enumerate(pairs):
        lo, hi = 0, len(tails)
        while lo < hi:
            mid = (lo + hi) >> 1
            if tails[mid] < j:
                lo = mid + 1
            else:
                hi = mid
        if lo == len(tails):
            tails.append(j)
            tail_idx.append(p)
        else:
            tails[lo] = j
            tail_idx[lo] = p
        prev[p] = tail_idx[lo - 1] if lo > 0 else -1
    out = []
    p = tail_idx[-1] if tails else -1
    while p >= 0:
        out.append(pairs[p])
        p = prev[p]
    out.reverse()
    return out


def word_ops(a, b, weight) -> list[Op]:
    """Edit script for tokens a -> b; weight(token) scores a match. Each gap lists its deletes
    before its inserts."""
    a0 = b0 = 0
    a1, b1 = len(a), len(b)
    while a0 < a1 and b0 < b1 and a[a0] == b[b0]:
        a0 += 1
        b0 += 1
    while a1 > a0 and b1 > b0 and a[a1 - 1] == b[b1 - 1]:
        a1 -= 1
        b1 -= 1
    n, m = a1 - a0, b1 - b0
    if n and m and n * m > WORD_CELL_CAP:
        ops = [("equal", k, k) for k in range(a0)]
        _diff(a, a0, a1, b, b0, b1, ops)
        ops.extend(("equal", a1 + k, b1 + k) for k in range(len(a) - a1))
        return ops
    mid = []
    if n and m:
        # The table always runs with the two sides in an order set by their content, not by which
        # is the original, so swapping the documents can only mirror the result.
        sa, sb = a[a0:a1], b[b0:b1]
        if sa <= sb:
            mid = _weighted(sa, sb, [weight(t) for t in sa])
        else:
            mid = [(i, j) for j, i in _weighted(sb, sa, [weight(t) for t in sb])]
    pairs = [(k, k) for k in range(a0)] + [(a0 + i, b0 + j) for i, j in mid]
    pairs += [(a1 + k, b1 + k) for k in range(len(a) - a1)]
    ops: list[Op] = []
    pi = pj = 0
    for i, j in pairs + [(len(a), len(b))]:
        ops.extend(("delete", k, pj) for k in range(pi, i))
        ops.extend(("insert", i, k) for k in range(pj, j))
        if i < len(a):
            ops.append(("equal", i, j))
        pi, pj = i + 1, j + 1
    return ops


def _weighted(a, b, wa) -> list[tuple[int, int]]:
    """Matched (i, j) pairs maximising (total weight, -change runs, match count), in that order."""
    n, m = len(a), len(b)
    run = n + m + 2                  # one run outweighs any match count
    big = run * run                  # one unit of weight outweighs any runs and count
    # e[i][j] / g[i][j]: best score for a[i:], b[j:] after an equal (a new gap opens a run) or
    # inside a gap (continuing it is free).
    e = [[0] * (m + 1) for _ in range(n + 1)]
    g = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n, -1, -1):
        ei, gi = e[i], g[i]
        en, gn = (e[i + 1], g[i + 1]) if i < n else (None, None)
        for j in range(m, -1, -1):
            if i == n and j == m:
                continue
            x = max(gn[j] if i < n else -big * big, gi[j + 1] if j < m else -big * big)
            best_e, best_g = x - run, x
            if i < n and j < m and a[i] == b[j]:
                s = wa[i] * big + 1 + en[j + 1]
                best_e, best_g = max(best_e, s), max(best_g, s)
            ei[j], gi[j] = best_e, best_g
    pairs = []
    i = j = 0
    gap = False
    while i < n and j < m:
        cur = (g if gap else e)[i][j]
        pen = 0 if gap else run
        if a[i] == b[j] and wa[i] * big + 1 + e[i + 1][j + 1] == cur:
            pairs.append((i, j))
            i, j, gap = i + 1, j + 1, False
        elif g[i + 1][j] - pen == cur:
            i, gap = i + 1, True
        else:
            j, gap = j + 1, True
    return pairs
