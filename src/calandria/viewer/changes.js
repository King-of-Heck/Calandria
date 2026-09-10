// The change list panel: summary tiles that filter (click to solo a category, again for all),
// the location select, the numbered list with the change text styled like the page (two lines
// per row, the selected row in full), navigation from the toolbar and the keys, and the on-page
// highlight of the selected change (a translucent band over every line and changed table row
// carrying its number).
import { pageSize } from "./app.js";

const $ = (id) => document.getElementById(id);
const SVG_NS = "http://www.w3.org/2000/svg";
const CONTEXT = 40;                   // characters of unchanged text kept on each side of a change (selected row)
const CONTEXT_SHORT = 24;             // the same for the clamped rows
const MAX_SEGMENT = 200;              // characters of one inserted / deleted segment shown
const BADGE = { insertion: "Add", deletion: "Delete", amendment: "Change", numbering: "Number" };
const TILES = [["Insertions", "insertions", "insertion"], ["Deletions", "deletions", "deletion"],
               ["Amendments", "amendments", "amendment"], ["Numbering", "numbering", "numbering"]];

let data = null;
let entries = [];                     // every numbered change, document order
let visible = [];                     // after the filters
let current = -1;                     // index into visible
let solo = null;                      // the one category shown, or null for all
let hasTables = false;                // any change inside a table (the table glyph is shown only then)

export function initChanges() {
  document.addEventListener("calandria:loaded", (e) => { data = e.detail; build(); });
  document.addEventListener("calandria:restyled", () => highlight(current));
  $("fLocation").addEventListener("change", refilter);
  $("tiles").addEventListener("click", (e) => {
    const t = e.target.closest("button.tile");
    if (!t) return;
    solo = solo === t.dataset.cat ? null : t.dataset.cat;
    refilter();
  });
  $("navFirst").addEventListener("click", () => go(0));
  $("navPrev").addEventListener("click", () => go(current - 1));
  $("navNext").addEventListener("click", () => go(current + 1));
  $("navLast").addEventListener("click", () => go(visible.length - 1));
  $("goto").addEventListener("change", (e) => {
    const n = Number(e.target.value);
    const i = visible.findIndex((en) => en.cid === n);
    if (i >= 0) go(i);
    e.target.value = "";
  });
  document.addEventListener("keydown", (e) => {
    if (e.target.matches("input, select, textarea") || e.ctrlKey || e.altKey || e.metaKey || $("keys").open) return;
    if (e.key === "n" || e.key === "j" || e.key === "ArrowRight") go(current + 1);
    else if (e.key === "p" || e.key === "k" || e.key === "ArrowLeft") go(current - 1);
    else if (e.key === "Home") go(0);
    else if (e.key === "End") go(visible.length - 1);
    else return;
    e.preventDefault();
  });
  initPanel();
}

// The panel folds to a narrow rail; the choice survives a restart (localStorage is per origin,
// and the origin is fixed at 127.0.0.1:<port>, so it may or may not be found again - harmless).
function initPanel() {
  const panel = $("panel");
  const btn = $("panelToggle");
  let collapsed = false;
  try { collapsed = localStorage.getItem("calandria.panel") === "collapsed"; } catch (e) { /* storage off */ }
  const apply = () => {
    panel.classList.toggle("collapsed", collapsed);
    btn.textContent = collapsed ? "›" : "‹";
    btn.title = collapsed ? "Show the change list" : "Hide the change list";
    btn.setAttribute("aria-expanded", String(!collapsed));
    document.dispatchEvent(new CustomEvent("calandria:resized"));
  };
  btn.addEventListener("click", () => {
    collapsed = !collapsed;
    try { localStorage.setItem("calandria.panel", collapsed ? "collapsed" : "open"); } catch (e) { /* storage off */ }
    apply();
  });
  apply();
}

function build() {
  entries = group(data.changes);
  hasTables = entries.some((en) => en.loc === "table");
  solo = null;
  tiles();
  refilter();
}

function group(rows) {
  const byCid = new Map();
  for (const row of rows) {
    if (row.cid === null || row.cid === undefined) continue;
    if (!byCid.has(row.cid)) {
      const a = data.anchors[String(row.cid)];
      byCid.set(row.cid, { cid: row.cid, category: row.category, loc: row.loc ? "table" : "body", page: a ? a.page : null, rows: [] });
    }
    byCid.get(row.cid).rows.push(row);
  }
  return [...byCid.values()];
}

function tiles() {
  const s = data.summary;
  $("tiles").innerHTML = TILES.map(([label, key, cat]) =>
    `<button type="button" class="tile ${cat}" data-cat="${cat}" aria-pressed="false" ` +
    `title="Show only ${label.toLowerCase()}; click again for all"><b>${s[key]}</b><span>${label}</span></button>`).join("") +
    `<div class="tile formatting" title="Formatting changes are shown on the page but not counted or listed">` +
    `<b>${s.formatting}</b><span>Formatting · shown, not counted</span></div>`;
}

function markTiles() {
  for (const t of $("tiles").querySelectorAll("button.tile")) {
    const on = solo === t.dataset.cat;
    t.setAttribute("aria-pressed", String(on));
    t.classList.toggle("on", on);
    t.classList.toggle("dim", solo !== null && !on);
  }
  $("tiles").querySelector(".tile.formatting").classList.toggle("dim", solo !== null);
}

function refilter() {
  const loc = $("fLocation").value;
  visible = entries.filter((en) => (solo === null || en.category === solo) && (loc === "all" || en.loc === loc));
  current = -1;
  markTiles();
  renderList();
  highlight(-1);
  status();
}

function esc(s) {
  return String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

function keepEnd(t, n) { return t.length > n ? "…" + t.slice(-n) : t; }
function keepStart(t, n) { return t.length > n ? t.slice(0, n) + "…" : t; }

function changeText(en, context) {
  const parts = [];
  for (const row of en.rows) {
    if (row.num_changed && row.old_marker !== null && row.old_marker !== undefined) {
      parts.push(`<s class="del">${esc(row.old_marker)}</s> <u class="ins">${esc(row.marker || "")}</u> `);
    }
    const segs = row.segments;
    let first = -1, last = -1;
    segs.forEach((s, i) => { if (s.m !== "eq") { if (first < 0) first = i; last = i; } });
    segs.forEach((s, i) => {
      let t = s.t;
      if (s.m === "eq") {
        if (first < 0 || i > last) t = keepStart(t, context);
        else if (i < first) t = keepEnd(t, context);
      } else {
        t = keepStart(t, MAX_SEGMENT);
      }
      parts.push(s.m === "del" ? `<s class="del">${esc(t)}</s>` : s.m === "ins" ? `<u class="ins">${esc(t)}</u>` : esc(t));
    });
    parts.push(" ");
  }
  return parts.join("");
}

function renderList() {
  const ol = $("changes");
  ol.innerHTML = "";
  ol.classList.toggle("tables", hasTables);
  visible.forEach((en, i) => {
    const li = document.createElement("li");
    li.className = en.category;
    li.dataset.i = String(i);
    li.tabIndex = i === 0 ? 0 : -1;                // one tab stop: the first row until one is selected
    li.innerHTML = `<span class="badge">${BADGE[en.category] || en.category}</span><span class="no">${en.cid}</span>` +
                   `<span class="pg" title="Page">${en.page === null ? "" : "p. " + en.page}</span>` +
                   (hasTables ? `<span class="tbl" title="${en.loc === "table" ? "In a table" : ""}">${en.loc === "table" ? "⊞" : ""}</span>` : "") +
                   `<span class="text">${changeText(en, CONTEXT_SHORT)}</span>`;
    li.addEventListener("click", () => go(i));
    li.addEventListener("keydown", (e) => { if (e.key === "Enter") go(i); });
    ol.appendChild(li);
  });
  $("listCount").textContent = !entries.length ? "No changes" :
    visible.length === entries.length ? `${entries.length} changes` : `${visible.length} of ${entries.length} changes`;
}

function status() {
  const el = $("changeStatus");
  if (!data) { el.textContent = ""; return; }
  if (!visible.length) el.textContent = entries.length ? "No changes match the filters" : "No changes";
  else el.textContent = current >= 0 ? `Change ${current + 1} of ${visible.length}` : `${visible.length} changes`;
}

function go(i) {
  if (!visible.length) return;
  i = Math.max(0, Math.min(visible.length - 1, i));
  const ol = $("changes");
  const was = ol.querySelector("li.current");
  if (was && Number(was.dataset.i) !== i) was.querySelector(".text").innerHTML = changeText(visible[Number(was.dataset.i)], CONTEXT_SHORT);
  const focusInList = ol.contains(document.activeElement);
  current = i;
  highlight(i);
  status();
  for (const li of ol.querySelectorAll("li")) {
    const on = Number(li.dataset.i) === i;
    li.classList.toggle("current", on);
    li.tabIndex = on ? 0 : -1;                       // the list is one tab stop: the current row
  }
  const li = ol.querySelector(`li[data-i="${i}"]`);
  if (li) {
    li.querySelector(".text").innerHTML = changeText(visible[i], CONTEXT);   // the selected row shows the full text
    li.scrollIntoView({ block: li.offsetHeight > ol.clientHeight ? "start" : "nearest" });
    if (focusInList) li.focus({ preventScroll: true });   // the keys move the focus with the selection
  }
  const a = data.anchors[String(visible[i].cid)];
  if (!a) return;
  const page = document.querySelector(`.page[data-page="${a.page}"]`);
  if (!page) return;
  const svg = page.querySelector("svg");
  const scale = svg.getBoundingClientRect().height / pageSize(svg).h;
  $("pages").scrollTo({ top: page.offsetTop + a.top * scale - 80, behavior: "smooth" });
}

function highlight(i) {
  for (const r of document.querySelectorAll("rect.hl")) r.remove();
  if (i < 0 || !visible[i] || !data) return;
  const cid = visible[i].cid;
  for (const [page, top, height, cids] of data.marks) {
    if (!cids.includes(cid)) continue;
    const svg = document.querySelector(`.page[data-page="${page}"] svg`);
    if (!svg) continue;
    const r = document.createElementNS(SVG_NS, "rect");
    r.setAttribute("class", "hl");
    r.setAttribute("x", "0");
    r.setAttribute("y", String(top));
    r.setAttribute("width", String(pageSize(svg).w));
    r.setAttribute("height", String(height));
    svg.insertBefore(r, svg.firstChild);
  }
}
