import pytest

from calandria.pdfread.content import IDENT, apply, base_matrix, interpret, mul
from calandria.pdfread.pdffonts import PdfFont
from calandria.pdfread.types import PageData

F = PdfFont("ABCDEF+Arial", widths={65: 500.0, 66: 500.0, 32: 250.0})
LETTER = (0.0, 0.0, 612.0, 792.0)


def run(ops, fonts=None, xobjects=None, box=LETTER, rotation=0):
    box_w, box_h = box[2] - box[0], box[3] - box[1]
    page = PageData(*((box_h, box_w) if rotation in (90, 270) else (box_w, box_h)))
    interpret(ops, fonts if fonts is not None else {"/F1": F}, xobjects or {}, base_matrix(box, rotation), page)
    return page


def text_ops(*show, at=(72.0, 700.0), size=10.0):
    return [([], b"BT"), (["/F1", size], b"Tf"), (list(at), b"Td"), *show, ([], b"ET")]


def test_matrices_compose_left_to_right():
    shift, scale = (1, 0, 0, 1, 10, 20), (2, 0, 0, 2, 0, 0)
    assert apply(mul(shift, scale), 1, 1) == (22, 42)
    assert mul(IDENT, shift) == shift


def test_base_matrix_flips_y_and_honours_the_box_origin_and_rotation():
    assert apply(base_matrix(LETTER, 0), 72, 700) == (72, 92)
    assert apply(base_matrix((10, 20, 622, 812), 0), 82, 720) == (72, 92)
    assert apply(base_matrix(LETTER, 90), 0, 0) == (0, 0)          # bottom-left becomes top-left
    assert apply(base_matrix(LETTER, 90), 612, 0) == (0, 612)
    assert apply(base_matrix(LETTER, 180), 612, 0) == (0, 0)
    assert apply(base_matrix(LETTER, 270), 612, 792) == (0, 0)


def test_tj_gives_a_run_with_start_end_baseline_and_size():
    p = run(text_ops(([b"AB"], b"Tj")))
    (r,) = p.runs
    assert (r.text, r.font, r.size) == ("AB", "ABCDEF+Arial", 10.0)
    assert (r.x0, r.x1, r.y) == pytest.approx((72.0, 82.0, 92.0))
    assert (p.chars, p.bad_chars) == (2, 0)


def test_tj_array_moves_by_its_numbers_and_word_spacing_applies_to_spaces():
    p = run(text_ops(([2.0], b"Tw"), ([[b"A", -1000.0, b"A B"]], b"TJ")))
    a, b = p.runs
    assert (a.x0, a.x1) == pytest.approx((72.0, 77.0))
    assert b.x0 == pytest.approx(87.0)                       # 77 + 1000/1000 * 10
    assert b.x1 == pytest.approx(87.0 + 5 + 2.5 + 2 + 5)     # A, space + Tw, B


def test_td_tstar_quote_and_tm_position_lines():
    ops = [([], b"BT"), (["/F1", 10.0], b"Tf"), ([12.0], b"TL"), ([72.0, 700.0], b"Td"), ([b"A"], b"Tj"),
           ([], b"T*"), ([b"A"], b"Tj"), ([b"B"], b"'"), ([1.0, 0.0, 0.0, 1.0, 100.0, 500.0], b"Tm"), ([b"A"], b"Tj"),
           ([], b"ET")]
    ys = [(r.x0, r.y) for r in run(ops).runs]
    assert ys == pytest.approx([(72, 92), (72, 104), (72, 116), (100, 292)])


def test_cm_scales_position_and_size_and_q_restores():
    ops = [([], b"q"), ([2.0, 0.0, 0.0, 2.0, 0.0, 0.0], b"cm"), *text_ops(([b"A"], b"Tj"), at=(36.0, 350.0)),
           ([], b"Q"), *text_ops(([b"A"], b"Tj"))]
    big, normal = run(ops).runs
    assert (big.x0, big.y, big.size, big.x1) == pytest.approx((72.0, 92.0, 20.0, 82.0))
    assert normal.size == 10.0


def test_rotated_text_is_dropped_and_nul_text_is_empty():
    rot = [([], b"BT"), (["/F1", 10.0], b"Tf"), ([0.0, 1.0, -1.0, 0.0, 100.0, 100.0], b"Tm"), ([b"A"], b"Tj"), ([], b"ET")]
    assert run(rot).runs == []
    nul = PdfFont("N", to_unicode={65: "\x00"})
    assert run(text_ops(([b"A"], b"Tj")), fonts={"/F1": nul}).runs == []


def test_an_unknown_font_name_still_reads_as_cp1252():
    p = run(text_ops(([b"Hi"], b"Tj")), fonts={})
    assert p.runs[0].text == "Hi" and p.runs[0].font == "Unknown"
    assert (p.chars, p.bad_chars) == (2, 2)          # counted as unreadable: its font was lost


def test_a_page_shown_entirely_through_an_unknown_font_is_unreadable():
    from calandria.pdfread.extract import unreadable
    p = run(text_ops(([b"Hi"], b"Tj")), fonts={})
    assert unreadable(p)


def test_a_stroked_rectangle_gives_four_segments_and_a_line_gives_one():
    ops = [([72.0, 642.0, 200.0, -40.0], b"re"), ([], b"S"),
           ([172.0, 642.0], b"m"), ([172.0, 602.0], b"l"), ([], b"S")]
    segs = run(ops).segs
    assert len(segs) == 5
    assert sorted((s.x0, s.y0, s.x1, s.y1) for s in segs if s.horizontal) == [(72, 150, 272, 150), (72, 190, 272, 190)]
    assert (172, 150, 172, 190) in [(s.x0, s.y0, s.x1, s.y1) for s in segs]


def test_a_thin_filled_rectangle_is_a_segment_and_a_fat_one_is_shading():
    ops = [([72.0, 572.0, 200.0, -0.5], b"re"), ([], b"f"),          # a border drawn as a filled sliver
           ([72.0, 500.0, 200.0, -40.0], b"re"), ([], b"f"),         # cell shading
           ([300.0, 700.0], b"m"), ([300.6, 700.0], b"l"), ([300.6, 600.0], b"l"), ([300.0, 600.0], b"l"),
           ([], b"h"), ([], b"f")]                                   # a sliver drawn as a closed path
    segs = run(ops).segs
    assert [(s.x0, s.y0, s.x1, s.y1) for s in segs] == pytest.approx([(72, 220.25, 272, 220.25), (300.3, 92, 300.3, 192)])


def test_a_clip_path_is_not_a_border_and_images_are_counted():
    ops = [([72.0, 642.0, 200.0, -40.0], b"re"), ([], b"W"), ([], b"n"),
           (["/Im1"], b"Do"), (["/Fm1"], b"Do"), ([{}], b"INLINE IMAGE")]
    p = run(ops, xobjects={"/Im1": "image", "/Fm1": "form"})
    assert p.segs == [] and p.images == 2
