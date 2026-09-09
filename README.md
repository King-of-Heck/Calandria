# Calandria

Offline Word (`.docx`) redline / compare tool from HeckSoft (a King of Heck Company).
Successor to SorkWhare Compare. Runs from a single downloaded folder — no install —
and produces a paged on-screen redline and a PDF from one layout engine. Documents
never leave the machine.

Status: pre-release (v2.0.0 in development).

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
                        [--report=first|last|none]
python -m calandria serve [--port=N] [--idle=SECONDS] [--no-browser] [--verbose]
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
page before the document, `--report=none` to omit). Change bars, change numbers and the summary
exist only in the PDF and the viewer; nothing is written back to Word.

The corpus gate `tests/parity/test_pdf.py` checks that every pair's PDF has exactly the layout's
page count and that its text reads back.

## Viewer

`python -m calandria serve` (or a double-click on `Calandria.cmd`) starts a local server on
127.0.0.1 and opens the browser on the viewer. Drop the original and the modified `.docx` on
the page (or pick them with the two file buttons) and press Compare: the pages shown are the
same drawing the PDF gets — the server draws every page as SVG from the page model, so the
screen and the PDF never disagree. The header switches the rendering set and the change bars
(a redraw), the compare options and the hide filters (a re-compare and re-layout), the zoom
(a scale of the fixed layout, 50–200 % or fit width) and the report placement; "Save PDF"
downloads the PDF with the current settings. The left panel has the count tiles, category and
location filters, the numbered change list (click a row to jump to it; First / Previous /
Next / Last, a go-to box, and the keys `n`, `p`, `Home`, `End` outside inputs) and "Change X
of Y". Documents never leave the machine.

The server keeps one comparison in memory, stops on Quit, and stops by itself after five
minutes without the page (`--idle=SECONDS`, 0 = never); `--port=N` fixes the port,
`--no-browser` only prints the URL, `--verbose` logs requests. Change bars, change numbers
and the summary exist only in the viewer and the PDF; nothing is written to Word.
