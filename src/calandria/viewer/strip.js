// The density strip beside the pages: one mark per passage at its position in the pane's
// scroll, coloured by category; the current change's mark is bigger; filtered-out marks dim; a
// translucent band shows the part of the document on screen. Marks and band sit on the same
// track as the pane's scrollbar thumb (the strip's height less the arrow button at each end and
// the horizontal scrollbar at the bottom), so a mark lines up with the thumb when its change is
// on screen. The strip only listens to the change list's events and asks for a jump with
// calandria:goto — it never reads its state. Top level touches no DOM, so the pure track and
// markTop can be imported under node.

const $ = (id) => document.getElementById(id);
const PT = 4 / 3;                                    // CSS px per pt

// The scrollbar's track within the strip: below the top arrow button (as tall as the scrollbar
// is wide; an overlay scrollbar has neither width nor buttons) and above the bottom one and the
// horizontal scrollbar. {top, len} in px.
export function track(stripH, scrollbarW, scrollbarH) {
  return { top: scrollbarW, len: Math.max(1, stripH - scrollbarH - 2 * scrollbarW) };
}

// Where on the track a point y px down the pane's scroll (of scrollHeight total) sits.
export function markTop(y, scrollHeight, tr) {
  return tr.top + (y / Math.max(1, scrollHeight)) * tr.len;
}

export function initStrip() {
  const strip = $("strip");
  const main = $("pages");
  const view = strip.querySelector(".view");
  let marks = new Map();                             // cid -> {button, anchor}

  const theTrack = () => track(strip.clientHeight, main.offsetWidth - main.clientWidth,
                               main.offsetHeight - main.clientHeight);

  // A change's position down the pane's scroll: its page's offset plus its top on the page at
  // the page's zoom. A page that is hidden (changed pages only) or not built has no position.
  const scrollY = (a) => {
    const page = main.querySelector(`.page[data-page="${a.page}"]`);
    if (!page || page.hidden) return null;
    return page.offsetTop + a.top * (Number(page.dataset.scale) || 1) * PT;
  };

  const place = () => {
    const tr = theTrack();
    const total = main.scrollHeight;
    for (const { button, anchor } of marks.values()) {
      const y = scrollY(anchor);
      button.hidden = y === null;
      if (y !== null) button.style.top = `${markTop(y, total, tr).toFixed(1)}px`;
    }
  };

  const build = (data) => {
    for (const m of marks.values()) m.button.remove();
    marks = new Map();
    for (const p of data.passages) {
      const a = data.anchors[String(p.cid)];
      if (!a) continue;
      const b = document.createElement("button");
      b.type = "button";
      b.className = `mark ${p.category}`;
      b.title = `Change ${p.cid} · p. ${a.page}`;
      b.setAttribute("aria-label", b.title);
      b.addEventListener("click", () => document.dispatchEvent(new CustomEvent("calandria:goto", { detail: { cid: p.cid } })));
      strip.appendChild(b);
      marks.set(p.cid, { button: b, anchor: a });
    }
    strip.hidden = marks.size === 0;
    place();
    viewport();
  };

  const viewport = () => {
    const tr = theTrack();
    const total = main.scrollHeight;
    view.style.top = `${markTop(main.scrollTop, total, tr).toFixed(1)}px`;
    view.style.height = `${((main.clientHeight / Math.max(1, total)) * tr.len).toFixed(1)}px`;
  };

  document.addEventListener("calandria:loaded", (e) => build(e.detail));
  document.addEventListener("calandria:filtered", (e) => {
    const on = new Set(e.detail.visible);
    for (const [cid, m] of marks) m.button.classList.toggle("dim", !on.has(cid));
  });
  document.addEventListener("calandria:selected", (e) => {
    for (const [cid, m] of marks) m.button.classList.toggle("current", cid === e.detail.cid);
  });
  const relayout = () => { place(); viewport(); };    // zoom, fit, changed pages only, a resize
  main.addEventListener("scroll", viewport);
  window.addEventListener("resize", relayout);
  document.addEventListener("calandria:resized", relayout);
}
