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
