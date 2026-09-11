// Synchronised scrolling between the panes, by content: the comparison row at the top of the
// pane the user scrolls is put at the top of every other visible pane, at the same fraction of
// its height (spec §12.5). Each pane has an index of its rows in pane pixels, rebuilt after a
// zoom, a changed-pages toggle or new data. A follower's own programmatic scroll is recognised
// by the value that was set (lastSet) and never leads. Top level touches no DOM, so the pure
// functions load under node.

const $ = (id) => document.getElementById(id);
const CAPTION = 0;                    // the captions are sticky inside the scroll box; no offset to subtract
const SIDES = ["original", "blackline", "modified"];
const PANE = { original: "paneOriginal", blackline: "pages", modified: "paneModified" };

// rows: {row_index: {page, top, height}} (points, from the payload); pageTop(page) -> pane pixel
// top of that page's element, or null when the page is hidden; scale: CSS px per pt for the pane,
// either one number for the whole pane or a function (page) => pxPerPt when Fit gives every page
// its own scale (a landscape page fits smaller). Returns [{row, top, height}] in pane pixels,
// sorted by top (row order).
export function buildIndex(rows, pageTop, scale) {
  const out = [];
  for (const k of Object.keys(rows)) {
    const r = rows[k];
    const pt = pageTop(r.page);
    if (pt === null || pt === undefined) continue;
    const sc = typeof scale === "function" ? scale(r.page) : scale;
    out.push({ row: Number(k), top: pt + r.top * sc, height: r.height * sc });
  }
  out.sort((a, b) => a.top - b.top || a.row - b.row);
  return out;
}

// The position in the index of the last entry whose top <= y (binary search); -1 above the first.
export function rowAt(index, y) {
  let lo = 0, hi = index.length - 1, ans = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (index[mid].top <= y) { ans = mid; lo = mid + 1; } else hi = mid - 1;
  }
  return ans;
}

// The scrollTop that puts row k at the top, f of its height down. A row this side does not have
// (an inserted paragraph seen from Original) resolves to the END of the nearest earlier row it
// has: that boundary is where the missing text would sit. 0 when nothing is at or before k.
export function follow(index, k, f) {
  let lo = 0, hi = index.length - 1, ans = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (index[mid].row <= k) { ans = mid; lo = mid + 1; } else hi = mid - 1;
  }
  if (ans < 0) return 0;
  const e = index[ans];
  return Math.round(e.row === k ? e.top + f * e.height : e.top + e.height);
}

const indexes = {};                   // side -> [{row, top, height}]
const lastSet = {};                   // side -> the scrollTop this module last wrote there
let data = null;
let views = null;

function pageTopIn(pane) {
  return (page) => {
    const el = pane.querySelector(`.page[data-page="${page}"]`);
    return el && !el.hidden ? el.offsetTop : null;
  };
}

export function refreshSync() {
  if (!data) return;
  for (const side of SIDES) {
    const pane = $(PANE[side]);
    // dataset.scale is a zoom factor per page (Fit gives each its own); pixels per pt = zoom * 4/3
    const scale = (page) => {
      const el = pane.querySelector(`.page[data-page="${page}"]`);
      return (el ? Number(el.dataset.scale) : 1) * (4 / 3);
    };
    indexes[side] = buildIndex(data.sides[side].rows, pageTopIn(pane), scale);
  }
}

function visible() {
  return SIDES.filter((s) => views && views[s]);
}

// Align every other visible pane to `side` as it stands now.
export function syncFrom(side) {
  if (!data || !views || !views[side]) return;
  const lead = $(PANE[side]);
  const ix = indexes[side] || [];
  const i = rowAt(ix, lead.scrollTop + CAPTION);
  const k = i < 0 ? -1 : ix[i].row;
  const f = i < 0 ? 0 : Math.max(0, Math.min(1, (lead.scrollTop + CAPTION - ix[i].top) / (ix[i].height || 1)));
  for (const other of visible()) {
    if (other === side) continue;
    const pane = $(PANE[other]);
    const top = k < 0 ? 0 : follow(indexes[other] || [], k, f) - CAPTION;
    // The browser clamps scrollTop to [0, scrollHeight - clientHeight]; if we don't clamp our own
    // record the same way, an over-long target leaves lastSet different from the real scrollTop
    // and the pane's own scroll event reads back as if the user had scrolled it (a feedback path).
    lastSet[other] = Math.max(0, Math.min(top, pane.scrollHeight - pane.clientHeight));
    pane.scrollTop = lastSet[other];
  }
}

function onScroll(side) {
  return () => {
    const pane = $(PANE[side]);
    if (lastSet[side] !== undefined && Math.abs(pane.scrollTop - lastSet[side]) < 1) return;   // our own write, not a lead
    lastSet[side] = undefined;
    syncFrom(side);
  };
}

export function initSync() {
  for (const side of SIDES) $(PANE[side]).addEventListener("scroll", onScroll(side));
  document.addEventListener("calandria:loaded", (e) => { data = e.detail; refreshSync(); });
  document.addEventListener("calandria:restyled", refreshSync);
  document.addEventListener("calandria:panes", (e) => {
    views = e.detail.views;
    refreshSync();
    const lead = views.blackline ? "blackline" : visible()[0];
    if (lead) syncFrom(lead);
  });
  document.addEventListener("calandria:resized", () => {
    refreshSync();
    const v = visible();
    const lead = views && views.blackline ? "blackline" : v[0];
    if (lead) syncFrom(lead);
  });
}
