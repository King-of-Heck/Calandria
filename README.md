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
