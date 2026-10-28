"""In-memory .docx builder for tests (STORED zip entries, no compression)."""
import io
import zipfile
from xml.sax.saxutils import escape

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def make_docx(parts: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as z:
        for name, text in parts.items():
            z.writestr(name, text.encode("utf8"))
    return buf.getvalue()


def DOC(body: str) -> str:
    return f'<w:document xmlns:w="{W_NS}"><w:body>{body}</w:body></w:document>'


def P(text: str, ppr: str = "", rpr: str = "") -> str:
    p = f"<w:pPr>{ppr}</w:pPr>" if ppr else ""
    r = f"<w:rPr>{rpr}</w:rPr>" if rpr else ""
    return (f"<w:p>{p}<w:r>{r}<w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r></w:p>")


def R(text: str, rpr: str = "") -> str:
    r = f"<w:rPr>{rpr}</w:rPr>" if rpr else ""
    return f'<w:r>{r}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def PR(runs: str, ppr: str = "") -> str:
    p = f"<w:pPr>{ppr}</w:pPr>" if ppr else ""
    return f"<w:p>{p}{runs}</w:p>"


def TBL(rows: list[list[str]], grid: list[int] | None = None, tblpr: str = "") -> str:
    g = ("<w:tblGrid>" + "".join(f'<w:gridCol w:w="{w}"/>' for w in grid) + "</w:tblGrid>") if grid else ""
    return "<w:tbl>" + tblpr + g + "".join(
        "<w:tr>" + "".join(f"<w:tc>{P(c)}</w:tc>" for c in r) + "</w:tr>" for r in rows) + "</w:tbl>"


def NUMBERING(levels: list[tuple]) -> str:
    """One abstract list (numId 1). levels: (numFmt, lvlText, left_twips, hanging_twips, suff|None)."""
    lv = ""
    for i, (fmt, text, left, hanging, suff) in enumerate(levels):
        s = f'<w:suff w:val="{suff}"/>' if suff else ""
        lv += (f'<w:lvl w:ilvl="{i}"><w:start w:val="1"/><w:numFmt w:val="{fmt}"/>{s}'
               f'<w:lvlText w:val="{escape(text)}"/><w:lvlJc w:val="left"/>'
               f'<w:pPr><w:ind w:left="{left}" w:hanging="{hanging}"/></w:pPr></w:lvl>')
    return (f'<w:numbering xmlns:w="{W_NS}"><w:abstractNum w:abstractNumId="0">{lv}</w:abstractNum>'
            f'<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>')


def STYLES(defaults_rpr: str = "", styles: str = "") -> str:
    return (f'<w:styles xmlns:w="{W_NS}"><w:docDefaults><w:rPrDefault><w:rPr>{defaults_rpr}</w:rPr>'
            f"</w:rPrDefault></w:docDefaults>{styles}</w:styles>")


def FNREF(note_id: int) -> str:
    """A footnote reference run (the superscript mark in the body)."""
    return f'<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr><w:footnoteReference w:id="{note_id}"/></w:r>'


def ENREF(note_id: int) -> str:
    return f'<w:r><w:rPr><w:rStyle w:val="EndnoteReference"/></w:rPr><w:endnoteReference w:id="{note_id}"/></w:r>'


def _notes(tag: str, ref: str, notes: dict) -> str:
    seps = (f'<w:{tag} w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:{tag}>'
            f'<w:{tag} w:type="continuationSeparator" w:id="0"><w:p><w:r><w:continuationSeparator/></w:r></w:p></w:{tag}>')
    body = ""
    for nid, text in notes.items():
        paras = text if text.startswith("<w:") else "".join(
            f'<w:p><w:r><w:rPr><w:rStyle w:val="{ref[0].upper()+ref[1:]}"/></w:rPr><w:{ref}/></w:r>'
            f'<w:r><w:t xml:space="preserve"> {escape(t)}</w:t></w:r></w:p>' for t in text.splitlines())
        body += f'<w:{tag} w:id="{nid}">{paras}</w:{tag}>'
    return f'<w:{tag}s xmlns:w="{W_NS}">{seps}{body}</w:{tag}s>'


def FOOTNOTES(notes: dict[int, str]) -> str:
    """word/footnotes.xml: the two separator notes plus one note per id. A value is the note's
    text (paragraphs split on newlines, each led by the w:footnoteRef mark run) or raw <w:p> XML."""
    return _notes("footnote", "footnoteRef", notes)


def ENDNOTES(notes: dict[int, str]) -> str:
    return _notes("endnote", "endnoteRef", notes)


WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_RELS = "http://schemas.openxmlformats.org/package/2006/relationships"
REL_HDR = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/header"
REL_FTR = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer"


def SECT(hdr: dict | None = None, ftr: dict | None = None, title_pg: bool = False, page_start: int | None = None,
         page_fmt: str | None = None, type: str | None = None, extra: str = "") -> str:
    """A <w:sectPr> (Letter, 1 in margins, header/footer 0.5 in). hdr/ftr: variant -> rId."""
    refs = "".join(f'<w:headerReference w:type="{v}" r:id="{rid}"/>' for v, rid in (hdr or {}).items())
    refs += "".join(f'<w:footerReference w:type="{v}" r:id="{rid}"/>' for v, rid in (ftr or {}).items())
    t = f'<w:type w:val="{type}"/>' if type else ""
    pn = ""
    if page_start is not None or page_fmt:
        pn = "<w:pgNumType" + (f' w:start="{page_start}"' if page_start is not None else "") + \
             (f' w:fmt="{page_fmt}"' if page_fmt else "") + "/>"
    tp = "<w:titlePg/>" if title_pg else ""
    return (f'<w:sectPr xmlns:r="{R_NS}">{refs}{t}<w:pgSz w:w="12240" w:h="15840"/>'
            f'<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720"/>'
            f"{pn}{tp}{extra}</w:sectPr>")


def HDR(body: str) -> str:
    return f'<w:hdr xmlns:w="{W_NS}" xmlns:r="{R_NS}">{body}</w:hdr>'


def FTR(body: str) -> str:
    return f'<w:ftr xmlns:w="{W_NS}" xmlns:r="{R_NS}">{body}</w:ftr>'


def RELS(mapping: dict[str, str]) -> str:
    """word/_rels/document.xml.rels: rId -> part basename (header*.xml / footer*.xml)."""
    rels = "".join(f'<Relationship Id="{rid}" Type="{REL_HDR if t.startswith("header") else REL_FTR}" Target="{t}"/>'
                   for rid, t in mapping.items())
    return f'<Relationships xmlns="{PKG_RELS}">{rels}</Relationships>'


def SETTINGS(even_and_odd: bool = False) -> str:
    return f'<w:settings xmlns:w="{W_NS}">{"<w:evenAndOddHeaders/>" if even_and_odd else ""}</w:settings>'


def FLD(name: str, cached: str = "1", rpr: str = "") -> str:
    """A simple field: <w:fldSimple w:instr=" NAME "> holding its cached result run."""
    return f'<w:fldSimple w:instr=" {name} \\* MERGEFORMAT ">{R(cached, rpr)}</w:fldSimple>'


def FLDC(name: str, cached: str = "1", rpr: str = "") -> str:
    """The complex field form: begin / instrText / separate / result / end, one run each."""
    r = f"<w:rPr>{rpr}</w:rPr>" if rpr else ""
    return (f'<w:r>{r}<w:fldChar w:fldCharType="begin"/></w:r>'
            f'<w:r>{r}<w:instrText xml:space="preserve"> {name}  \\* MERGEFORMAT </w:instrText></w:r>'
            f'<w:r>{r}<w:fldChar w:fldCharType="separate"/></w:r>'
            f'<w:r>{r}<w:t>{escape(cached)}</w:t></w:r>'
            f'<w:r>{r}<w:fldChar w:fldCharType="end"/></w:r>')


def IMG(cx_emu: int, cy_emu: int) -> str:
    """A run holding an inline drawing of the given extent (no picture data)."""
    return (f'<w:r><w:drawing><wp:inline xmlns:wp="{WP_NS}"><wp:extent cx="{cx_emu}" cy="{cy_emu}"/>'
            f'<wp:docPr id="1" name="Picture 1"/></wp:inline></w:drawing></w:r>')


W14_NS = "http://schemas.microsoft.com/office/word/2010/wordml"
W15_NS = "http://schemas.microsoft.com/office/word/2012/wordml"
REL_COMMENTS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
REL_COMMENTS_EX = "http://schemas.microsoft.com/office/2011/relationships/commentsExtended"
REL_PEOPLE = "http://schemas.microsoft.com/office/2011/relationships/people"


def CRANGE(cid: str, text: str, rpr: str = "") -> str:
    """A run of `text` wrapped by commentRangeStart/End for comment id `cid` (the anchored span),
    followed by the commentReference run."""
    return (f'<w:commentRangeStart w:id="{cid}"/>{R(text, rpr)}<w:commentRangeEnd w:id="{cid}"/>'
            f'<w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr><w:commentReference w:id="{cid}"/></w:r>')


def CREF(cid: str) -> str:
    """A bare commentReference run (a point anchor: no range)."""
    return f'<w:r><w:commentReference w:id="{cid}"/></w:r>'


def _cpara(paraid: str, text: str) -> str:
    return f'<w:p w14:paraId="{paraid}"><w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'


def COMMENTS(comments: list[dict]) -> str:
    """word/comments.xml. Each dict: id, author, initials (optional), date (optional),
    paras = list of (paraId, text). One <w:comment> per dict."""
    body = ""
    for c in comments:
        attrs = f'w:id="{c["id"]}" w:author="{escape(c.get("author", ""))}"'
        if c.get("date"):
            attrs += f' w:date="{c["date"]}"'
        if c.get("initials"):
            attrs += f' w:initials="{escape(c["initials"])}"'
        paras = "".join(_cpara(pid, t) for pid, t in c["paras"])
        body += f"<w:comment {attrs}>{paras}</w:comment>"
    return f'<w:comments xmlns:w="{W_NS}" xmlns:w14="{W14_NS}">{body}</w:comments>'


def COMMENTS_EX(entries: list[dict]) -> str:
    """word/commentsExtended.xml. Each dict: paraId, parent (optional paraIdParent), done (bool)."""
    body = ""
    for e in entries:
        a = f'w15:paraId="{e["paraId"]}"'
        if e.get("parent"):
            a += f' w15:paraIdParent="{e["parent"]}"'
        if e.get("done"):
            a += ' w15:done="1"'
        body += f"<w15:commentEx {a}/>"
    return f'<w15:commentsEx xmlns:w15="{W15_NS}">{body}</w15:commentsEx>'


def PEOPLE(names: list[str]) -> str:
    """word/people.xml (author identities; content not otherwise used by the reader)."""
    ppl = "".join(f'<w15:person w15:author="{escape(n)}"/>' for n in names)
    return f'<w15:people xmlns:w15="{W15_NS}">{ppl}</w15:people>'


def CRELS(comments=False, comments_ex=False, people=False, start=1) -> str:
    """word/_rels/document.xml.rels wiring the comment parts (rIds from `start`)."""
    rels, i = "", start
    for want, target, typ in ((comments, "comments.xml", REL_COMMENTS),
                              (comments_ex, "commentsExtended.xml", REL_COMMENTS_EX),
                              (people, "people.xml", REL_PEOPLE)):
        if want:
            rels += f'<Relationship Id="rId{i}" Type="{typ}" Target="{target}"/>'
            i += 1
    return f'<Relationships xmlns="{PKG_RELS}">{rels}</Relationships>'
