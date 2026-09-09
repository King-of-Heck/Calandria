import json
from calandria.__main__ import main
from calandria.testing.makedocx import make_docx, DOC, P


def test_dump(tmp_path, capsys):
    f = tmp_path / "x.docx"
    f.write_bytes(make_docx({"word/document.xml": DOC(P("Héllo"))}))
    assert main(["dump", str(f)]) == 0
    out = capsys.readouterr().out
    assert out.isascii()
    assert json.loads(out)[0]["text"] == "Héllo"


def test_usage(capsys):
    assert main([]) == 2
    assert "usage" in capsys.readouterr().out.lower()


def _write(tmp_path, name, body):
    p = tmp_path / name
    p.write_bytes(make_docx({"word/document.xml": DOC(body)}))
    return str(p)


def test_compare_prints_change_model_json(tmp_path, capsys):
    # "Beta gamma" / "beta gamma" pair at similarity 0.5 (a lone "Beta"/"beta" would not pair).
    a = _write(tmp_path, "a.docx", P("Alpha") + P("Beta gamma"))
    b = _write(tmp_path, "b.docx", P("Alpha") + P("beta gamma"))
    assert main(["compare", a, b]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["summary"]["total"] == 1 and out["changes"][1]["cat"] == "punctuation"
    assert out["options"] == {"ignore_case": False, "count_numbering": True}
    assert main(["compare", a, b, "--ignore-case", "--no-count-numbering"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["summary"]["total"] == 0 and out["options"] == {"ignore_case": True, "count_numbering": False}


def test_compare_usage_errors(tmp_path, capsys):
    a = _write(tmp_path, "a.docx", P("x"))
    assert main(["compare", a]) == 2
    assert main(["compare", a, a, "--bogus"]) == 2
    assert "usage" in capsys.readouterr().out
