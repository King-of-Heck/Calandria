from calandria.pdfread.pdffonts import REPLACEMENT, PdfFont, load_font, parse_tounicode

CMAP = b"""/CIDInit /ProcSet findresource begin
1 begincodespacerange <0000> <FFFF> endcodespacerange
3 beginbfchar
<0001> <0048>
<0002> <00660069>
<0003> <>
endbfchar
2 beginbfrange
<0010> <0012> <0061>
<0020> <0021> [<0058> <0059>]
endbfrange
endcmap"""


class Stream(dict):
    def __init__(self, data):
        super().__init__()
        self._data = data

    def get_data(self):
        return self._data


class BoomStream(dict):
    """A stream whose get_data() raises, as a ToUnicode object with a filter pypdf cannot apply
    would."""
    def get_data(self):
        raise ValueError("corrupt stream")


class Ref:
    """A tiny stand-in for pypdf's IndirectObject: get_object() returns the wrapped value."""
    def __init__(self, value):
        self._value = value

    def get_object(self):
        return self._value


def test_parse_tounicode_reads_chars_ranges_and_the_code_width():
    m, n = parse_tounicode(CMAP)
    assert n == 2
    assert (m[1], m[2], m[3]) == ("H", "fi", "")
    assert (m[0x10], m[0x11], m[0x12]) == ("a", "b", "c")
    assert (m[0x20], m[0x21]) == ("X", "Y")


def test_a_one_byte_cmap_reports_one_byte():
    assert parse_tounicode(b"1 beginbfchar <41> <0041> endbfchar")[1] == 1


def test_type0_font_decodes_two_byte_codes_with_w_and_dw():
    res = {"/Subtype": "/Type0", "/BaseFont": "/ABCDEF+Calibri", "/ToUnicode": Stream(CMAP),
           "/DescendantFonts": [{"/DW": 1000, "/W": [1, [722, 444], 16, 18, 500]}]}
    f = load_font(res)
    assert (f.name, f.nbytes) == ("ABCDEF+Calibri", 2)
    assert f.decode(b"\x00\x01\x00\x02\x00\x11\x00\x99") == [
        (1, "H", 722.0), (2, "fi", 444.0), (0x11, "b", 500.0), (0x99, REPLACEMENT, 1000.0)]


def test_type0_font_dereferences_indirect_dw_w_and_descendant_font_entry():
    res = {"/Subtype": "/Type0", "/BaseFont": "/ABCDEF+Calibri",
           "/DescendantFonts": Ref([Ref({"/DW": Ref(1000), "/W": Ref([1, [722, 444]])})])}
    f = load_font(res)
    assert f.default_width == 1000.0
    assert f.decode(b"\x00\x01\x00\x02\x00\x99") == [
        (1, REPLACEMENT, 722.0), (2, REPLACEMENT, 444.0), (0x99, REPLACEMENT, 1000.0)]


def test_simple_font_uses_widths_the_codec_and_differences():
    res = {"/Subtype": "/TrueType", "/BaseFont": "/Arial,Bold", "/FirstChar": 65, "/Widths": [600, 650],
           "/FontDescriptor": {"/MissingWidth": 250},
           "/Encoding": {"/BaseEncoding": "/WinAnsiEncoding", "/Differences": [1, "/bullet", "/fi"]}}
    f = load_font(res)
    assert f.decode(b"AB\x93\x01\x02") == [(65, "A", 600.0), (66, "B", 650.0), (0x93, "“", 250.0),
                                          (1, "•", 250.0), (2, "ﬁ", 250.0)]


def test_simple_font_dereferences_indirect_first_char_and_missing_width():
    res = {"/Subtype": "/TrueType", "/BaseFont": "/Arial,Bold", "/FirstChar": Ref(65), "/Widths": [600],
           "/FontDescriptor": {"/MissingWidth": Ref(250)}}
    f = load_font(res)
    assert f.decode(b"A\x99") == [(65, "A", 600.0), (0x99, "™", 250.0)]


def test_unmapped_control_codes_and_undefined_bytes_are_replacements():
    f = PdfFont("X")
    assert [t for _c, t, _w in f.decode(b"\x05\x81A")] == [REPLACEMENT, REPLACEMENT, "A"]


def test_a_broken_font_resource_still_gives_a_font():
    f = load_font({"/Subtype": "/Type0", "/BaseFont": "/Broken"})     # no descendant fonts
    assert f.name == "Broken" and f.decode(b"\x00\x41")[0][1] == REPLACEMENT


def test_a_tounicode_that_cannot_be_read_still_leaves_the_widths_loaded():
    res = {"/Subtype": "/TrueType", "/BaseFont": "/Arial", "/FirstChar": 65, "/Widths": [600, 650],
           "/ToUnicode": BoomStream()}
    f = load_font(res)
    assert f.decode(b"AB") == [(65, "A", 600.0), (66, "B", 650.0)]


def test_a_bad_widths_entry_still_leaves_the_character_map_loaded():
    res = {"/Subtype": "/TrueType", "/BaseFont": "/Arial", "/FirstChar": 65, "/Widths": ["nope"],
           "/ToUnicode": Stream(CMAP)}
    f = load_font(res)
    assert f.to_unicode[1] == "H"
    assert f.widths == {}                     # the bad entry left the width table empty, not the font broken
