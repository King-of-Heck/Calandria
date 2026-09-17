# Calandria changelog

## v2.8.0 — Comments (2026-09-16)

- Comments are compared as displayed: matched by identity across the two documents (a durable id,
  then anchor overlap plus author, then text similarity), classified added / removed / edited /
  unchanged, threaded (a reply follows its parent), and their text diffed like body text. They are
  an uncounted, navigable side list — never a row in the change list, never part of the counted
  summary.
- Drawn as right-margin bubbles on the page holding their anchor, with a connector to the anchored
  text and a bracket around it; a resolved comment shows a check mark. A commented document widens
  its sheet to the right to hold the comment column, so the body keeps its full width and a document
  paginates the same with or without comments; comment-free documents are unchanged.
- The viewer's location filter gains a Comments entry, listing every comment change with its
  author, initials, date, resolved state and diffed text, indented by reply depth.

## v2.7.0 — Headers and footers (2026-09-15)

- Headers and footers are compared, as they are displayed: for every section, the header and
  footer Word shows on its first, odd and even pages (linked to the previous section when the
  section sets none), blank ones dropped, repeated ones once, in document order. Changes in them
  are counted like body changes, listed with the location Header or Footer, and the location
  filter has both.
- Headers and footers are drawn on every page where Word draws them: the header at the header
  distance from the top, the footer above the footer distance from the bottom, the right variant
  per page (first page, even, odd). A header or footer taller than the room above or below the
  margin pushes the body, as in Word. PAGE and NUMPAGES fields show the page's own number
  (numbering restarts and roman or letter formats honoured) and the page total; a page number
  is never a change.
- A changed header shows its redline on every page it appears on; the change bar and margin
  number sit on the first of those pages, and the change list goes there.
- An inline image in an otherwise empty paragraph keeps its box (the template's logo headers are
  as tall as in Word); the picture itself is not drawn.
- Known limits: a table inside a header is laid out as its cells' paragraphs stacked; a header
  change inside a continuous section shows from the next page; Word's red notice for a changed
  first-page or link-to-previous setting is not produced.

## v2.6.1 — Paragraph spacing as Word adds it (2026-09-15)

- The space between two paragraphs is the larger of the first one's space after and the second
  one's space before, as Word lays it out (Word's HTML paragraph auto spacing, on unless the
  document's compatibility settings turn it off). Before, the two were added, so a run of
  paragraphs with both values set came out taller than in Word; on the EPC template's cover that
  pushed its last line onto a blank page once the cover's footnote took its room. Measured against
  Word's own PDF of the template: the cover's lines now sit within a point of Word's.
- Empty paragraphs at the start of a section no longer push the section's first text a page
  further: the page a section break starts was being charged twice. On the EPC template this
  removes the blank page before the list of schedules; the template alone now lays out at 199
  pages against Word's 198.
- An empty paragraph is as tall as its paragraph mark says (its style's font and size), as in
  Word, instead of the document default size.

## v2.6.0 — Footnotes and endnotes (2026-09-15)

- Footnotes and endnotes are compared. A note that was edited, added or removed shows as a
  redline like body text, with its own change number, change bar and place in the totals and
  the tiles; the change list's location filter gains Footnotes and Endnotes. A note's changes
  are numbered right after the paragraph that references it, so the numbers read in page order.
- Footnotes are drawn at the foot of the page that references them, under Word's short
  separator rule, and endnotes after the last body paragraph. Reference marks are drawn as
  superscript numbers in the text, and a note opens with its number. A note dropped with its
  paragraph keeps a struck mark where it stood. A page keeps room for the notes it carries, so a
  line moves to the next page together with its notes. A long note is not split across pages in
  this version.
- Before, references and note text were ignored: a note's edits were invisible and the pages had
  no footnotes.

## v2.5.3 — Style bold and paragraph borders (2026-09-15)

- Bold set by a paragraph style (a TOC level, a heading, a caption) is drawn in bold, as Word
  shows it. Before, only a run's own bold was drawn, so "SECTION 1" in a table of contents whose
  style is bold came out in regular weight. The comparison is unchanged: bold from a style is
  drawn, never reported as a formatting change.
- Paragraph borders (`w:pBdr`: top, bottom, left, right, on the paragraph or its style) are drawn
  as rules in the pages and the PDF, at the border's width and colour, with Word's space between
  the text and the line. Adjacent paragraphs with the same borders and indents share one box, as
  in Word. Double, dashed and the other line styles draw as a single line. Before, borders were
  not drawn at all (the two rules on the EPC template's cover were missing).

## v2.5.2 — Tabs do not size the line (2026-09-15)

- A tab formatted larger than the text around it no longer makes its line taller, as in Word.
  A table of contents whose entries carry an 11 pt tab between 10 pt text (every entry of the
  EPC template's stored TOC) now sits at Word's line pitch, so its page breaks fall where Word's
  do. Before, each such line took the tab's height.

## v2.5.1 — Capitals, symbol characters, tab stops (2026-09-15)

- Text formatted as capitals or small capitals (`w:caps`, `w:smallCaps`, on the run or its
  paragraph style) is drawn in capitals, as Word shows it; the comparison still runs on the text
  as typed. Small capitals are drawn at full size.
- A character from a symbol font (Wingdings, Wingdings 2, Symbol: a checkbox, an arrow) measures
  its own glyph width instead of a placeholder's, and the on-screen pages draw the glyph's outline
  from the font file, so it no longer runs into the text beside it. The PDF already embedded the
  right glyph.
- Tabs advance to tab stops: the paragraph's own stops and its style's and list level's, then
  Word's default stops beyond them. Right, centre and decimal stops align the text that follows,
  and dot, hyphen and underscore leaders are drawn. A table of contents now lays out as in Word:
  number, title, leader dots, page number at the right stop. Before, every tab was one space.
- The change strip beside the pages lines up with the scrollbar: its marks and the band that
  shows the part on screen sit on the scrollbar's own track (below the top arrow button, above
  the bottom one and the horizontal scrollbar), placed by where each change really is in the
  scroll, gaps between pages and zoom included. Before, the strip spanned the whole pane height
  and placed marks by page number, so a mark sat a little off the thumb.

## v2.5.0 — Changes counted by passage (2026-09-15)

- A change is a passage: a contiguous run of inserted text, a contiguous run of deleted text, or
  a renumbered list marker. A paragraph that swaps a word holds two changes, the deletion then
  the insertion, numbered in reading order and labelled together in the margin ("22-23"). This
  is the unit other comparison tools count; the amendment class is gone, and the three tiles,
  Insertions, Deletions and Numbering, add up to the total. Before, every changed paragraph was
  one change and counted as an insertion and a deletion as well, so a 200-change document could
  read 200 insertions, 200 deletions, 200 amendments and 200 changes.
- The change list has one row per passage, showing that passage with a little unchanged text
  either side; the margin numbers sit beside the line each passage starts on; the density strip,
  the on-page highlight and the side panes follow the passage.
- The PDF summary line reads `Changes: T (insertions I, deletions D, numbering N); formatting F
  (not counted)`.
- Version 2.4.7 was built but never released; its work ships here.

## v2.4.6 — Review minors (2026-09-14)

- The row menu of the changes list keeps the keyboard focus while it is open (Tab and the arrow
  keys cycle through it) and opens from the keyboard on the current row (Shift+F10 or the Menu
  key); the row's menu buttons leave the tab order.
- "Changed pages only" keeps the reader's page when it is turned on or off.
- Copy Final reports the number of lines it copied.
- The marks on the page strip carry an accessible label, and the strip reads the page heights
  once per layout.
- Inside: the blackline and the side panes share one page builder and one side map; the server
  checks a requested side in one place; a PDF request checks the document names before its flags;
  an empty layout draws nothing instead of failing.

## v2.4.5 — Shortcut without PowerShell (2026-09-12)

- The `Calandria` shortcut beside the launcher is written by Calandria itself, in the Windows
  shortcut file format, instead of through a PowerShell command: a machine that runs PowerShell
  in Constrained Language Mode refused that command, so no shortcut appeared and its errors
  filled the log. The shortcut is rewritten only when its contents change, so a synced folder
  is left alone. The log carries one `shortcut` line per start.
- "Defer page rendering" is on by default and has moved from the main display to
  Options > Rendering, where it can still be turned off. It is remembered.

## v2.4.4 — Compare on request (2026-09-12)

- Dropping documents fills the two slots and waits for the Compare button; a first drop of two
  files no longer compares by itself.
- A test toggle, "Defer page rendering", lays out the pages as they come into view instead of all
  at once, and finishes the rest in the background once the comparison is on screen. It is off
  by default and remembered.

## v2.4.3 — Faster compare (2026-09-11)

- The compare runs about three times faster: the formatting of a paragraph is worked out run by
  run instead of character by character. The result is the same to the character (the old walk
  stays in the tests as the reference).
- The Original and Modified pages are laid out and drawn the first time their pane is turned on,
  and kept for the rest of the comparison; a new comparison draws the blackline alone. A pane
  turned on while a request is still running waits for it.
- The log (`%LOCALAPPDATA%\Calandria\calandria.log`) carries one `timing` line per compare,
  relayout and redraw, with the page count and the seconds of every stage.

## v2.4.2 — Shortcut with the icon (2026-09-11)

- `Calandria.ico` ships in the zip and the launcher writes a `Calandria` shortcut beside itself with
  that icon, refreshed on every launch: a `.cmd` cannot carry an icon, a shortcut can. Start
  Calandria from the shortcut, or drag it to the Desktop or pin it.

## v2.4.1 — Icon (2026-09-11)

- Calandria has an icon: a delta with a red and a blue bar. It is embedded in the page, so the
  app window's title bar and taskbar entry show it with no file to fetch and nothing new to install.

## v2.4.0 — Side-by-side panes (2026-09-11)

- Three toggles in the toolbar, Original, Blackline and Modified, show any combination of the
  three views side by side in that order (keys 1, 2, 3). Blackline alone is the default for
  every new comparison; the last pane on cannot be turned off.
- The Original and Modified panes are clean pages laid out by the same engine as the blackline,
  with no change marks. Marks (key m) tints the deleted text in Original and the inserted text
  in Modified.
- The panes scroll together by content: the paragraph at the top of the pane you scroll is put
  at the top of the others. Next, Prev, the change list, the density strip, zoom, Fit and Changed
  pages only act on every pane; the current change is highlighted in each.
- The PDF is unchanged: it is the blackline.

## v2.3.3 — Toolbar layout (2026-09-11)

- Once a comparison exists, the Original and Modified fields, Swap and Compare sit in the
  toolbar as a second row instead of above the pages; the remove buttons sit in line with
  the file names. The empty state's drop cards are unchanged.
- The change navigation (First, Prev, Next, Last, the number box and the count) sits at the
  right of the toolbar, beside the zoom controls and Save PDF.

## v2.3.2 — Tile filters (2026-09-11)

- The Insertions and Deletions tiles filter the way their counts count: an amendment (deleted
  and inserted text in one paragraph) counts as an insertion and as a deletion, so those two
  tiles now include amendments and a tile's list matches its number. The tooltips say so.

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
