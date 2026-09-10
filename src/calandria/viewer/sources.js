// The two source cards (empty state) that become the compact source strip above the pages once
// a comparison exists: pick by click, drop one file onto a card, drop two onto anything, remove,
// swap, and the one Compare button. The rule for Compare: enabled when both slots hold files and
// they are not exactly the pair of the current comparison. A two-file drop before any comparison
// compares at once (the first-use path); every other fill waits for Compare. Swap re-runs at
// once when a comparison exists, because the sides only make sense together.
import { state } from "./app.js";

const $ = (id) => document.getElementById(id);
const EMPTY = "Drop the .docx here or click to choose";
const IDS = { a: { card: "cardA", input: "fileA", name: "nameA", clear: "clearA" },
              b: { card: "cardB", input: "fileB", name: "nameB", clear: "clearB" } };

let handlers = { compare: () => {}, swap: () => {} };

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
      if (file) setFile(slot, file);
    });
    $(ids.clear).addEventListener("click", (e) => { e.stopPropagation(); if (!state.closed) setFile(slot, null); });
    card.addEventListener("dragover", (e) => { e.preventDefault(); e.stopPropagation(); if (!state.closed) card.classList.add("over"); });
    card.addEventListener("dragleave", () => card.classList.remove("over"));
    card.addEventListener("drop", (e) => {
      e.preventDefault();
      e.stopPropagation();
      card.classList.remove("over");
      takeDrop(e.dataTransfer.files, slot);
    });
  }
  const main = $("pages");
  main.addEventListener("dragover", (e) => { e.preventDefault(); if (!state.closed) main.classList.add("over"); });
  main.addEventListener("dragleave", () => main.classList.remove("over"));
  main.addEventListener("drop", (e) => {
    e.preventDefault();
    main.classList.remove("over");
    takeDrop(e.dataTransfer.files, null);
  });
  $("swap").addEventListener("click", swap);
  $("compare").addEventListener("click", () => { if (!$("compare").disabled) handlers.compare(); });
  refreshSources();
}

function docxOnly(list) {
  return [...list].filter((f) => /\.docx$/i.test(f.name));
}

// `slot` is the card the files landed on, or null for a drop elsewhere on the page area.
function takeDrop(list, slot) {
  if (state.closed) return;
  const files = docxOnly(list);
  if (!files.length) return;
  const before = !state.data;
  if (files.length >= 2) { setFile("a", files[0]); setFile("b", files[1]); }
  else if (slot) setFile(slot, files[0]);
  else setFile(state.files.a ? "b" : "a", files[0]);
  if (before && files.length >= 2 && state.files.a && state.files.b) handlers.compare();
}

function setFile(slot, file) {
  state.files[slot] = file;
  refreshSources();
}

function swap() {
  if (state.closed) return;
  [state.files.a, state.files.b] = [state.files.b, state.files.a];
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
  }
  const both = !!(state.files.a && state.files.b);
  $("swap").disabled = state.closed || !(state.files.a || state.files.b);
  $("compare").disabled = state.closed || state.busy || !both || sameAsCompared();
  $("sources").classList.toggle("compact", !!state.data);
}
