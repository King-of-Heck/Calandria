# Calandria changelog

## v2.3.1 — Two fixes (2026-09-11)

- Gutter change numbers: changes that start on one baseline (the cells of a table row) share
  one label such as "7-9" instead of printing on top of each other, on screen and in the PDF.
- Viewer: dropping a file on the Original or Modified card clears the page area's drag
  highlight, which used to stay as a dashed outline.

## v2.3.0 — Viewer majors (2026-09-10)

- A change-density strip beside the pages: one mark per change at its place in the whole
  document, coloured by category; the current change's mark is bigger, filtered-out ones dim; a
  band shows the part of the document on screen; a click jumps to the change.
- "Changed pages only": a view toggle under Options → On the page hides the pages without a
  change (page numbers stay real; the counter says how many pages are shown), and a PDF option
  writes only the first page and the changed pages (`calandria pdf --changed-only`,
  `/api/pdf?changed_only=1`; the file name says "(changed pages)" and the summary block says
  how many of the document's pages are shown).
- Copy per change: a ⋯ button on the row, or right-click, copies the modified or the original
  text of that change; Copy Final in the change list header copies the whole modified document
  as plain text.
- The change numbers in the margin stay legible below 100 % zoom on screen; the PDF is unchanged.

## v2.2.1 — Small fixes (2026-09-10)

- Viewer: the panel's footer note is gone; the caveat stays on the empty-state card.
- Viewer: a `?` button opens the shortcut sheet; the change list is a single tab stop and the
  keys move the focus within it; the panel toggle and the sheet stay usable after the session
  closes, and the Options popover folds; Fit shows the on-screen scale of the page under the top
  of the view and follows the scroll; Escape on the popover returns the focus to Options; aria
  roles on the source cards, the panel toggle, the progress bar and the notice; the Formatting
  tile dims like the others when a category is soloed; a little room under the two-line clamp.
- Server: a refused cross-origin request no longer resets the idle clock; only the session's
  own bad-request and no-comparison errors map to 400 and 409, anything else is a 500; the page
  sends a beacon on pagehide so a last hidden ping does not delay the stop; the log rotates to
  `.1` instead of being truncated; `--verbose` is dropped when there is no stderr.
- Launcher: the stamp path is quoted; when the log folder cannot be made the log goes next to
  the launcher.
- Build: the zip leaves the testing package out; the stage smoke starts from a clean folder; a
  fenced heading no longer ends a changelog entry; `--notes` with `--notes-out` prints as well.

## v2.2.0 — Viewer refinements (2026-09-10)

- Two labelled drop cards, "Original" and "Modified", replace the file buttons: drop one file
  on a card, or two files anywhere, or click a card to choose; a Swap button exchanges the
  sides. After a comparison the cards stay above the pages as a compact strip; a new file
  waits for Compare, Swap compares again at once.
- The toolbar keeps only what every session needs: First / Prev / Next / Last with the go-to
  box and "Change x of N", the zoom stepper (−, +, 100 %, Fit; Ctrl+wheel and Ctrl+= / Ctrl+-
  / Ctrl+0), Save PDF and an Options popover holding the comparison, page, rendering and PDF
  settings and Quit. The page toggles now say "Show unchanged text", "Show insertions"…
- Keys `j` / `k` and the left / right arrows join `n` / `p`; the keys are shown on the buttons
  and `?` opens a shortcut sheet.
- A progress bar and a card over the pages during a comparison; errors and the closed state
  show as a card instead of a line in the status bar.
- Change list: each row shows its page and clamps to two lines (the selected row shows the
  full text); the count tiles are the category filters (click one to show only that category,
  click again for all); a table glyph marks changes inside tables when there are any.
- The change list folds to a narrow rail with the ‹ button and remembers it.
- Empty state explains what Calandria does, that nothing is written to Word, and that closing
  the window closes Calandria. Focus rings, one button height and readable page numbers.

## v2.1.0 — One window (2026-09-09)

- `Calandria.cmd` no longer leaves a console window open (it flashes and closes): it starts
  the program in the background and the viewer opens in its own window (Microsoft Edge in app
  mode: no tabs, no address bar, its own taskbar entry). Without Edge the default browser is
  used as before.
- Closing the window stops Calandria within a few seconds (the page pings the server every
  2 s; `--idle` now defaults to 8 s after the first visit, with a 120 s `--grace` before it).
  A laptop that sleeps with the window open resumes where it was.
- `serve --log=PATH` writes the start line and any error to a file; the launcher uses
  `%LOCALAPPDATA%\Calandria\calandria.log`.
- The extracted folder holds `Calandria.cmd`, `README.md`, `CHANGELOG.md` and one `_internal`
  folder (the Python runtime and the program). Command line from the folder:
  `_internal\python\python.exe -m calandria <command>`.

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
