// The change list panel: summary tiles, category and location filters, the numbered list with
// the change text styled like the page, navigation, and the on-page highlight of the selected
// change (a translucent band over every line and changed table row carrying its number).
import { pageSize } from "./app.js";

const $ = (id) => document.getElementById(id);
const SVG_NS = "http://www.w3.org/2000/svg";
const CONTEXT = 40;                   // characters of unchanged text kept on each side of a change
const MAX_SEGMENT = 200;              // characters of one inserted / deleted segment shown
const BADGE = { insertion: "Add", deletion: "Delete", amendment: "Change", numbering: "Number" };
const FILTER_IDS = { insertion: "fInsertion", deletion: "fDeletion", amendment: "fAmendment", numbering: "fNumbering" };

let data = null;
let entries = [];                     // every numbered change, document order
let visible = [];                     // after the filters
let current = -1;                     // index into visible

export function initChanges() {
  document.addEventListener("calandria:loaded", (e) => { data = e.detail; build(); });
  document.addEventListener("calandria:restyled", () => highlight(current));
  for (const id of [...Object.values(FILTER_IDS), "fLocation"]) $(id).addEventListener("change", refilter);
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
    if (e.target.matches("input, select, textarea") || e.ctrlKey || e.altKey || e.metaKey) return;
    if (e.key === "n" || e.key === "j" || e.key === "ArrowRight") go(current + 1);
    else if (e.key === "p" || e.key === "k" || e.key === "ArrowLeft") go(current - 1);
    else if (e.key === "Home") go(0);
    else if (e.key === "End") go(visible.length - 1);
    else return;
    e.preventDefault();
  });
}

function build() {
  entries = group(data.changes);
  tiles();
  refilter();
}

function group(rows) {
  const byCid = new Map();
  for (const row of rows) {
    if (row.cid === null || row.cid === undefined) continue;
    if (!byCid.has(row.cid)) byCid.set(row.cid, { cid: row.cid, category: row.category, loc: row.loc ? "table" : "body", rows: [] });
    byCid.get(row.cid).rows.push(row);
  }
  return [...byCid.values()];
}

function tiles() {
  const s = data.summary;
  const cells = [["Insertions", s.insertions, "insertion"], ["Deletions", s.deletions, "deletion"],
                 ["Amendments", s.amendments, "amendment"], ["Numbering", s.numbering, "numbering"],
                 ["Total", s.total, "total"], ["Formatting", s.formatting, "formatting"]];
  $("tiles").innerHTML = cells.map(([label, n, cls]) =>
    `<div class="tile ${cls}" title="${cls === "formatting" ? "Formatting changes are shown but not counted" : ""}"><b>${n}</b><span>${label}</span></div>`).join("");
}

function refilter() {
  const loc = $("fLocation").value;
  visible = entries.filter((en) => $(FILTER_IDS[en.category]).checked && (loc === "all" || en.loc === loc));
  current = -1;
  renderList();
  highlight(-1);
  status();
}

function esc(s) {
  return String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

function keepEnd(t) { return t.length > CONTEXT ? "…" + t.slice(-CONTEXT) : t; }
function keepStart(t, n) { return t.length > n ? t.slice(0, n) + "…" : t; }

function changeText(en) {
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
        if (first < 0 || i > last) t = keepStart(t, CONTEXT);
        else if (i < first) t = keepEnd(t);
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
  visible.forEach((en, i) => {
    const li = document.createElement("li");
    li.className = en.category;
    li.dataset.i = String(i);
    li.innerHTML = `<span class="badge">${BADGE[en.category] || en.category}</span><span class="no">${en.cid}</span>` +
                   `<span class="loc">${en.loc === "table" ? "Table" : "Body"}</span><span class="text">${changeText(en)}</span>`;
    li.addEventListener("click", () => go(i));
    ol.appendChild(li);
  });
  $("listCount").textContent = entries.length ? `${visible.length} of ${entries.length}` : "";
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
  current = i;
  highlight(i);
  status();
  const ol = $("changes");
  for (const li of ol.querySelectorAll("li")) li.classList.toggle("current", Number(li.dataset.i) === i);
  const li = ol.querySelector(`li[data-i="${i}"]`);
  if (li) li.scrollIntoView({ block: "nearest" });
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
