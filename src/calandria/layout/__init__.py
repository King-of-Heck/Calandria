"""Layout engine: a Comparison -> pages of positioned lines and glyph runs, drawn identically by
every sink.

Rules (Word-like, spec section 4.5):
- Line height: single spacing is the tallest run's font line height, taken from the TrueType hhea
  table (ascender - descender + lineGap), which is what Word uses (Calibri 11 -> 13.43 pt, Times
  New Roman 12 -> 13.8 pt). "auto" spacing multiplies it, "exact" fixes it, "atLeast" takes the
  larger. Text is bottom-aligned in the line: baseline = top + height - descent.
- Widths: hmtx advances; no kerning (Word kerns only when w:kern is set; not modelled).
- Paragraph spacing: space before + space after both apply (they add, they do not collapse);
  contextual spacing zeroes the gap between adjacent paragraphs of the same style; absent
  spacing is 0 pt; space before is dropped at the top of a page unless the page was started by
  an explicit break (or is the first page).
- Pagination: widow/orphan control (never one line alone on either side of a break), keep-with-
  next chains (looked ahead four deep, spacing included), keep-lines-together, page-break-before,
  section breaks. Table rows are atomic; a row taller than a page degrades to stacked paragraphs.
- Indents: left, first-line, hanging; a list marker sits at the first-line position and the text
  starts at the next tab stop (the hanging indent acts as one; default stops every
  Document.default_tab_pt) unless the level's suffix is a space or nothing.
- Order: the revised document in order, empty paragraphs included, with each deleted paragraph
  placed where it stood ("final showing markup").
Deviations recorded for v2.0.0: body tabs render as one space (the diff runs on collapsed text);
custom tab stops, kerning, character styles and paragraph-mark fonts (an empty paragraph takes the
document default size) are later minors.
"""
