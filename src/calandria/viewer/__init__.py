"""The on-screen viewer: server-drawn SVG pages shown by a small browser page.

Rules:
- The browser draws nothing of its own. svg.py is a Painter (page / text / rule / line) driven by
  the same pdf.draw.draw_layout walk that writes the PDF, one <svg> per page in points
  (viewBox "0 0 w h"). A run is a <text x y> at its laid-out x on its baseline, in the layout's
  RESOLVED family, with textLength pinning its advance to the layout's width (lengthAdjust
  "spacing": glyphs are never distorted). Decorations, the table grid, change bars and gutter
  numbers are the same rules and lines the PDF gets. Screen equals PDF because they are one
  drawing; run_style, cid_label, bar_intervals, decorations and report_lines are shared code.
- A real bold / italic face sets font-weight / font-style so the browser picks the installed
  face; a synthetic face keeps the regular face and is faked exactly like the PDF: fake bold is a
  stroke of 0.03 x size in the text colour, fake italic a skewX(-12) about the baseline origin.
  A dotted underline is the dash pattern the PDF uses (1 on, 1.5 off).
- Zoom is a CSS scale of the fixed layout (the SVG keeps its viewBox; width / height = page size
  x zoom); nothing re-lays-out on zoom. Selecting a change draws a translucent band (a <rect>
  the page script inserts) over every line and changed table row carrying its number.
- index.html / style.css / app.js / changes.js / sources.js are the page. They talk only to the JSON API in
  calandria.server (see that package's docstring).
- Change bars, change numbers and the summary exist only in the viewer and the PDF; nothing is
  written to Word.
- A density strip beside the pages marks every change at its place in the whole document, coloured
  by category, with a band for what is on screen and a click that jumps to a change.
- "Changed pages only" is a view toggle that hides pages without a change while keeping real page
  numbers, and a matching PDF option that writes only the first page and the changed pages.
- Each change row can copy its modified or original text (a ⋯ menu or right-click), and Copy Final
  in the change list header copies the whole modified document as plain text.
- The gutter change numbers keep a minimum legible size below 100% zoom on screen, independent of
  the page's own scale; the PDF numerals are unaffected.
"""
