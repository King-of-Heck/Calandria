from pathlib import Path

CMD = Path(__file__).resolve().parent.parent / "Calandria.cmd"


def test_launcher_runs_pythonw_detached_with_a_log_and_no_console():
    raw = CMD.read_bytes()
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")      # a .cmd keeps CRLF
    text = raw.decode("ascii")
    assert r"%~dp0_internal\python\pythonw.exe" in text
    assert r"%~dp0.venv\Scripts\pythonw.exe" in text                         # the dev checkout
    assert 'start "" "%PYW%" -m calandria serve --log="%LOG%"' in text
    assert "python.exe" not in text.replace("pythonw.exe", "")               # never the console interpreter
    assert r"%LOCALAPPDATA%\Calandria\calandria.log" in text
    assert "pause" in text                                                    # the only visible failure path


def test_launcher_stamps_the_log_before_it_starts_anything():
    text = CMD.read_bytes().decode("ascii")
    assert r'mkdir "%LOCALAPPDATA%\Calandria"' in text                        # the folder may not exist yet
    stamp = '>>"%LOG%" echo === launching %PYW%'
    assert stamp in text
    # the stamp goes in before the program is started, so an empty log means the launcher never ran
    assert text.index(stamp) < text.index('start "" "%PYW%"')
