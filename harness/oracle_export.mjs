// Runs the SorkWhare 1.16.0 engine on every corpus pair and writes tests/oracle/<alias>.json.
// Usage: node harness/oracle_export.mjs        (env SORKWHARE_DIR overrides the checkout path)
import {readFileSync, writeFileSync, mkdirSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import path from 'node:path';

const SW = process.env.SORKWHARE_DIR || path.resolve(process.cwd(), '..', 'SorkWhare');
const ROOT = path.resolve(process.cwd());
const CORPUS = path.join(ROOT, 'tests', 'corpus');
const OUT = path.join(ROOT, 'tests', 'oracle');

const {loadApp} = await import(pathToFileURL(path.join(SW, 'tests', 'load.mjs')).href);
const ctx = loadApp('SorkWhare 1.16.0.html');

const fileOf = p => { const b = readFileSync(p); return {name: path.basename(p),
  arrayBuffer: async () => b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength)}; };

const KEYS = ['text','marker','isNumbered','ilvl','styleId','align','indLeftPt','indHangingPt','indFirstLinePt',
  'spaceBeforePt','spaceAfterPt','lineSpacing','lineExactPt','keepNext','keepLines','pageBreakBefore',
  'contextualSpacing','heading','boldRuns'];
function rec(p) {
  const r = {};
  // Arrays (boldRuns) come out of the engine's realm; round-trip them so the written JSON is
  // plain data rather than a live cross-realm object.
  for (const k of KEYS) { const v = p[k];
    r[k] = v === undefined ? null : (Array.isArray(v) ? JSON.parse(JSON.stringify(v)) : v); }
  r.tbl = p.tbl ? {ti: p.tbl.ti, ri: p.tbl.ri, ci: p.tbl.ci, cols: p.tbl.cols} : null;
  return r;
}
function side(A) { return {paras: Array.from(A, rec), geometry: JSON.parse(JSON.stringify(A.geometry || null))}; }
function rows(res) {
  return res.rows.map(r => ({type: r.type, cid: r.cid ?? null, cat: r.cat ?? null, oi: r.oi ?? null, ni: r.ni ?? null,
    html: r.html ?? '', numChanged: !!r.numChanged, oldMarker: r.oldMarker ?? null}));
}

mkdirSync(OUT, {recursive: true});
const manifest = JSON.parse(readFileSync(path.join(CORPUS, 'manifest.json'), 'utf8'));
for (const pair of manifest.pairs) {
  const A = await ctx.docxToParagraphs(fileOf(path.join(CORPUS, pair.a)));
  const B = await ctx.docxToParagraphs(fileOf(path.join(CORPUS, pair.b)));
  const res = ctx.compare(A, B, {});
  const out = {A: side(A), B: side(B), compare: {rows: rows(res), summary: JSON.parse(JSON.stringify(res.summary))}};
  writeFileSync(path.join(OUT, pair.alias + '.json'), JSON.stringify(out));
  console.log(pair.alias, out.A.paras.length, out.B.paras.length, 'changes', res.summary.total);
}
