from pathlib import Path

CMD = Path(__file__).resolve().parent.parent / "Delta.cmd"


def test_launcher_runs_pythonw_detached_with_a_log_and_no_console():
    raw = CMD.read_bytes()
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")      # a .cmd keeps CRLF
    text = raw.decode("ascii")
    assert r"%~dp0_internal\python\pythonw.exe" in text
    assert r"%~dp0.venv\Scripts\pythonw.exe" in text                         # the dev checkout
    assert 'start "" "%PYW%" -m delta serve --log="%LOG%"' in text
    assert "python.exe" not in text.replace("pythonw.exe", "")               # never the console interpreter
    assert r"%LOCALAPPDATA%\Delta\delta.log" in text
    assert "pause" in text                                                    # the only visible failure path


def test_launcher_stamps_the_log_before_it_starts_anything():
    text = CMD.read_bytes().decode("ascii")
    assert r'mkdir "%LOCALAPPDATA%\Delta"' in text                        # the folder may not exist yet
    stamp = '>>"%LOG%" echo === launching "%PYW%"'                       # quoted: & or ^ in the path
    assert stamp in text
    # the stamp goes in before the program is started, so an empty log means the launcher never ran
    assert text.index(stamp) < text.index('start "" "%PYW%"')


def test_launcher_falls_back_to_a_log_next_to_itself_when_the_folder_cannot_be_made():
    text = CMD.read_bytes().decode("ascii")
    mkdir = text.index(r'mkdir "%LOCALAPPDATA%\Delta"')
    fallback = text.index(r'if not exist "%LOCALAPPDATA%\Delta" set "LOG=%~dp0delta.log"')
    assert mkdir < fallback < text.index('>>"%LOG%"')


def test_launcher_leaves_the_shortcut_to_the_app_and_runs_no_powershell():
    """A .cmd cannot carry an icon; a shortcut can. The app writes Delta.lnk beside the launcher
    itself (`--shortcut` names the launcher; the .lnk and the .ico are beside it). The inline
    PowerShell of 2.4.2 is gone: a locked-down machine runs PowerShell in Constrained Language
    Mode, where the WScript.Shell COM object is refused and its errors spilled into the log."""
    text = CMD.read_bytes().decode("ascii")
    assert 'start "" "%PYW%" -m delta serve --log="%LOG%" --shortcut="%~f0"' in text
    assert "powershell" not in text.lower() and "WScript" not in text and ".lnk" not in text.replace("Delta.lnk", "")
    assert "%~f0" in text                                                     # the launcher's own full path
