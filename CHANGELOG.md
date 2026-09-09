# Calandria changelog

## v2.0.0 — First release (2026-09-09)

- Offline Word (`.docx`) redline / compare tool: a paged on-screen viewer and a PDF, both drawn
  from one layout engine, so the screen and the PDF never disagree. Documents never leave the
  machine.
- Runs from a single downloaded folder on any 64-bit Windows machine: extract the zip, double-click
  `Calandria.cmd`. No install, no admin rights, no internet connection.
- Compares body text, tables and list numbering; reports insertions, deletions, amendments,
  numbering changes and formatting changes; options to ignore case and to leave numbering
  changes uncounted.
- Layout engine with Word's pagination rules: font metrics from the installed fonts, widow and
  orphan control, keep-with-next and keep-lines, page-break-before, section breaks with their
  own page geometry, indents, list markers with tab stops, atomic table rows.
- Viewer: drop two files, compare, page through the redline, switch the rendering set
  ("Standard": blue double underline / red strikethrough; "Black and White"), toggle change bars,
  hide unchanged text or any category, zoom 50–200 % or fit width, and navigate the numbered
  change list (badges, count tiles, category and location filters, First / Previous / Next /
  Last, go-to, keys `n`, `p`, `Home`, `End`).
- PDF: embedded TrueType subsets, redline styling, change bars, gutter change numbers, a uniform
  table grid and a summary report block (first page, last page or none). Saved from the viewer or
  from the command line (`python -m calandria pdf`).
- Command line: `dump`, `compare`, `layout`, `pdf`, `serve`, `version`.
- Change bars, change numbers and the summary exist only in the viewer and the PDF; nothing is
  written back to Word. No `.docx` output.
- Successor to SorkWhare Compare 1.16.0 (frozen); extraction and change lists are held to it by
  the parity harness.
