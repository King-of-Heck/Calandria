"""Longest-common-subsequence edit script.

Ops are ("equal" | "delete" | "insert", i, j) triples in the reference engine's exact order and
tie-breaking: a suffix-LCS table walked forward, preferring delete over insert on ties. difflib
was rejected on purpose -- SequenceMatcher is not an LCS (longest-block heuristic plus autojunk),
so its edit scripts differ from the reference's and the change-list gate could never hold.
Above DP_CELL_CAP cells the input is trimmed (common prefix/suffix) and split on patience
anchors (elements unique in both slices, chained by longest increasing subsequence).
"""
from __future__ import annotations

DP_CELL_CAP = 1_000_000  # max n*m cells the exact table may allocate

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
