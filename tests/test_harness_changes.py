from calandria.diff.chars import FmtSpan
from calandria.diff.compare import compare
from calandria.diff.fmt import FmtRange
from calandria.diff.inline import Seg
from calandria.docx.parser import parse_docx
from calandria.harness.changes import esc, fmt_wrap, records, render_html
from calandria.testing.makedocx import DOC, P, PR, R, make_docx


def _doc(body):
    return parse_docx(make_docx({"word/document.xml": DOC(body)}))


def test_esc_only_amp_lt_gt():
    assert esc('a & <b> "q"') == 'a &amp; &lt;b&gt; "q"'


def test_render_html_one_wrapper_per_mode_run_with_nested_bold():
    segs = [Seg("eq", "x "), Seg("del", "a", True), Seg("del", " b"), Seg("ins", "c<"), Seg("eq", " y")]
    assert render_html(segs) == "x <del><b>a</b> b</del><ins>c&lt;</ins> y"
    assert render_html([]) == ""


def test_fmt_wrap_matches_reference_shape():
    spans = [FmtSpan(0, 5, False, False, False, "Calibri", 11.0, None),
             FmtSpan(5, 11, True, True, False, "Calibri", 11.0, None)]
    ranges = [FmtRange(5, 11, "bold added; italic added")]
    assert fmt_wrap("Hello World", spans, ranges) == (
        'Hello<span class="fmtchg" title="bold added; italic added"><i><b> World</b></i></span>')


def test_fmt_wrap_escapes_quotes_in_title_and_splits_on_desc_change():
    spans = [FmtSpan(0, 2, False, False, False, 'F"', 11.0, None), FmtSpan(2, 4, False, False, True, 'F"', 11.0, None)]
    ranges = [FmtRange(0, 2, 'font F" → G'), FmtRange(2, 4, "underline added")]
    assert fmt_wrap("abcd", spans, ranges) == (
        '<span class="fmtchg" title="font F&quot; → G">ab</span>'
        '<span class="fmtchg" title="underline added"><u>cd</u></span>')


def test_records_shape_for_each_row_type():
    a = _doc(P("Keep") + P("Old para") + P("Bold me") + P("Gone"))
    b = _doc(P("Keep") + P("New para") + PR(R("Bold", "<w:b/>") + R(" me")) + P("Added"))
    recs = records(compare(a, b))
    assert [r["type"] for r in recs] == ["equal", "changed", "equal", "deleted", "inserted"]
    assert recs[0] == {"type": "equal", "cid": None, "cat": None, "oi": 0, "ni": 0, "html": "Keep",
                       "numChanged": False, "oldMarker": None, "fmtChanged": False, "fmtDescs": None, "tbl": None}
    assert recs[1]["html"] == "<del>Old</del><ins>New</ins> para" and recs[1]["cid"] == 1 and recs[1]["cat"] == "content"
    assert recs[2]["fmtChanged"] and recs[2]["fmtDescs"] == ["bold added"]
    assert recs[2]["html"] == '<span class="fmtchg" title="bold added"><b>Bold</b></span> me'
    assert recs[3]["html"] == "<del>Gone</del>" and recs[4]["html"] == "<ins>Added</ins>"
