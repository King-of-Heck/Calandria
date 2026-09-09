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
