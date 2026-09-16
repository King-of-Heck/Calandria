"""Headers and footers on the page: which part a page shows, how tall it is, where the body may
go, and the lines themselves.

Word puts the header's top at the header distance from the page top and the footer's bottom at
the footer distance from the page bottom. The body starts at the top margin unless the header
reaches lower, and ends at the bottom margin unless the footer reaches higher (the footnote
reserve comes off that). The PAGE field is filled when the page is created (its number is known
then); NUMPAGES is filled once every page exists. A changed header is drawn in redline on every
page it appears on, but only the first of those pages carries its change bar and gutter number.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..docx.hf import SectionHf, format_number, variant_for
from ..model import Document, Section
from .blocks import Ctx, ParaBlock, collapse_spacing, note_height, para_block
from .merged import Item
from .pages import Page, PlacedLine
from .pieces import visible
from .placeline import place_line

STREAMS = ("header", "footer")


def hf_groups(items: list[Item]) -> dict[tuple[str, str | None], list[Item]]:
    """(stream, part) -> the header/footer items of that part in merged order (deleted rows
    already carry the revised part they sit next to, see merged._attach_deleted_parts)."""
    out: dict[tuple[str, str | None], list[Item]] = {}
    for it in items:
        if it.stream in STREAMS:
            out.setdefault((it.stream, it.part), []).append(it)
    return out


def part_blocks(stream: str, part: str | None, ctx: Ctx) -> list[ParaBlock]:
    """The blocks of one part at this context's width, built once per context (a table inside a
    part is laid out as its cells' paragraphs, stacked)."""
    key = (stream, part)
    if key not in ctx.parts:
        its = ctx.hf_items.get(key, [])
        blocks = [para_block(it, its[j - 1] if j else None, its[j + 1] if j + 1 < len(its) else None, ctx)
                  for j, it in enumerate(its)
                  if (ctx.opts.show_equal if it.row is None else visible(it.row, ctx.opts))]
        ctx.parts[key] = collapse_spacing(blocks, ctx)
    return ctx.parts[key]


def fill_fields(line: PlacedLine, values: dict[str, str], faces: dict, align: str) -> None:
    """Replace the field runs named in `values` by their text, re-measured; the runs after each
    move by the difference, and a centred or right-aligned line moves as a whole so it stays
    centred / flush right."""
    delta = 0.0
    for g in line.runs:
        g.x += delta
        if g.field in values:
            face = faces[g.face]
            new_w = face.width(values[g.field], g.size)
            delta += new_w - g.w
            g.text, g.w = values[g.field], new_w
    if delta and align == "center":
        for g in line.runs:
            g.x -= delta / 2
        line.x -= delta / 2
    elif delta and align == "right":
        for g in line.runs:
            g.x -= delta
        line.x -= delta


def strip_marks(line: PlacedLine) -> None:
    """A repeat of a header already marked on an earlier page: the redline stays (run modes), the
    change bar, gutter number and passage highlight do not."""
    line.changed = False
    line.cid_starts = []
    for g in line.runs + line.marker:
        g.cid = None


@dataclass
class Chrome:
    """The header and footer of one section group: its geometry per page and its drawing."""

    sec: Section
    hf: SectionHf
    doc: Document
    aliases: dict                 # stream -> {resolved part name: displayed entry name | None}
    ctx: Ctx
    first_number: int             # Word page number of the group's first page
    seen: set                     # (stream, part) already marked on a page, shared across the layout
    numpages_lines: list = field(default_factory=list)   # (PlacedLine, align) to fill once the total is known

    def number(self, pi: int) -> int:
        return self.first_number + pi

    def label(self, pi: int) -> str:
        return format_number(self.number(pi), self.sec.page_fmt)

    def part(self, stream: str, pi: int) -> str | None:
        """The canonical part name the page shows (the displayed entry carrying the resolved
        part's content), or None when the page has no header/footer or a blank one."""
        name = self.hf.part(stream, variant_for(self.sec, self.doc, pi == 0, self.number(pi)))
        return self.aliases.get(stream, {}).get(name) if name is not None else None

    def blocks(self, stream: str, pi: int) -> list[ParaBlock]:
        # A page with no part of its own shows the orphan group (deleted rows with no revised part
        # to sit next to) when there is one, else nothing.
        key = self.part(stream, pi)
        if key is None and (stream, None) not in self.ctx.hf_items:
            return []
        return part_blocks(stream, key, self.ctx)

    def top(self, pi: int) -> float:
        h = note_height(self.blocks("header", pi))
        return max(self.sec.margin_top_pt, self.sec.header_pt + h) if h else self.sec.margin_top_pt

    def bottom(self, pi: int) -> float:
        h = note_height(self.blocks("footer", pi))
        margin = self.sec.page_h_pt - self.sec.margin_bottom_pt
        return min(margin, self.sec.page_h_pt - self.sec.footer_pt - h) if h else margin

    def draw(self, page: Page, pi: int) -> None:
        page.label = self.label(pi)
        values = {"PAGE": page.label}
        for stream in STREAMS:
            blocks = self.blocks(stream, pi)
            if not blocks:
                continue
            key = (stream, self.part(stream, pi))
            marked = key not in self.seen
            self.seen.add(key)
            if stream == "header":
                y = self.sec.header_pt
            else:
                y = self.sec.page_h_pt - self.sec.footer_pt - note_height(blocks)
            for pb in blocks:
                y += pb.space_before
                for li, line in enumerate(pb.lines):
                    pl = place_line(pb, li, line, self.sec.margin_left_pt, y, self.ctx.content_w, self.ctx)
                    pl.stream = stream
                    fill_fields(pl, values, self.ctx.faces, pb.align)
                    if any(g.field == "NUMPAGES" for g in pl.runs):
                        self.numpages_lines.append((pl, pb.align))
                    if not marked:
                        strip_marks(pl)
                    page.lines.append(pl)
                    y += line.height
                y += pb.space_after
