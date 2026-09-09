"""Page-break planner: Word's paragraph pagination rules over abstract blocks.

Rules: widow/orphan control (a break never leaves a single line of a paragraph on either side);
keep-with-next chains (a block needs room for itself plus its successors' first two lines and the
spacing between them, looked ahead up to four deep, stopping at a page-break-before); keep-lines-
together (a paragraph that fits a page in full is not split); explicit page-break-before; and
space-before is dropped at the top of an automatically started page but kept on the first page
and after an explicit break. Structure ported from the reference planner; the space-before rule
is Word's.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class BlockSpec:
    line_heights: list[float]
    space_before: float = 0.0
    space_after: float = 0.0
    keep_next: bool = False
    keep_lines: bool = False
    page_break_before: bool = False


@dataclass(frozen=True)
class Break:
    block: int
    line: int        # the break falls BEFORE this line of the block


@dataclass
class Plan:
    breaks: list[Break]
    before: list[bool]   # per block: whether its space_before is applied


def plan_breaks(blocks: list[BlockSpec], avail_of: Callable[[int], float]) -> Plan:
    breaks: list[Break] = []
    before = [False] * len(blocks)
    st = {"page": 0, "free": avail_of(0), "top": True, "explicit": True}

    def new_page(b: int, l: int, explicit: bool = False):
        breaks.append(Break(b, l))
        st["page"] += 1
        st["free"] = avail_of(st["page"])
        st["top"], st["explicit"] = True, explicit

    def need(b: int, depth: int) -> float:
        if b >= len(blocks):
            return 0.0
        bk = blocks[b]
        total = sum(bk.line_heights)
        n = total if (bk.keep_lines and total <= avail_of(st["page"])) else sum(bk.line_heights[:2])
        if bk.keep_next and depth < 4 and b + 1 < len(blocks) and not blocks[b + 1].page_break_before:
            n = total + bk.space_after + blocks[b + 1].space_before + need(b + 1, depth + 1)
        return n

    for b, bk in enumerate(blocks):
        lines = bk.line_heights
        if bk.page_break_before and not st["top"]:
            new_page(b, 0, explicit=True)
        if not st["top"]:
            if bk.space_before + need(b, 0) > st["free"]:
                new_page(b, 0)
            else:
                st["free"] -= bk.space_before
                before[b] = True
        if st["top"] and (st["page"] == 0 or st["explicit"]):
            st["free"] = max(0.0, st["free"] - bk.space_before)
            before[b] = True
        start = 0
        while start < len(lines):
            fit, h = start, 0.0
            while fit < len(lines) and h + lines[fit] <= st["free"] + 1e-9:
                h += lines[fit]
                fit += 1
            if fit >= len(lines):
                st["free"] -= h
                st["top"] = False
                start = fit
                break
            cut = fit
            if len(lines) - cut == 1:            # widow: two lines must follow the break
                cut -= 1
            if start == 0 and cut - start == 1:  # orphan: never strand one leading line
                cut = start
            if cut <= start:
                full = abs(st["free"] - avail_of(st["page"])) < 1e-9
                if st["top"] and (fit == start or full):
                    # nothing fits, or a full-size page cannot help: force progress
                    cut = max(fit, start + 1)
                    new_page(b, cut)
                    start = cut
                else:
                    # pushed back by widow/orphan; a fresh page may hold more: retry there
                    if start == 0:
                        before[b] = False    # the block moves whole to an automatic page: no space before
                    new_page(b, start)
            else:
                new_page(b, cut)
                start = cut
        if start >= len(lines) and not st["top"]:
            st["free"] = max(0.0, st["free"] - bk.space_after)
    return Plan(breaks, before)
