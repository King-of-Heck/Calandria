// Calandria viewer: loads two .docx files, shows the server's page drawings, restyles them by
// rendering set, zooms, downloads the PDF, and keeps the session alive. The change list lives
// in changes.js and listens for the events dispatched here.
import { initChanges } from "./changes.js";

const $ = (id) => document.getElementById(id);
const PING_MS = 15000;
const PING_MISSES = 3;                              // a single dropped ping is not a dead server
const PT = 4 / 3;                                   // CSS px per pt
const OPTION_IDS = ["optIgnoreCase", "optCountNumbering", "hideUnchanged", "hideInsertions", "hideDeletions", "hideFormatting"];

export const state = {
  data: null, files: { a: null, b: null }, zoom: 1, fit: false,
  renderSet: "Standard", changeBars: true, closed: false, timer: null,
  // Every server round trip that changes what is on screen takes a ticket; a reply whose ticket
  // is no longer the current one lost the race (a second option toggled while the first was in
  // flight) and is dropped, so the page always shows the answer to the LAST request.
  seq: 0, misses: 0,
};

export async function api(path, body) {
  const init = body === undefined ? {} :
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  let r;
  try { r = await fetch(path, init); } catch (e) { throw new Error("Calandria is not running"); }
  const text = await r.text();
  let json = null;
  try { json = JSON.parse(text); } catch (e) { /* not JSON */ }
  if (!r.ok) throw new Error((json && json.error) || `${r.status} ${r.statusText}`);
  return json;
}

export function pageSize(svg) {
  const [, , w, h] = svg.getAttribute("viewBox").split(/\s+/).map(Number);
  return { w, h };
}

function msg(text, isError) {
  const m = $("msg");
  m.textContent = text || "";
  m.classList.toggle("error", !!isError);
}

function busy(on, text) {
  document.body.classList.toggle("busy", on);
  msg(on ? text : "");
}

function readBase64(file) {
  return new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = () => resolve(String(fr.result).split(",")[1]);
    fr.onerror = () => reject(fr.error);
    fr.readAsDataURL(file);
  });
}

function setFile(slot, file) {
  state.files[slot] = file;
  $(slot === "a" ? "nameA" : "nameB").textContent = file ? file.name : "none";
  $("compare").disabled = !(state.files.a && state.files.b) || state.closed;
}

function options() {
  return {
    ignore_case: $("optIgnoreCase").checked, count_numbering: $("optCountNumbering").checked,
    show_equal: !$("hideUnchanged").checked, show_insertions: !$("hideInsertions").checked,
    show_deletions: !$("hideDeletions").checked, show_formatting: !$("hideFormatting").checked,
  };
}

function setOptions(o) {
  $("optIgnoreCase").checked = o.ignore_case;
  $("optCountNumbering").checked = o.count_numbering;
  $("hideUnchanged").checked = !o.show_equal;
  $("hideInsertions").checked = !o.show_insertions;
  $("hideDeletions").checked = !o.show_deletions;
  $("hideFormatting").checked = !o.show_formatting;
}

async function compareNow() {
  const { a, b } = state.files;
  if (!a || !b || state.closed) return;
  const seq = ++state.seq;
  busy(true, "Comparing…");
  try {
    const body = { a: { name: a.name, data: await readBase64(a) }, b: { name: b.name, data: await readBase64(b) },
                   options: options(), render_set: state.renderSet, change_bars: state.changeBars };
    const d = await api("/api/compare", body);
    if (state.seq !== seq) return;
    show(d);
  } catch (e) {
    msg(e.message, true);
  } finally {
    if (state.seq === seq) busy(false);   // a superseded reply must not clear the newer one's status
  }
}

export async function relayout() {
  if (!state.data || state.closed) return;
  const seq = ++state.seq;
  busy(true, "Laying out…");
  try {
    const d = await api("/api/layout", { options: options(), render_set: state.renderSet, change_bars: state.changeBars });
    if (state.seq !== seq) return;
    show(d);
  } catch (e) {
    msg(e.message, true);
  } finally {
    if (state.seq === seq) busy(false);   // a superseded reply must not clear the newer one's status
  }
}

async function restyle() {
  if (!state.data || state.closed) return;
  const seq = ++state.seq;
  busy(true, "Redrawing…");
  try {
    const q = `render_set=${encodeURIComponent(state.renderSet)}&change_bars=${state.changeBars ? 1 : 0}`;
    const d = await api(`/api/pages?${q}`);
    if (state.seq !== seq) return;
    Object.assign(state.data, { pages: d.pages, report_lines: d.report_lines, render_set: d.render_set, change_bars: d.change_bars });
    renderPages();
    applyStyles();
    document.dispatchEvent(new CustomEvent("calandria:restyled"));
  } catch (e) {
    msg(e.message, true);
  } finally {
    if (state.seq === seq) busy(false);   // a superseded reply must not clear the newer one's status
  }
}

function show(data) {
  state.data = data;
  const sel = $("renderSet");
  sel.innerHTML = "";
  for (const name of data.render_sets) {
    const o = document.createElement("option");
    o.value = o.textContent = name;
    sel.appendChild(o);
  }
  state.renderSet = data.render_set;
  state.changeBars = data.change_bars;
  sel.value = data.render_set;
  $("changeBars").checked = data.change_bars;
  setOptions(data.options);
  $("pdf").disabled = false;
  $("drop").hidden = true;
  document.title = `${data.names.original} vs ${data.names.modified} — Calandria`;
  renderPages();
  applyStyles();
  msg("");
  document.dispatchEvent(new CustomEvent("calandria:loaded", { detail: data }));
}

function renderPages() {
  const main = $("pages");
  const keepScroll = main.scrollTop;
  for (const p of main.querySelectorAll(".page")) p.remove();
  state.data.pages.forEach((svg, i) => {
    const page = document.createElement("div");
    page.className = "page";
    page.dataset.page = String(i + 1);
    page.innerHTML = svg;
    const n = document.createElement("div");
    n.className = "pagenum";
    n.textContent = `Page ${i + 1} of ${state.data.page_count}`;
    page.appendChild(n);
    main.appendChild(page);
  });
  applyZoom();
  main.scrollTop = keepScroll;
  updatePageStatus();
}

function applyZoom() {
  const main = $("pages");
  for (const page of main.querySelectorAll(".page")) {
    const svg = page.querySelector("svg");
    const { w, h } = pageSize(svg);
    const z = state.fit ? Math.max(0.2, (main.clientWidth - 48) / (w * PT)) : state.zoom;
    svg.setAttribute("width", `${w * z}pt`);
    svg.setAttribute("height", `${h * z}pt`);
    page.style.width = `${w * z}pt`;
  }
}

function applyStyles() {
  const rs = state.data.render_set_styles[state.renderSet];
  if (!rs) return;
  const root = document.documentElement.style;
  root.setProperty("--ins", "#" + rs.insert.color);
  root.setProperty("--del", "#" + rs.delete.color);
  root.setProperty("--fmt", "#" + rs.formatting.color);
}

function updatePageStatus() {
  if (!state.data) {
    $("pageStatus").textContent = "No comparison";
    return;
  }
  const main = $("pages");
  const top = main.getBoundingClientRect().top + 8;
  let current = 1;
  for (const p of main.querySelectorAll(".page")) {
    if (p.getBoundingClientRect().top <= top) current = Number(p.dataset.page);
    else break;
  }
  $("pageStatus").textContent = `Page ${current} of ${state.data.page_count}`;
}

function savePdf() {
  const q = `render_set=${encodeURIComponent(state.renderSet)}&change_bars=${state.changeBars ? 1 : 0}&report=${$("report").value}`;
  window.location.href = `/api/pdf?${q}`;
}

function closed(text) {
  state.closed = true;
  clearInterval(state.timer);
  document.body.classList.add("closed");
  for (const el of document.querySelectorAll("button, input, select")) el.disabled = true;
  msg(text, true);
}

async function quit() {
  try { await api("/api/quit", {}); } catch (e) { /* already gone */ }
  closed("Calandria has quit. You can close this tab.");
}

function ping() {
  fetch("/api/ping", { method: "POST" })
    .then((r) => { if (!r.ok) throw new Error(); state.misses = 0; })
    .catch(() => {
      // One lost ping is a hiccup (a sleeping laptop, a busy server); three in a row is a server
      // that has gone, and only then does the page shut itself down.
      if (++state.misses >= PING_MISSES) {
        closed("Calandria is no longer running (it stops after a while without this page). Double-click Calandria.cmd to start it again.");
      }
    });
}

function wire() {
  $("fileA").addEventListener("change", (e) => setFile("a", e.target.files[0] || null));
  $("fileB").addEventListener("change", (e) => setFile("b", e.target.files[0] || null));
  $("compare").addEventListener("click", compareNow);
  const main = $("pages");
  main.addEventListener("dragover", (e) => { e.preventDefault(); main.classList.add("over"); });
  main.addEventListener("dragleave", () => main.classList.remove("over"));
  main.addEventListener("drop", (e) => {
    e.preventDefault();
    main.classList.remove("over");
    if (state.closed) return;
    const files = [...e.dataTransfer.files].filter((f) => /\.docx$/i.test(f.name));
    if (files.length >= 2) { setFile("a", files[0]); setFile("b", files[1]); }
    else if (files.length === 1) setFile(state.files.a ? "b" : "a", files[0]);
    if (state.files.a && state.files.b) compareNow();
  });
  for (const id of OPTION_IDS) $(id).addEventListener("change", relayout);
  $("renderSet").addEventListener("change", (e) => { state.renderSet = e.target.value; restyle(); });
  $("changeBars").addEventListener("change", (e) => { state.changeBars = e.target.checked; restyle(); });
  $("zoom").addEventListener("change", (e) => {
    state.fit = e.target.value === "fit";
    if (!state.fit) state.zoom = Number(e.target.value);
    applyZoom();
  });
  window.addEventListener("resize", () => { if (state.fit) applyZoom(); });
  main.addEventListener("scroll", updatePageStatus);
  $("pdf").addEventListener("click", savePdf);
  $("quit").addEventListener("click", quit);
  state.timer = setInterval(ping, PING_MS);
  initChanges();
}

wire();
