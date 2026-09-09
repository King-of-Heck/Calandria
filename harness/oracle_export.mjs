// Runs the SorkWhare 1.16.0 engine on every corpus pair and writes tests/oracle/<alias>.json.
// Usage: node harness/oracle_export.mjs        (env SORKWHARE_DIR overrides the checkout path)
import {readFileSync, writeFileSync, mkdirSync, existsSync} from 'node:fs';
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
    html: r.html ?? '', numChanged: !!r.numChanged, oldMarker: r.oldMarker ?? null,
    fmtChanged: !!r.fmtChanged, fmtDescs: r.fmtDescs ? JSON.parse(JSON.stringify(r.fmtDescs)) : null,
    tbl: r.meta && r.meta.tbl ? {ti: r.meta.tbl.ti, ri: r.meta.tbl.ri, ci: r.meta.tbl.ci, cols: r.meta.tbl.cols} : null}));
}
function result(res) { return {rows: rows(res), summary: JSON.parse(JSON.stringify(res.summary))}; }
// v2.0.0 scope: no moves (moveMin:Infinity) and no split/merge (SM_SIM is a `var` in the engine, so
// it is a property of the vm context and can be raised past any similarity).
function compareV2(A, B, opts) {
  const keep = ctx.SM_SIM; ctx.SM_SIM = Infinity;
  try { const res = ctx.compare(A, B, Object.assign({moveMin: Infinity}, opts));
    if (res.summary.moves || res.summary.splits || res.summary.merges) throw new Error('v2 variant produced moves/splits/merges');
    return result(res); }
  finally { ctx.SM_SIM = keep; }
}

mkdirSync(OUT, {recursive: true});
const pairs = [];
for (const name of ['manifest.json', 'manifest.gen.json']) {
  const p = path.join(CORPUS, name);
  if (existsSync(p)) pairs.push(...JSON.parse(readFileSync(p, 'utf8')).pairs);
}
for (const pair of pairs) {
  const A = await ctx.docxToParagraphs(fileOf(path.join(CORPUS, pair.a)));
  const B = await ctx.docxToParagraphs(fileOf(path.join(CORPUS, pair.b)));
  const out = {A: side(A), B: side(B), compare: result(ctx.compare(A, B, {})),
    compare_v2: compareV2(A, B, {}), compare_v2_ic: compareV2(A, B, {ignoreCase: true})};
  writeFileSync(path.join(OUT, pair.alias + '.json'), JSON.stringify(out));
  console.log(pair.alias, out.A.paras.length, out.B.paras.length, 'changes', out.compare_v2.summary.total);
}
