"""PDF sink: draws the layout engine's page model with fpdf2. Nothing here measures text or
paginates; every coordinate comes from the page model (points, origin top-left, y downward).

Rules:
- Rendering sets (rendersets.py) are the one data object that styles both sinks: per category
  (insert, delete, formatting, move-from, move-to) a colour, a set of effects, an optional
  background, a prefix and a suffix. Built in: "Standard" (Litera's defaults) and "Black and
  White" (black text, same effects, no fills). Prefix/suffix and cell fills are data only in
  v2.0.0: no sink draws them (widths are the layout's; the page model has no per-cell change kind).
- A run's colour is its category's colour, else the document's own colour, else black. Effects
  that draw lines (decor.py, fractions of the size below the baseline): underline +0.11 (0.06
  thick), double underline +0.08 / +0.20 (0.045), strikethrough -0.26 (0.06), double
  strikethrough -0.31 / -0.21 (0.045), dotted underline = the underline dashed 1 pt on / 1.5 pt
  off. The document's own underline adds a single underline unless the category already draws a
  double one. bold / italic effects and synthetic faces are drawn as fake bold (fill + stroke,
  0.03 x size) and fake italic (12 degree skew about the baseline origin): widths never change.
- Change bars (default on): a 1.5 pt black bar at margin_left - 6 spanning each run of
  vertically contiguous changed lines; a changed table row contributes its row box and the lines
  inside it are not counted again. Gutter change numbers: PlacedLine.cid_starts, 7 pt in the
  document's default face, right-aligned to margin_left - 10 on the line's baseline, contiguous
  numbers hyphenated ("2-3"), others comma-joined.
- Tables: a uniform 0.5 pt black grid around every cell box, no top rule on a v_merge_continue
  cell (KNOWN_DIVERGENCES (m)); no shading.
- Summary report (report.py): "Comparison summary" with the original / modified names, the
  date and time, the rendering set, the options and the counts, on the last page below the
  content when it fits, else on one extra page; or on its own page before page 1; or omitted.
- Fonts: every face in Layout.fonts is embedded as a TrueType subset from its file (TTC members
  by font number); a synthetic face is drawn with the file the layout resolved and faked.
"""
