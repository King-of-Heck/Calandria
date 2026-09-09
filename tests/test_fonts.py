import os

import pytest

from calandria.layout.fonts import FontResolver, default_dirs
from calandria.testing.fakefonts import FakeResolver

pytestmark = pytest.mark.skipif(not any(os.path.isdir(d) for d in default_dirs()),
                                reason="no system font directory on this machine")


@pytest.fixture(scope="module")
def fonts():
    return FontResolver()


def test_word_single_line_spacing_comes_from_hhea(fonts):
    # The values Word shows for single spacing (line height = ascender - descender + lineGap).
    assert round(fonts.face("Calibri").line_height(11), 2) == 13.43
    assert round(fonts.face("Times New Roman").line_height(12), 2) == 13.8
    assert round(fonts.face("Arial").line_height(10), 2) == 11.5


def test_ascent_plus_descent_never_exceeds_line_height(fonts):
    f = fonts.face("Calibri")
    assert f.ascent(11) + f.descent(11) <= f.line_height(11) + 1e-9
    assert f.ascent(11) > 0 and f.descent(11) > 0


def test_advance_width_is_the_hmtx_sum(fonts):
    f = fonts.face("Calibri")
    assert f.width("a", 11) == pytest.approx(981 * 11 / 2048)
    assert f.width("ab", 11) == pytest.approx(f.width("a", 11) + f.width("b", 11))
    assert f.width("", 11) == 0
    assert f.width("a", 22) == pytest.approx(2 * f.width("a", 11))


def test_bold_and_italic_faces_are_distinct_files(fonts):
    r, b, i, bi = (fonts.face("Calibri"), fonts.face("Calibri", bold=True),
                   fonts.face("Calibri", italic=True), fonts.face("Calibri", bold=True, italic=True))
    assert len({r.path, b.path, i.path, bi.path}) == 4
    assert (r.key, b.key, i.key, bi.key) == ("Calibri|", "Calibri|B", "Calibri|I", "Calibri|BI")
    assert not b.synthetic and b.bold and not b.italic


def test_light_face_resolves_by_its_own_name_and_never_shadows_regular(fonts):
    assert os.path.basename(fonts.face("Calibri Light").path).lower() == "calibril.ttf"
    assert os.path.basename(fonts.face("Calibri").path).lower() == "calibri.ttf"


def test_family_lookup_is_case_insensitive(fonts):
    assert fonts.face("CALIBRI").path == fonts.face("calibri").path


def test_unknown_family_falls_back(fonts):
    assert fonts.fallback in ("Calibri", "Times New Roman", "Arial")
    assert fonts.face("No Such Font 123").family == fonts.fallback
    assert fonts.face(None).family == fonts.fallback
    assert fonts.face("").family == fonts.fallback


def test_substitution_map(fonts):
    assert fonts.face("Helvetica").family == "Arial"
    assert fonts.face("Cambria Math").family == "Cambria"


def test_missing_style_is_synthesized_from_the_nearest_present_face(fonts):
    f = fonts.face("Symbol", bold=True)
    assert f.synthetic and f.bold and f.key == "Symbol|B"
    assert f.path == fonts.face("Symbol").path


def test_missing_glyph_still_has_a_width(fonts):
    assert fonts.face("Calibri").width("\U0001F600", 11) > 0


def test_ttc_collection_family(fonts):
    assert fonts.face("Cambria").path.lower().endswith(".ttc")
    assert fonts.face("Cambria").line_height(11) > 11


def test_faces_are_cached(fonts):
    assert fonts.face("Arial") is fonts.face("Arial")
    assert fonts.face("Arial") is not fonts.face("Arial", bold=True)


def test_env_dirs_override_and_empty_dir_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("CALANDRIA_FONT_DIRS", str(tmp_path))
    assert default_dirs() == [str(tmp_path)]
    with pytest.raises(RuntimeError):
        FontResolver()


def test_fake_resolver_surface():
    fr = FakeResolver()
    f = fr.face("Anything", bold=True)
    assert f.key == "Anything|B" and f.width("abcd", 10) == 20 and f.line_height(10) == 12
    assert f.ascent(10) == 8 and f.descent(10) == pytest.approx(4)
    assert fr.face("Anything", bold=True) is f
    assert fr.face(None).family == fr.fallback == "Fake"
