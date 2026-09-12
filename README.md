# Calandria

Offline Word (`.docx`) redline / compare tool from HeckSoft (a King of Heck Company).
Successor to SorkWhare Compare. Runs from a single downloaded folder
and produces a paged on-screen redline and a PDF from one layout engine. Documents
never leave the machine.

Status: v2.4.4 (see `CHANGELOG.md`).

## Running from the release zip

Download `Calandria-<version>.zip` from the GitHub release, extract it anywhere (Explorer's
"Extract All" is fine) and double-click `Calandria.cmd` inside the extracted folder. Calandria
opens in its own window (Microsoft Edge in app mode; the default browser if Edge is absent).
Close the window, or press Quit, to stop it. Nothing is installed: the folder holds its own
64-bit Python and libraries, and removing the folder removes everything. To update, extract the
new zip and delete the old folder. If nothing appears, look at
`%LOCALAPPDATA%\Calandria\calandria.log`. Its first line is written by `Calandria.cmd` itself,
so a missing or empty log means the launcher never ran.

The first launch also writes a `Calandria` shortcut beside `Calandria.cmd`, carrying the icon (a
`.cmd` cannot). Double-click the shortcut, or drag it to the Desktop or pin it, to start Calandria from
then on; every launch refreshes it, so it follows the folder if you move it.

Inside the folder: `Calandria.cmd`, `Calandria.ico`, this file, the changelog and `_internal\` (`python\`, the
official embeddable Python with the libraries extracted into `Lib\site-packages`, and
`app\calandria\`, the program). `_internal\python\python.exe -m calandria <command>` runs the
command line from the folder.

## Command line

```
python -m calandria dump <file.docx>
python -m calandria compare <a.docx> <b.docx> [--ignore-case] [--no-count-numbering]
python -m calandria layout <a.docx> <b.docx> [--ignore-case] [--no-count-numbering]
                           [--hide-unchanged] [--hide-insertions] [--hide-deletions]
                           [--hide-formatting] [--pages]
python -m calandria pdf <a.docx> <b.docx> <out.pdf> [--ignore-case] [--no-count-numbering]
                        [--hide-unchanged] [--hide-insertions] [--hide-deletions]
                        [--hide-formatting] [--no-change-bars] [--render-set=NAME]
                        [--report=first|last|none] [--changed-only]
python -m calandria serve [--port=N] [--idle=SECONDS] [--grace=SECONDS] [--log=PATH]
                          [--no-browser] [--verbose]
```

## Running the parity gate

Extraction is held to the reference engine by `tests/parity`. The corpus and the reference
output it compares against are both generated and git-ignored, so a fresh clone is red until
they have been built:

```
uv run python harness/build_corpus.py
uv run python harness/gen_pairs.py
node harness/oracle_export.mjs
```

The first copies the regression pairs into `tests/corpus/` and writes its manifest; the second
writes five synthetic pairs (formatting, tables, punctuation, dense rewrites, the inline token
cap) into `tests/corpus/` alongside `manifest.gen.json`; the third runs the reference engine over
both manifests and writes `tests/oracle/`. Re-run the third whenever the exporter's field list
changes. Then `uv run pytest tests/parity -q` should be green with an empty
`tests/parity/allow.json`; deliberate differences are listed in `tests/parity/KNOWN_DIVERGENCES.md`.

## Layout, page counts and the Word smoke check

`layout` prints the page model (pages, positioned lines, glyph runs, table boxes) that the PDF
writer and the viewer draw; `--pages` prints only the page count. Metrics come from the fonts
installed under `C:\Windows\Fonts` (override with `CALANDRIA_FONT_DIRS`).

Page counts on the corpus, and a digest of each redline's whole page model (so a line that merely
moves is caught too), are pinned by `tests/parity/golden-pages.json`. After a deliberate layout
change, regenerate it and review the diff:

```
uv run python harness/golden_pages.py
```

Word's own page count is a smoke check, not a gate: export a corpus document to PDF from Word,
drop it in `tests/fixtures/wordpdf/<name>.pdf` (or a `<name>.pages` file with the count) and run
`uv run python harness/word_pages.py`.

## PDF

`pdf` draws the same page model into a PDF: the fonts the layout resolved are embedded as
TrueType subsets, insertions and deletions are styled by a rendering set (`--render-set=Standard`,
the default: blue double underline / red strikethrough; `--render-set="Black and White"`: black
text, same effects), changed lines get a change bar in the left margin (`--no-change-bars` to
omit) and a change number in the gutter, tables draw a uniform 0.5 pt grid, and a summary block
(names, date, rendering set, options, counts) goes on the last page (`--report=first` for its own
page before the document, `--report=none` to omit). `--changed-only` writes only the first page
and the pages with a change; the summary block says how many of the document's pages are shown.
Change bars, change numbers and the summary exist only in the PDF and the viewer; nothing is
written back to Word.

The corpus gate `tests/parity/test_pdf.py` checks that every pair's PDF has exactly the layout's
page count and that its text reads back.

## Viewer

`python -m calandria serve` (or a double-click on `Calandria.cmd`) starts a local server on
127.0.0.1 and opens the viewer in an Edge app window (or the default browser). Drop the original
`.docx` on the "Original" card and the modified one on "Modified" (or click a card to choose, or
drop both files anywhere), then press Compare; Swap exchanges the sides. The pages shown are the
same drawing the PDF gets — the server draws every page as SVG from the page model, so the screen
and the PDF never disagree. The toolbar has the change navigation (First / Prev / Next / Last, a
go-to box, "Change X of Y"; keys `n` / `p`, `j` / `k`, the arrows, `Home`, `End`, and `?` for
the sheet), the zoom stepper (20–400 % or fit width; Ctrl+wheel), "Save PDF", and an Options
popover with the comparison options and the page toggles (a re-compare and re-layout), the
rendering set and change bars (a redraw), the PDF summary placement and Quit. The left panel has
the count tiles (click one to filter), the location select, and the numbered change list (page
number per row; click a row to jump to it); it folds to a rail with ‹. Documents never leave
the machine.

A density strip sits beside the pages: one mark per change over the whole document, coloured by
category, with the current change's mark bigger; clicking a mark jumps to that change. "Changed
pages only" under Options → On the page hides the pages without a change (page numbers stay
real; the counter says how many pages are shown), with a matching PDF option. A ⋯ button on a
change row, or a right-click on it, copies that change's modified or original text; Copy Final
in the change list header copies the whole modified document as plain text. The gutter change
numbers stay legible below 100 % zoom on screen.

The server keeps one comparison in memory, stops on Quit, and stops by itself a few seconds
after the window closes (`--idle=SECONDS` after the last request, default 8, 0 = never;
`--grace=SECONDS` before the first request, default 120); `--port=N` fixes the port,
`--no-browser` only prints the URL, `--verbose` logs requests, `--log=PATH` writes the start
line and any error to a file. Change bars, change numbers
and the summary exist only in the viewer and the PDF; nothing is written to Word.

The corpus gate `tests/parity/test_viewer.py` checks that every pair's viewer payload has one
well-formed page drawing per layout page and that every numbered change has a place to jump to.

## Building a release

```
uv run python harness/build_release.py
```

runs the whole test suite (the parity gates included), downloads the embeddable Python and the
runtime wheels named in `uv.lock` into `build/cache/` (each checked against its recorded sha256),
extracts them into `build/stage/Calandria-<version>/`, smoke-tests the staged interpreter
(`version`, the imports, a `pdf`, a `serve`) and writes `dist/Calandria-<version>.zip`. The
version is `calandria.__version__` and must have an entry in `CHANGELOG.md`.
`--skip-tests`, `--skip-smoke` and `--keep-stage` are for iterating on the script; `--notes`
prints the release notes for the GitHub release.
