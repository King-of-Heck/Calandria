from calandria.pdfread.types import Line, PageData, PdfRefused, Seg, Span, TextRun


def test_seg_direction_and_length():
    assert Seg(10, 50, 110, 50).horizontal and Seg(10, 50, 110, 50).length == 100
    assert not Seg(10, 50, 10, 90).horizontal and Seg(10, 50, 10, 90).length == 40


def test_line_text_joins_its_spans():
    ln = Line(0, 72, 200, 100, 12, [Span("Hello ", "Arial", 12), Span("world", "Arial,Bold", 12)])
    assert ln.text == "Hello world" and ln.cell is None


def test_page_data_starts_empty_and_refusal_is_a_value_error():
    p = PageData(612, 792)
    assert (p.runs, p.segs, p.images, p.chars, p.bad_chars) == ([], [], 0, 0, 0)
    assert issubclass(PdfRefused, ValueError)
    assert TextRun("a", 1, 2, 3, 4, "F").x1 == 2
