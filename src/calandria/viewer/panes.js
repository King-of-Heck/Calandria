// The three views of a comparison (Original, Blackline, Modified) as independent toggles, each a
// pane in the #view row in that fixed order; Blackline alone is the default and the last pane on
// cannot be turned off. Marks tints the changed text of the side panes (a redraw request). The
// side panes hold pages drawn by the server exactly like the blackline's, without change marks;
// the blackline pane is #pages, unchanged. Nothing here scrolls: sync.js does that.
import { applyZoom, restyle, state } from "./app.js";

const $ = (id) => document.getElementById(id);
const SVG_NS = "http://www.w3.org/2000/svg";
export const SIDE_ORDER = ["original", "blackline", "modified"];
const BUTTON = { original: "viewOriginal", blackline: "viewBlackline", modified: "viewModified" };
const PANE = { original: "paneOriginal", blackline: "pages", modified: "paneModified" };

export function paneOf(side) {
  return $(PANE[side]);
}

// The visible panes, left to right.
export function visiblePanes() {
  return SIDE_ORDER.filter((s) => state.views[s]).map((s) => ({ side: s, el: paneOf(s) }));
}

// The pane the page status and a re-sync follow: the blackline when it is on, else the leftmost.
export function leadPane() {
  const v = visiblePanes();
  return v.find((p) => p.side === "blackline") || v[0];
}

// The sides a request asks the server to draw: the visible panes only (v2.4.3). A side is laid
// out and drawn on the server the first time a request names it, so a hidden pane costs nothing.
export function requestedSides() {
  return SIDE_ORDER.filter((s) => state.views[s]);
}

// A visible pane whose pages the current data does not carry (its side was hidden when the data
// was requested): the reason for a redraw request.
function missingSide() {
  return !!state.data && visiblePanes().some((p) => !state.data.sides[p.side]);
}

export function initPanes() {
  for (const side of SIDE_ORDER) $(BUTTON[side]).addEventListener("click", () => toggleView(side));
  $("viewMarks").addEventListener("click", toggleMarks);
  document.addEventListener("keydown", (e) => {
    if (state.closed || !state.data) return;
    if (e.target.matches("input, select, textarea") || e.ctrlKey || e.altKey || e.metaKey || $("keys").open || !$("rowMenu").hidden) return;
    if (e.key === "1") toggleView("original");
    else if (e.key === "2") toggleView("blackline");
    else if (e.key === "3") toggleView("modified");
    else if (e.key === "m") toggleMarks();
    else return;
    e.preventDefault();
  });
  applyPanes();
}

function toggleView(side) {
  if (state.busy) return;                          // a pane may need a request; one at a time
  if (state.closed || !state.data) return;
  if (state.views[side] && visiblePanes().length === 1) return;   // the last pane on stays on
  state.views[side] = !state.views[side];
  applyPanes();
}

function toggleMarks() {
  if (state.busy) return;
  if (state.closed || !state.data || $("viewMarks").disabled) return;
  state.marks = !state.marks;
  $("viewMarks").setAttribute("aria-pressed", String(state.marks));
  restyle();                                       // the side pages are drawn on the server
}

// Defaults for every new comparison (spec section 12.4).
export function resetPanes() {
  state.views = { original: false, blackline: true, modified: false };
  state.marks = false;
  $("viewMarks").setAttribute("aria-pressed", "false");
  applyPanes();
}

export function applyPanes() {
  for (const side of SIDE_ORDER) {
    const on = !!state.views[side];
    paneOf(side).hidden = !on;
    $(BUTTON[side]).setAttribute("aria-pressed", String(on));
  }
  const sides = state.views.original || state.views.modified;
  $("viewMarks").disabled = state.closed || !state.data || !sides;
  if (!sides) {
    // A disabled control must not read as pressed.
    state.marks = false;
    $("viewMarks").setAttribute("aria-pressed", "false");
  }
  // A redraw request when a visible pane has no pages yet, or the side panes are tinted the wrong
  // way; never while a request is in flight (a new comparison resets the panes before it shows).
  if (state.data && !state.busy && (missingSide() || (sides && state.data.side_marks !== state.marks))) restyle();
  $("view").classList.toggle("multi", visiblePanes().length > 1);
  if (state.data) applyZoom();
  document.dispatchEvent(new CustomEvent("calandria:panes", { detail: { views: { ...state.views } } }));
  document.dispatchEvent(new CustomEvent("calandria:resized"));
}

// The side panes' pages, from data.sides; the blackline's are app.js's renderPages. A side the
// data does not carry (hidden when it was requested) leaves its pane empty.
export function renderPanes() {
  for (const side of ["original", "modified"]) {
    const pane = paneOf(side);
    const keepScroll = pane.scrollTop;
    for (const p of pane.querySelectorAll(".page")) p.remove();
    const blk = state.data.sides[side];
    if (!blk) continue;
    blk.pages.forEach((svg, i) => {
      const page = document.createElement("div");
      page.className = "page";
      page.dataset.page = String(i + 1);
      page.innerHTML = svg;
      const n = document.createElement("div");
      n.className = "pagenum";
      n.textContent = `Page ${i + 1} of ${blk.page_count}`;
      page.appendChild(n);
      pane.appendChild(page);
    });
    pane.scrollTop = keepScroll;
  }
}

// The current change's row highlighted in every side pane: the row of its first changed row on
// that side (an inserted row has no place in Original and gets none there).
export function highlightSides(cid) {
  for (const side of ["original", "modified"]) {
    const pane = paneOf(side);
    for (const r of pane.querySelectorAll("rect.hl")) r.remove();
    if (cid === null || !state.data || !state.data.sides[side]) continue;
    const rows = state.data.sides[side].rows;
    const k = state.data.changes.findIndex((row, i) => row.cid === cid && rows[String(i)]);
    if (k < 0) continue;
    const a = rows[String(k)];
    const svg = pane.querySelector(`.page[data-page="${a.page}"] svg`);
    if (!svg) continue;
    const r = document.createElementNS(SVG_NS, "rect");
    r.setAttribute("class", "hl");
    r.setAttribute("x", "0");
    r.setAttribute("y", String(a.top));
    r.setAttribute("width", svg.getAttribute("viewBox").split(/\s+/)[2]);
    r.setAttribute("height", String(a.height));
    svg.insertBefore(r, svg.firstChild);
  }
}
