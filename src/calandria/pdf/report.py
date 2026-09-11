"""The summary report block (V28): names, time, rendering set, options, counts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..diff.changes import Comparison

TITLE = "Comparison summary"
TITLE_SIZE = 11.0
SIZE = 9.0
GAP = 24.0           # space between the last content and the block
RULE_GAP = 6.0       # space between the top rule and the title
LINE_GAP = 2.0       # space between the title and the first line
RULE_T = 0.5
BLACK = "000000"
ELLIPSIS = "..."


@dataclass
class ReportInfo:
    original: str
    modified: str
    when: datetime
    render_set: str
    summary: dict
    ignore_case: bool
    count_numbering: bool
    changed_only: tuple[int, int] | None = None   # (pages emitted, pages in the layout) for a changed-pages-only PDF


def report_info(cmp: Comparison, original: str, modified: str, render_set: str,
                when: datetime | None = None) -> ReportInfo:
    return ReportInfo(original, modified, when or datetime.now(), render_set, dict(cmp.summary),
                      cmp.ignore_case, cmp.count_numbering)


def _onoff(b: bool) -> str:
    return "on" if b else "off"


def report_lines(info: ReportInfo) -> list[str]:
    s = info.summary
    lines = [
        f"Original: {info.original}",
        f"Modified: {info.modified}",
        f"Compared: {info.when:%Y-%m-%d %H:%M}",
        f"Rendering set: {info.render_set}",
        f"Options: ignore case {_onoff(info.ignore_case)}; count numbering changes {_onoff(info.count_numbering)}",
        f"Changes: {s['total']} (insertions {s['insertions']}, deletions {s['deletions']}, "
        f"amendments {s['amendments']}, numbering {s['numbering']}); formatting {s['formatting']} (not counted)",
    ]
    if info.changed_only:
        lines.append(f"Changed pages only: {info.changed_only[0]} of {info.changed_only[1]} pages")
    return lines


def report_height(info: ReportInfo, regular, bold) -> float:
    return RULE_GAP + bold.line_height(TITLE_SIZE) + LINE_GAP + len(report_lines(info)) * regular.line_height(SIZE)


def _fit(text: str, face, size: float, w: float) -> str:
    if face.width(text, size) <= w:
        return text
    while text and face.width(text + ELLIPSIS, size) > w:
        text = text[:-1]
    return text + ELLIPSIS


def draw_report(info: ReportInfo, x: float, y: float, w: float, regular, bold, painter) -> float:
    """Draws the block with its top rule at y; returns the y below it."""
    painter.rule(x, x + w, y, RULE_T, BLACK)
    y += RULE_GAP
    painter.text(x, y + bold.ascent(TITLE_SIZE), TITLE, bold, TITLE_SIZE, BLACK,
                 fake_bold=bool(bold.synthetic and bold.bold))
    y += bold.line_height(TITLE_SIZE) + LINE_GAP
    for t in report_lines(info):
        painter.text(x, y + regular.ascent(SIZE), _fit(t, regular, SIZE, w), regular, SIZE, BLACK)
        y += regular.line_height(SIZE)
    return y
