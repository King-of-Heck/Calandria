"""harness/build_corpus.py: a pair with a missing side must not reach the manifest."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("build_corpus", ROOT / "harness" / "build_corpus.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _setup(tmp_path, monkeypatch):
    mod = _load()
    fixtures = tmp_path / "sw" / "tests" / "fixtures"
    fixtures.mkdir(parents=True)
    corpus = tmp_path / "corpus"
    monkeypatch.setattr(mod, "CORPUS", corpus)
    monkeypatch.setenv("SORKWHARE_DIR", str(tmp_path / "sw"))
    return mod, fixtures, corpus


def _manifest(path, pairs):
    path.write_text(json.dumps({"pairs": pairs}), "utf8")
    return path


def test_complete_pairs_are_copied_and_listed(tmp_path, monkeypatch):
    mod, fixtures, corpus = _setup(tmp_path, monkeypatch)
    for name in ("okA.docx", "okB.docx"):
        (fixtures / name).write_bytes(b"x")
    m = _manifest(tmp_path / "m.json", [{"alias": "ok", "a": "okA.docx", "b": "okB.docx"}])
    mod.main(["build_corpus.py", str(m)])
    assert json.loads((corpus / "manifest.json").read_text("utf8"))["pairs"][0]["alias"] == "ok"
    assert (corpus / "okA.docx").exists() and (corpus / "okB.docx").exists()


def test_pair_with_a_missing_side_is_excluded_and_exits_nonzero(tmp_path, monkeypatch, capsys):
    mod, fixtures, corpus = _setup(tmp_path, monkeypatch)
    for name in ("okA.docx", "okB.docx", "goneA.docx"):
        (fixtures / name).write_bytes(b"x")
    m = _manifest(tmp_path / "m.json", [{"alias": "ok", "a": "okA.docx", "b": "okB.docx"},
                                        {"alias": "gone", "a": "goneA.docx", "b": "goneB.docx"}])
    with pytest.raises(SystemExit) as exc:
        mod.main(["build_corpus.py", str(m)])
    assert exc.value.code == 1
    assert [p["alias"] for p in json.loads((corpus / "manifest.json").read_text("utf8"))["pairs"]] == ["ok"]
    # The surviving half of the broken pair is not copied either -- nothing half-built lands.
    assert not (corpus / "goneA.docx").exists()
    assert "goneB.docx" in capsys.readouterr().out
