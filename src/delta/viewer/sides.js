// The three sides of a comparison as the viewer knows them: their order left to right and the
// element of each one's pane. Declared once, for panes.js and sync.js; no imports and no DOM at
// the top level, so it loads under node with the pure modules.
export const SIDE_ORDER = ["original", "blackline", "modified"];
export const PANE = { original: "paneOriginal", blackline: "pages", modified: "paneModified" };
