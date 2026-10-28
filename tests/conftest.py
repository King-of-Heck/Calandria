import pytest


@pytest.fixture(autouse=True)
def _no_real_desktop(monkeypatch, tmp_path_factory):
    """`serve --shortcut` also puts a shortcut on the Desktop and a marker in %LOCALAPPDATA%/Delta;
    no test may touch the real ones."""
    root = tmp_path_factory.mktemp("user")
    (root / "Desktop").mkdir()
    monkeypatch.setattr("delta.__main__.desktop_folder", lambda: str(root / "Desktop"))
    monkeypatch.setattr("delta.__main__.data_folder", lambda: str(root / "data"))
    return root
