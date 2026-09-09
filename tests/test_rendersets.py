import json

import pytest

from calandria.pdf.rendersets import (BLACK_AND_WHITE, EFFECTS, RENDER_SETS, STANDARD, CatStyle,
                                      RenderSet, render_set)


def test_standard_matches_the_litera_defaults():
    s = STANDARD
    assert s.name == "Standard"
    assert (s.insert.color, s.insert.effects) == ("0000ff", frozenset({"double-underline"}))
    assert (s.delete.color, s.delete.effects) == ("ff0000", frozenset({"strikethrough"}))
    assert (s.move_from.color, s.move_from.effects) == ("008000", frozenset({"strikethrough"}))
    assert (s.move_to.color, s.move_to.effects) == ("008000", frozenset({"double-underline"}))
    assert (s.formatting.color, s.formatting.effects) == ("7c3aed", frozenset({"dotted-underline"}))
    assert (s.cell_inserted, s.cell_deleted, s.cell_merged, s.cell_split, s.table_moved) == \
        ("e6e6fa", "ffdead", "008080", "ff00ff", "ccffcc")
    for c in (s.insert, s.delete, s.formatting, s.move_from, s.move_to):
        assert c.background is None and c.prefix == "" and c.suffix == ""


def test_black_and_white_is_black_with_the_same_effects_and_no_fills():
    b, s = BLACK_AND_WHITE, STANDARD
    assert b.name == "Black and White"
    for name in ("insert", "delete", "formatting", "move_from", "move_to"):
        assert getattr(b, name).color == "000000"
        assert getattr(b, name).effects == getattr(s, name).effects
    assert (b.cell_inserted, b.cell_deleted, b.cell_merged, b.cell_split, b.table_moved) == (None,) * 5


def test_registry_and_lookup():
    assert list(RENDER_SETS) == ["Standard", "Black and White"]
    assert render_set("Standard") is STANDARD and render_set("Black and White") is BLACK_AND_WHITE
    with pytest.raises(KeyError) as e:
        render_set("Sepia")
    assert "Standard" in str(e.value) and "Black and White" in str(e.value)


def test_category_maps_run_mode_and_formatting_flag():
    s = STANDARD
    assert s.category("ins", False) is s.insert and s.category("ins", True) is s.insert
    assert s.category("del", False) is s.delete
    assert s.category("eq", True) is s.formatting
    assert s.category("eq", False) is None


def test_effects_are_validated():
    with pytest.raises(ValueError):
        CatStyle("000000", frozenset({"blink"}))
    assert EFFECTS == {"bold", "italic", "underline", "double-underline", "dotted-underline",
                       "strikethrough", "double-strikethrough"}


def test_to_dict_is_json_with_sorted_effects():
    d = STANDARD.to_dict()
    json.dumps(d)
    assert d["name"] == "Standard" and d["insert"] == {"color": "0000ff", "effects": ["double-underline"],
                                                       "background": None, "prefix": "", "suffix": ""}
    assert d["cell_inserted"] == "e6e6fa"


def test_render_set_is_immutable_data():
    with pytest.raises(Exception):
        STANDARD.name = "x"          # frozen dataclass
    assert isinstance(STANDARD, RenderSet)
