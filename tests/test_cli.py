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
