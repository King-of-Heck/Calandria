// The density strip beside the pages: one mark per numbered change at its position over the
// whole document, coloured by category; the current change's mark is bigger; filtered-out marks
// dim; a translucent band shows the part of the document on screen. The strip only listens to
// the change list's events and asks for a jump with calandria:goto — it never reads its state.
// Top level touches no DOM, so the pure markTop can be imported under node.

const $ = (id) => document.getElementById(id);

// Fraction of the document (0..1) at which a change sits: page index plus top over page height,
// over the page count. No zoom knowledge, no layout data.
export function markTop(anchor, pageH, pageCount) {
  return (anchor.page - 1 + anchor.top / pageH) / pageCount;
}

export function initStrip() {
  const strip = $("strip");
  const main = $("pages");
  const view = strip.querySelector(".view");
  let marks = new Map();                             // cid -> button

  const pageHeight = (page) => {
    const svg = $("pages").querySelector(`.page[data-page="${page}"] svg`);
    return svg ? Number(svg.getAttribute("viewBox").split(/\s+/)[3]) : null;
  };

  const build = (data) => {
    for (const b of marks.values()) b.remove();
    marks = new Map();
    const seen = new Set();
    for (const row of data.changes) {
      if (row.cid === null || row.cid === undefined || seen.has(row.cid)) continue;
      seen.add(row.cid);
      const a = data.anchors[String(row.cid)];
      const h = a ? pageHeight(a.page) : null;
      if (!a || !h) continue;
      const b = document.createElement("button");
      b.type = "button";
      b.className = `mark ${row.category}`;
      b.title = `Change ${row.cid} · p. ${a.page}`;
      b.style.top = `${(markTop(a, h, data.page_count) * 100).toFixed(3)}%`;
      b.addEventListener("click", () => document.dispatchEvent(new CustomEvent("calandria:goto", { detail: { cid: row.cid } })));
      strip.appendChild(b);
      marks.set(row.cid, b);
    }
    strip.hidden = marks.size === 0;
    viewport();
  };

  const viewport = () => {
    const total = main.scrollHeight || 1;
    view.style.top = `${(main.scrollTop / total * 100).toFixed(3)}%`;
    view.style.height = `${(main.clientHeight / total * 100).toFixed(3)}%`;
  };

  document.addEventListener("calandria:loaded", (e) => build(e.detail));
  document.addEventListener("calandria:filtered", (e) => {
    const on = new Set(e.detail.visible);
    for (const [cid, b] of marks) b.classList.toggle("dim", !on.has(cid));
  });
  document.addEventListener("calandria:selected", (e) => {
    for (const [cid, b] of marks) b.classList.toggle("current", cid === e.detail.cid);
  });
  main.addEventListener("scroll", viewport);
  window.addEventListener("resize", viewport);
  document.addEventListener("calandria:resized", viewport);
}
