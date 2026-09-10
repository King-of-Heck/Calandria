import subprocess

from calandria.server import launch


def _install_edge(root):
    exe = root / "Microsoft" / "Edge" / "Application" / "msedge.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"MZ")
    return str(exe)


def test_edge_path_checks_the_roots_in_order(tmp_path):
    x86, pf, local = tmp_path / "x86", tmp_path / "pf", tmp_path / "local"
    in_pf = _install_edge(pf)
    env = {"ProgramFiles(x86)": str(x86), "ProgramFiles": str(pf), "LOCALAPPDATA": str(local)}
    assert launch.edge_path(env) == in_pf
    in_x86 = _install_edge(x86)
    assert launch.edge_path(env) == in_x86              # Program Files (x86) wins when both exist
    assert launch.edge_path({"ProgramFiles": str(local)}) is None
    assert launch.edge_path({}) is None
    assert launch.edge_path({"ProgramFiles": ""}) is None


def test_open_viewer_launches_edge_in_app_mode(tmp_path, monkeypatch):
    exe = _install_edge(tmp_path)
    calls = []
    monkeypatch.setattr(launch.webbrowser, "open", lambda url: calls.append(("browser", url)))

    def popen(args, **kw):
        calls.append(("popen", args, kw))

    how = launch.open_viewer("http://127.0.0.1:5/", env={"ProgramFiles": str(tmp_path)}, popen=popen)
    assert how == "edge"
    assert calls == [("popen", [exe, "--app=http://127.0.0.1:5/"],
                      {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL})]


def test_open_viewer_falls_back_to_the_browser_without_edge(monkeypatch):
    opened = []
    monkeypatch.setattr(launch.webbrowser, "open", lambda url: opened.append(url))
    assert launch.open_viewer("http://127.0.0.1:5/", env={}, popen=lambda *a, **k: 1/0) == "browser"
    assert opened == ["http://127.0.0.1:5/"]


def test_open_viewer_falls_back_when_edge_cannot_start(tmp_path, monkeypatch, capsys):
    _install_edge(tmp_path)
    opened = []
    monkeypatch.setattr(launch.webbrowser, "open", lambda url: opened.append(url))

    def popen(args, **kw):
        raise OSError("blocked")

    assert launch.open_viewer("http://127.0.0.1:5/", env={"ProgramFiles": str(tmp_path)}, popen=popen) == "browser"
    assert opened == ["http://127.0.0.1:5/"]
    assert "edge did not start: 'blocked'" in capsys.readouterr().err      # the log says why
