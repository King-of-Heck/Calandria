from calandria.diff.units import Loc, units
from calandria.docx.parser import parse_docx
from calandria.testing.makedocx import DOC, P, make_docx


def _doc(body, **parts):
    return parse_docx(make_docx({"word/document.xml": DOC(body), **parts}))


def _tbl(rows):
    return "<w:tbl>" + "".join(
        "<w:tr>" + "".join(f"<w:tc>{P(c)}</w:tc>" for c in r) + "</w:tr>" for r in rows) + "</w:tbl>"


def test_units_skip_empty_paragraphs_and_tag_table_cells():
    d = _doc(P("Intro") + P("") + _tbl([["a", "b"], ["c", "d"]]) + P("Outro"))
    us = units(d)
    assert [u.text for u in us] == ["Intro", "a", "b", "c", "d", "Outro"]
    assert [u.index for u in us] == list(range(6))
    assert us[0].loc is None and us[5].loc is None
    assert us[1].loc == Loc(0, 0, 0, 2) and us[4].loc == Loc(0, 1, 1, 2)
    assert us[0].marker == "" and us[0].bold_runs == [] and us[0].fmt_spans[0].e == 5
    assert us[0].para is d.blocks[0]


def test_units_second_table_increments_ti():
    d = _doc(_tbl([["a"]]) + _tbl([["b", "c"], ["d"]]))
    us = units(d)
    assert [u.loc for u in us] == [Loc(0, 0, 0, 1), Loc(1, 0, 0, 2), Loc(1, 0, 1, 2), Loc(1, 1, 0, 2)]


def test_loc_as_dict():
    from calandria.diff.units import Loc
    assert Loc(1, 2, 3, 4).as_dict() == {"ti": 1, "ri": 2, "ci": 3, "cols": 4}
