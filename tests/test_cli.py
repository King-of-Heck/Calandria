import json
import os
import sys
import time
from datetime import datetime

import pytest
from pypdf import PdfReader

from calandria.__main__ import _open_log, main
from calandria.layout.fonts import default_dirs
from calandria.testing.makedocx import make_docx, DOC, P

_needs_fonts = pytest.mark.skipif(not any(os.path.isdir(d) for d in default_dirs()),
                                  reason="no system font directory on this machine")


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


def test_compare_flags_accepted_in_any_position(tmp_path, capsys):
    a = _write(tmp_path, "a.docx", P("x"))
    b = _write(tmp_path, "b.docx", P("x"))
    assert main(["compare", "--ignore-case", b]) == 2
    assert "usage" in capsys.readouterr().out.lower()
    assert main(["compare", a, "--ignore-case"]) == 2
    assert "usage" in capsys.readouterr().out.lower()
    assert main(["compare", "--ignore-case", a, b]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["options"]["ignore_case"] is True



@_needs_fonts
def test_layout_pages_only(tmp_path, capsys):
    a = _write(tmp_path, "a.docx", P("Alpha"))
    b = _write(tmp_path, "b.docx", P("Alpha") + P("Beta"))
    assert main(["layout", a, b, "--pages"]) == 0
    assert json.loads(capsys.readouterr().out) == {"pages": 1}


@_needs_fonts
def test_layout_model_and_hide_flag(tmp_path, capsys):
    a = _write(tmp_path, "a.docx", P("Alpha"))
    b = _write(tmp_path, "b.docx", P("Alpha") + P("Beta"))
    assert main(["layout", "--hide-unchanged", a, b]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["page_count"] == 1 and d["options"]["show_equal"] is False
    assert [r["t"] for r in d["pages"][0]["lines"][0]["runs"]] == ["Beta"]
    assert d["pages"][0]["lines"][0]["runs"][0]["m"] == "ins"


def test_layout_rejects_unknown_flags_and_wrong_arity(tmp_path, capsys):
    a = _write(tmp_path, "a.docx", P("Alpha"))
    assert main(["layout", a, a, "--bogus"]) == 2
    assert main(["layout", a]) == 2
    assert main(["compare", a, a, "--pages"]) == 2      # a layout-only flag is not a compare flag


@_needs_fonts
def test_pdf_command_writes_the_file_and_reports_pages(tmp_path, capsys):
    a = _write(tmp_path, "a.docx", P("Alpha"))
    b = _write(tmp_path, "b.docx", P("Alpha") + P("Beta"))
    out = str(tmp_path / "red.pdf")
    assert main(["pdf", a, b, out]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d == {"pages": 1, "out": out}
    r = PdfReader(out)
    text = r.pages[0].extract_text()
    assert "Beta" in text and "Comparison summary" in text and "Original: a.docx" in text
    assert "Rendering set: Standard" in text


@_needs_fonts
def test_pdf_command_options(tmp_path, capsys):
    a = _write(tmp_path, "a.docx", P("Alpha"))
    b = _write(tmp_path, "b.docx", P("Alpha") + P("Beta"))
    out = str(tmp_path / "red.pdf")
    assert main(["pdf", "--render-set=Black and White", "--report=first", "--no-change-bars",
                 "--hide-unchanged", a, b, out]) == 0
    assert json.loads(capsys.readouterr().out)["pages"] == 2
    r = PdfReader(out)
    assert "Rendering set: Black and White" in r.pages[0].extract_text()
    assert "Alpha" not in r.pages[1].extract_text() and "Beta" in r.pages[1].extract_text()
    assert main(["pdf", "--report=none", a, b, out]) == 0
    assert json.loads(capsys.readouterr().out)["pages"] == 1
    assert "Comparison summary" not in PdfReader(out).pages[0].extract_text()


@_needs_fonts
def test_pdf_command_stamps_the_report_and_the_metadata_from_one_clock(tmp_path, capsys, monkeypatch):
    import calandria.__main__ as cli

    class _Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 9, 9, 14, 5)

    monkeypatch.setattr(cli, "datetime", _Clock)
    a = _write(tmp_path, "a.docx", P("Alpha"))
    b = _write(tmp_path, "b.docx", P("Alpha") + P("Beta"))
    out = str(tmp_path / "red.pdf")
    assert main(["pdf", a, b, out]) == 0
    capsys.readouterr()
    r = PdfReader(out)
    assert "Compared: 2026-09-09 14:05" in r.pages[0].extract_text()
    assert str(r.metadata["/CreationDate"]).startswith("D:20260909140500")


def test_pdf_command_usage_errors(tmp_path, capsys):
    a = _write(tmp_path, "a.docx", P("x"))
    out = str(tmp_path / "o.pdf")
    assert main(["pdf", a, a]) == 2                              # three positionals needed
    assert main(["pdf", a, a, out, "--pages"]) == 2              # a layout-only flag
    assert main(["pdf", a, a, out, "--report=middle"]) == 2
    assert main(["pdf", a, a, out, "--render-set"]) == 2         # needs =NAME
    assert "usage" in capsys.readouterr().out.lower()
    assert main(["pdf", a, a, out, "--render-set=Sepia"]) == 2
    err = capsys.readouterr().out
    assert "Sepia" in err and "Standard" in err and "Black and White" in err
    assert not os.path.exists(out)


def test_serve_usage_errors(capsys):
    assert main(["serve", "--bogus"]) == 2
    assert main(["serve", "extra"]) == 2
    assert main(["serve", "--port=abc"]) == 2
    assert main(["serve", "--port=70000"]) == 2
    assert main(["serve", "--idle=-1"]) == 2
    assert main(["serve", "--idle=soon"]) == 2
    assert main(["serve", "--idle=nan"]) == 2                # float() takes these; a watchdog cannot
    assert main(["serve", "--idle=inf"]) == 2
    assert "serve" in capsys.readouterr().out


def test_serve_prints_the_url_and_stops_when_idle(capsys, monkeypatch):
    opened = []
    monkeypatch.setattr("calandria.server.app.open_viewer", lambda url: opened.append(url))
    t0 = time.perf_counter()
    assert main(["serve", "--no-browser", "--port=0", "--idle=0.4", "--grace=0.4"]) == 0
    assert time.perf_counter() - t0 < 30
    line = capsys.readouterr().out.splitlines()[0]
    url = json.loads(line)["url"]
    assert url.startswith("http://127.0.0.1:") and url.endswith("/") and opened == []


def test_serve_opens_the_browser_by_default(monkeypatch):
    opened = []
    monkeypatch.setattr("calandria.server.app.open_viewer", lambda url: opened.append(url))
    assert main(["serve", "--idle=0.4", "--grace=0.4"]) == 0
    assert len(opened) == 1 and opened[0].startswith("http://127.0.0.1:")


def test_version_subcommand(capsys):
    from calandria import __version__
    assert main(["version"]) == 0
    assert capsys.readouterr().out.strip() == f"calandria {__version__}"


def test_version_subcommand_takes_no_arguments(capsys):
    assert main(["version", "extra"]) == 2
    assert "usage" in capsys.readouterr().out.lower()


def test_serve_grace_usage_errors(capsys):
    assert main(["serve", "--grace=-1"]) == 2
    assert main(["serve", "--grace=soon"]) == 2
    assert main(["serve", "--grace=inf"]) == 2
    assert "--grace=SECONDS" in capsys.readouterr().out


def test_serve_writes_the_url_line_to_the_log_file(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("calandria.server.app.open_viewer", lambda url: None)
    log = tmp_path / "sub" / "calandria.log"
    assert main(["serve", "--no-browser", "--idle=0.4", "--grace=0.4", f"--log={log}"]) == 0
    lines = log.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("--- ") and "calandria" in lines[0]
    assert json.loads(lines[1])["url"].startswith("http://127.0.0.1:")
    assert json.loads(capsys.readouterr().out.splitlines()[0])["url"] == json.loads(lines[1])["url"]


def test_open_log_binds_missing_streams_and_rotates(tmp_path, monkeypatch):
    log = tmp_path / "c.log"
    log.write_bytes(b"x" * 1_000_001)
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    f = _open_log(str(log))
    try:
        assert sys.stdout is f and sys.stderr is f
        print("hello")
        f.flush()
    finally:
        f.close()
    text = log.read_text(encoding="utf-8")
    assert not text.startswith("x") and text.splitlines()[0].startswith("--- ") and "hello" in text


def test_open_log_appends_when_a_console_exists(tmp_path):
    log = tmp_path / "c.log"
    log.write_text("old\n", encoding="utf-8")
    f = _open_log(str(log))
    f.close()
    assert sys.stdout is not f
    assert log.read_text(encoding="utf-8").startswith("old\n--- ")
