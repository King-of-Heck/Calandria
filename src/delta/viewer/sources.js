// The two source cards (empty state) that become the compact source strip in the toolbar once
// a comparison exists: pick by click, drop one file onto a card, drop two onto anything, remove,
// swap, and the one Compare button. Both `.docx` and `.pdf` are accepted. The rule for Compare:
// enabled when both slots hold files and they are not exactly the pair of the current comparison.
// Every fill waits for Compare, a two-file drop included (v2.4.4: a drop never compares by
// itself). Swap re-runs at once when a comparison exists, because the sides only make sense
// together.
import { api, readBase64, state } from "./app.js";

const $ = (id) => document.getElementById(id);
const EMPTY = "Drop the .docx or .pdf here or click to choose";
const IDS = { a: { card: "cardA", input: "fileA", name: "nameA", clear: "clearA", tracked: "trackedA" },
              b: { card: "cardB", input: "fileB", name: "nameB", clear: "clearB", tracked: "trackedB" } };

let handlers = { compare: () => {}, swap: () => {} };

// What /api/inspect said about each slot's current file: null until it answers (or when it could
// not), then {kind, tracked, pages}. Compare never waits for it.
const info = { a: null, b: null };

async function inspect(slot, file) {
  try {
    const d = await api("/api/inspect", { name: file.name, data: await readBase64(file) });
    if (state.files[slot] !== file) return;       // the slot moved on (cleared, replaced or swapped)
    info[slot] = { kind: d.kind, tracked: d.tracked, pages: d.pages };
  } catch (e) {
    if (state.files[slot] !== file) return;
    info[slot] = null;                             // Compare reports a bad file itself
  }
  refreshSources();
}

function subline(i) {
  if (!i) return "";
  if (i.kind === "pdf") return `PDF · ${i.pages} page${i.pages === 1 ? "" : "s"} · text re-read from the pages`;
  return i.tracked ? `${i.tracked} tracked change${i.tracked === 1 ? "" : "s"}, compared as if accepted` : "";
}

export function initSources(h) {
  handlers = h;
  for (const slot of ["a", "b"]) {
    const ids = IDS[slot];
    const card = $(ids.card);
    const input = $(ids.input);
    card.addEventListener("click", (e) => {
      if (state.closed || e.target.closest("button")) return;
      input.click();
    });
    card.addEventListener("keydown", (e) => {
      if (e.key !== "Enter" && e.key !== " ") return;
      e.preventDefault();
      if (!state.closed) input.click();
    });
    input.addEventListener("change", (e) => {
      const file = e.target.files[0] || null;
      e.target.value = "";                            // the same file can be picked again after a remove
      if (file && !state.closed) setFile(slot, file);
    });
    $(ids.clear).addEventListener("click", (e) => { e.stopPropagation(); if (!state.closed) setFile(slot, null); });
    card.addEventListener("dragover", (e) => { e.preventDefault(); e.stopPropagation(); if (!state.closed) card.classList.add("over"); });
    card.addEventListener("dragleave", (e) => { if (!card.contains(e.relatedTarget)) card.classList.remove("over"); });
    card.addEventListener("drop", (e) => {
      e.preventDefault();
      e.stopPropagation();
      card.classList.remove("over");
      $("view").classList.remove("over");             // the drag crossed the pane row to reach the card
      takeDrop(e.dataTransfer.files, slot);
    });
  }
  const view = $("view");
  view.addEventListener("dragover", (e) => { e.preventDefault(); if (!state.closed) view.classList.add("over"); });
  view.addEventListener("dragleave", (e) => { if (!view.contains(e.relatedTarget)) view.classList.remove("over"); });
  view.addEventListener("drop", (e) => {
    e.preventDefault();
    view.classList.remove("over");
    takeDrop(e.dataTransfer.files, null);
  });
  $("swap").addEventListener("click", swap);
  $("compare").addEventListener("click", () => { if (!$("compare").disabled) handlers.compare(); });
  refreshSources();
}

function accepted(list) {
  return [...list].filter((f) => /\.(docx|pdf)$/i.test(f.name));
}

// `slot` is the card the files landed on, or null for a drop elsewhere on the page area.
function takeDrop(list, slot) {
  if (state.closed || state.busy) return;    // no drop while a request is in flight: a second compare could finish first
  const files = accepted(list);
  if (!files.length) return;
  if (files.length >= 2) { setFile("a", files[0]); setFile("b", files[1]); }
  else if (slot) setFile(slot, files[0]);
  else setFile(state.files.a ? "b" : "a", files[0]);
}

function setFile(slot, file) {
  state.files[slot] = file;
  info[slot] = null;
  refreshSources();
  if (file) inspect(slot, file);
}

function swap() {
  if (state.closed) return;
  [state.files.a, state.files.b] = [state.files.b, state.files.a];
  [info.a, info.b] = [info.b, info.a];
  refreshSources();
  if (state.data && state.files.a && state.files.b) handlers.swap();
}

function sameAsCompared() {
  const c = state.compared;
  return !!c && c.a === state.files.a && c.b === state.files.b;
}

export function refreshSources() {
  for (const slot of ["a", "b"]) {
    const ids = IDS[slot];
    const f = state.files[slot];
    $(ids.name).textContent = f ? f.name : EMPTY;
    $(ids.name).title = f ? f.name : "";
    $(ids.card).classList.toggle("filled", !!f);
    $(ids.clear).hidden = !f;
    const text = f ? subline(info[slot]) : "";
    $(ids.tracked).hidden = !text;
    $(ids.tracked).textContent = text;
  }
  const both = !!(state.files.a && state.files.b);
  $("swap").disabled = state.closed || state.busy || !(state.files.a || state.files.b);
  $("compare").disabled = state.closed || state.busy || !both || sameAsCompared();
  placeSources(!!state.data);
}

// The cards start in the page area (the empty state) and move into the toolbar as a second row
// once a comparison exists, so the page area holds pages only; the listeners travel with the nodes.
function placeSources(compact) {
  const src = $("sources");
  src.classList.toggle("compact", compact);
  const home = compact ? $("bar") : $("pages");
  if (src.parentElement === home) return;
  home.append(src);
}
