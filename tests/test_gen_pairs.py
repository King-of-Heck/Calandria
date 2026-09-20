import io
import json
import sys
from pathlib import Path

from calandria.diff.compare import compare
from calandria.docx.parser import parse_docx
from calandria.model import Table

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "harness"))
import gen_pairs  # noqa: E402


def test_every_pair_parses_and_compares(tmp_path):
    pairs = gen_pairs.write_all(tmp_path)
    assert [p["alias"] for p in pairs] == ["gen-fmt", "gen-table", "gen-punct", "gen-dense", "gen-longcap",
                                           "gen-empty", "gen-latin1", "gen-notes", "gen-hf", "gen-comments",
                                           "gen-grid", "gen-longtable", "gen-schedule"]
    manifest = json.loads((tmp_path / "manifest.gen.json").read_text("utf8"))
    assert manifest["pairs"] == pairs
    for p in pairs:
        c = compare(parse_docx(tmp_path / p["a"]), parse_docx(tmp_path / p["b"]))
        assert c.rows, p["alias"]


def test_fmt_pair_exercises_every_formatting_attribute():
    a, b = gen_pairs.PAIRS["fmt"]
    c = compare(parse_docx(io.BytesIO(gen_pairs.build(a))), parse_docx(io.BytesIO(gen_pairs.build(b))))
    descs = sorted(d for r in c.rows for d in (x.desc for x in r.fmt_ranges))
    assert descs == ["bold added", "colour default → #ff0000", "font Calibri → Arial",
                     "italic added", "size 11 → 14", "underline added"]
    assert c.summary["formatting"] == 6 and c.summary["total"] == 2


def test_longcap_pair_is_above_the_inline_cap():
    from calandria.diff.inline import INLINE_TOKEN_CAP
    from calandria.diff.text import tokenize
    a, _b = gen_pairs.PAIRS["longcap"]
    d = parse_docx(io.BytesIO(gen_pairs.build(a)))
    assert len(tokenize(d.blocks[0].text)) > INLINE_TOKEN_CAP


def test_hf_pair_has_two_changed_header_rows_and_no_footer_change():
    a, b = gen_pairs.PAIRS["hf"]
    c = compare(parse_docx(io.BytesIO(gen_pairs.build(a))), parse_docx(io.BytesIO(gen_pairs.build(b))))
    streams = [c.unit_for(r).stream for r in c.rows if r.type != "equal"]
    # the cover replacement (deletion + insertion = 2 passages) and the added even header (1)
    assert sorted(streams) == ["header", "header"] and c.summary["total"] == 3
    d = parse_docx(io.BytesIO(gen_pairs.build(b)))
    assert d.even_and_odd and d.sections[2].page_start == 1 and len(d.sections) == 3


def test_comments_pair_covers_add_remove_edit_thread_and_resolve():
    a, b = gen_pairs.PAIRS["comments"]
    c = compare(parse_docx(io.BytesIO(gen_pairs.build(a))), parse_docx(io.BytesIO(gen_pairs.build(b))))
    flagged = [cc for cc in c.comments if cc.state != "unchanged"]
    counts = {k: sum(cc.state == k for cc in flagged) for k in ("added", "removed", "edited")}
    assert counts == {"added": 5, "removed": 1, "edited": 1}      # 2,6,3,4,5 added; 1 removed; 0 edited
    assert any(cc.done for cc in c.comments)                       # the resolved comment
    assert any(cc.depth == 1 for cc in c.comments)                # the reply
    assert c.summary["total"] == c.summary["insertions"] + c.summary["deletions"] + \
        c.summary["numbering_changes"]                            # comments never entered the count


def test_grid_pair_has_one_ruled_table_with_a_span_and_a_vmerge():
    a, b = gen_pairs.PAIRS["grid"]
    da = parse_docx(io.BytesIO(gen_pairs.build(a)))
    tables = [t for t in da.blocks if isinstance(t, Table)]
    assert len(tables) == 1
    t = tables[0]
    assert len(t.rows) == 6 and len(t.grid_pt) == 4
    spans = [c.grid_span for r in t.rows for c in r.cells]
    vmerges = [c.v_merge for r in t.rows for c in r.cells if c.v_merge]
    assert 2 in spans
    assert vmerges == ["restart", "continue"]
    c = compare(parse_docx(io.BytesIO(gen_pairs.build(a))), parse_docx(io.BytesIO(gen_pairs.build(b))))
    assert c.summary["total"] > 0


def test_longtable_pair_has_a_repeating_header_and_a_mid_table_insert():
    a, b = gen_pairs.PAIRS["longtable"]
    da = parse_docx(io.BytesIO(gen_pairs.build(a)))
    db = parse_docx(io.BytesIO(gen_pairs.build(b)))
    ta = next(t for t in da.blocks if isinstance(t, Table))
    tb = next(t for t in db.blocks if isinstance(t, Table))
    assert len(ta.rows) == 110                   # header + 109 data rows
    assert len(tb.rows) == 111                   # one row inserted mid-table
    c = compare(parse_docx(io.BytesIO(gen_pairs.build(a))), parse_docx(io.BytesIO(gen_pairs.build(b))))
    assert c.summary["total"] > 0


def test_ruled_tables_carry_all_six_tbl_borders_sides():
    # A regression that drops a border side (or the whole w:tblBorders element) must fail here.
    a, _b = gen_pairs.PAIRS["grid"]
    xml = a["word/document.xml"]
    assert "<w:tblBorders>" in xml
    borders = xml.split("<w:tblBorders>", 1)[1].split("</w:tblBorders>", 1)[0]
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        assert f'<w:{side} w:val="single"' in borders, side


def test_schedule_pair_has_two_ruled_tables_and_numbered_clauses():
    a, b = gen_pairs.PAIRS["schedule"]
    da = parse_docx(io.BytesIO(gen_pairs.build(a)))
    tables = [t for t in da.blocks if isinstance(t, Table)]
    assert len(tables) == 2
    assert (len(tables[0].rows), len(tables[0].grid_pt)) == (8, 3)
    assert (len(tables[1].rows), len(tables[1].grid_pt)) == (4, 2)
    c = compare(parse_docx(io.BytesIO(gen_pairs.build(a))), parse_docx(io.BytesIO(gen_pairs.build(b))))
    assert c.summary["total"] > 0
