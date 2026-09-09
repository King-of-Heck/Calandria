# Known model-vs-reference divergences

The parity gate (`tests/parity/test_extraction.py`) compares Calandria's extraction against the
reference engine's, paragraph for paragraph, over the corpus. The two are not meant to agree
everywhere: `calandria.model` and the parser keep Word semantics, while the reference engine is a
regex reader with its own simplifications. The list below records every place where the two are
known to differ by design, with the reason and which side matches Word.

None of these are currently reached by a corpus pair, so `allow.json` is empty. They are written
down so that a future failure is recognised as a known divergence rather than a fresh bug.

## (a) List counters: per abstract list vs. a single level-keyed cascade

Calandria keeps one counter set per abstract numbering definition, so two interleaved lists that
use different abstract definitions advance independently. The reference keeps a single cascade
keyed by level, so interleaving two lists at the same level makes them share one running number.

Calandria is Word-correct. Word restarts and continues numbering per abstract list; a level
number belongs to the list that owns it, not to the level index on its own.

## (b) `w:lvlOverride` / `w:startOverride`

Calandria honours a `<w:num>`'s `<w:lvlOverride><w:startOverride>` and restarts that level's
counter on first use of the overriding `numId`. The reference ignores overrides entirely and
continues the shared abstract list.

Calandria is Word-correct. `startOverride` is how Word expresses "restart numbering at 1" for a
list that reuses an existing abstract definition, which is the normal shape a restart takes.

## (c) Empty numbered paragraphs consume a number

An empty paragraph carrying a `<w:numPr>` takes a number in Calandria, so the next item in the
list skips one. The reference returns from its paragraph handler as soon as the collapsed text is
empty -- before it resolves numbering -- so an empty numbered paragraph consumes nothing.

Calandria is Word-correct: Word numbers an empty list item and shows its marker. Both sides drop
the empty paragraph from the flat records, so the divergence surfaces as a `marker` mismatch on
the *following* items, not as a paragraph-count difference. Pinned by
`tests/test_parser.py::test_empty_numbered_paragraph_consumes_a_number`.

## (d) The default paragraph style applies to unstyled paragraphs

A paragraph with no `<w:pStyle>` resolves through Word's default paragraph style (the
`w:type="paragraph"` style marked `w:default`) in Calandria, so it inherits that style's
alignment, indents and `numPr` as well as its spacing and keep flags. The reference consults the
default style for spacing and the keep flags only; alignment, indents and numbering fall back to
their hard defaults.

Calandria is Word-correct: the default paragraph style is a full style, not a spacing-only one.
Expect this to show up as `align`, `indLeftPt`, `indHangingPt`, `indFirstLinePt`, `marker` or
`isNumbered` on a document whose default style sets any of them.

## (e) A dangling `pStyle` skips the default-style rung

When a paragraph names a `pStyle` that is absent from `styles.xml`, Calandria resolves an empty
style chain -- the default paragraph style is used only when no `pStyle` is named at all. So a
dangling style id yields hard defaults, not the default style's properties.

This matches Word, which resolves the named style or nothing; it is not a fallback to Normal. The
reference reaches the same result by a different route (it has no default-style rung for these
fields in the first place), so this only diverges on the fields listed in (d).

## (f) `w:default` acceptance is wider than the reference's

Calandria treats a style as the default paragraph style when `w:default` is `1`, `true` or `on`,
and treats a style with no `w:type` as a paragraph style (Word's own default for the attribute).
The reference requires literally `w:default="1"` together with an explicit `w:type="paragraph"`.

Calandria is Word-correct -- these are ordinary OOXML boolean and attribute-default rules -- but
it means a document written with `w:default="true"`, or with the type attribute omitted, gets a
default paragraph style in Calandria and none in the reference, which then shows up as the
divergences described in (d).

## Policy

When a corpus pair actually hits one of these, add an entry to `tests/parity/allow.json` scoped to
that pair's alias and to the single field that diverges, citing the item letter above in the
reason. For example:

    [{"alias": "spacing", "field": "indLeftPt", "reason": "KNOWN_DIVERGENCES (d)"}]

Do not use `"alias": "*"`, and do not widen an entry to cover fields the pair does not actually
diverge on -- a scoped entry keeps the gate discriminating everywhere else. Anything not on this
list is a bug in Calandria until it is investigated and either fixed or added here.

# Diff-engine divergences (Plan 2)

The change-list gate (`tests/parity/test_changes.py`) compares rows (type, cid, category, indices,
rendered html, numbering and formatting flags, table location) and the summary against the
reference's `compare()` with moves and split/merge disabled (`compare_v2` / `compare_v2_ic` in the
oracle files). Its allow list is `allow-changes.json`, same policy as above.

## (g) ASCII word class (not yet diverged — a recorded intention)

The tokenizer uses the reference's ASCII word/digit classes so that tokens, and therefore rendered
rows, match. Word treats a non-ASCII letter as part of a word; a future release may widen the
class, at which point every changed paragraph containing such letters will diverge on `html` and
the oracle comparison needs a token-level normalization. Until then both sides agree.

## (h) Whitespace class (not a divergence -- a recorded intention)

Calandria deliberately uses the reference's JavaScript `\s` set (single source `model.WS_CHARS`),
so U+FEFF collapses to a space and U+0085 does not -- matching the reference, not Python's `\s`.

Not a divergence today; recorded so nobody "fixes" it back to `\s`.

## (i) Non-BMP characters

Calandria indexes text by code point; the reference by UTF-16 code unit, so an emoji or astral CJK
character occupies one position here and two there.

Calandria is correct. Surfaces as `boldRuns`/`html` divergences on a pair containing such
characters; a scoped allow entry citing (i) is the remedy.

## (j) Nested tables

Calandria (lxml) keeps a nested table's paragraphs inside the outer cell with the outer location;
the reference's non-greedy `<w:tbl>...</w:tbl>` / `<w:tc>...</w:tc>` regexes terminate on the INNER
closing tag and truncate the outer table.

Calandria is correct; a nested-table pair will fail the gate with the oracle wrong -- do not "fix"
Calandria to match.

# Layout (Plan 3)

The layout engine has no oracle: page counts are pinned by `tests/parity/golden-pages.json`
(our own output, regenerated deliberately with `harness/golden_pages.py`) and Word's page count
is a manual smoke check (`harness/word_pages.py`). Two model-level readings matter here:

## (k) Section break type is read from the section being closed

`w:sectPr/w:type` describes how the section it belongs to STARTS relative to the previous one
(ECMA-376 17.6.22). Both the parser and the reference read it as how the section ENDS -- the
paragraph carrying the sectPr sets the next paragraph's page break unless its own type is
continuous. The extraction gate pins `pageBreakBefore`, so the parser keeps the reference's
reading, and the layout groups page geometry the same way (a section whose predecessor closed
"continuous" flows on under the previous geometry). Only a document whose sections carry
different types is affected; none in the corpus does. Fixing it means moving the decision to a
post-pass over the sections and adding a scoped allow entry for the first pair that hits it.
`evenPage` and `oddPage` start the following paragraph on a new page like `nextPage`, but no
blank page is inserted to reach the requested parity -- page parity is not modelled.

## (l) Empty paragraphs and deleted empty paragraphs

Empty paragraphs of the revised document are laid out as one blank line each (their height is
the document default font's line height -- the paragraph mark's own run properties are not
modelled). Empty paragraphs that exist only in the original are not rendered: they are not diff
units, so nothing marks them deleted. Word shows a struck paragraph mark there.

## (m) Table borders, shading and vertical alignment

The page model carries cell boxes only. In v2.0.0 every sink draws the same uniform 0.5 pt grid
around every cell box (a `v_merge_continue` cell draws no top rule), no shading, and cells are
top-aligned. `w:tblBorders` / `w:tcBorders`, `w:shd` and `w:vAlign` are not modelled; when they
are, they will be added to `Cell` and `CellBox` so that both sinks keep reading one answer.
