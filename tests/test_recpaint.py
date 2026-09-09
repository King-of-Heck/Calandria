from calandria.layout.pages import FontRef
from calandria.pdf.painter import rgb
from calandria.testing.recpaint import RecordingPainter

FACE = FontRef("<fake:Fake|>", 0, "Fake", False, False, False)


def test_records_every_operation_in_order_with_rounded_coordinates():
    p = RecordingPainter()
    p.page(612, 792)
    p.text(72.004, 80.0, "Hi", FACE, 11, "0000ff")
    p.rule(72, 92.129, 81.21, 0.66, "0000ff", dotted=True)
    p.line(66, 72, 66, 84, 1.5, "000000")
    p.page(612, 792)
    assert p.pages == 2
    assert p.ops == [("page", 612, 792),
                     ("text", 72.0, 80.0, "Hi", "<fake:Fake|>", 11, "0000ff", False, False),
                     ("rule", 72, 92.13, 81.21, 0.66, "0000ff", True),
                     ("line", 66, 72, 66, 84, 1.5, "000000"),
                     ("page", 612, 792)]
    assert p.of("text") == [p.ops[1]] and p.of("page") == [p.ops[0], p.ops[4]]
    assert p.page_ops(1) == p.ops[1:4] and p.page_ops(2) == []


def test_fake_flags_are_recorded():
    p = RecordingPainter()
    p.page(100, 100)
    p.text(0, 10, "b", FACE, 10, "000000", fake_bold=True, fake_italic=True)
    assert p.ops[-1][-2:] == (True, True)


def test_rgb():
    assert rgb("0000ff") == (0, 0, 255) and rgb("7c3aed") == (124, 58, 237) and rgb("000000") == (0, 0, 0)
