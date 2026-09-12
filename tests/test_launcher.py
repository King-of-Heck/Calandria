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
    stamp = '>>"%LOG%" echo === launching "%PYW%"'                       # quoted: & or ^ in the path
    assert stamp in text
    # the stamp goes in before the program is started, so an empty log means the launcher never ran
    assert text.index(stamp) < text.index('start "" "%PYW%"')


def test_launcher_falls_back_to_a_log_next_to_itself_when_the_folder_cannot_be_made():
    text = CMD.read_bytes().decode("ascii")
    mkdir = text.index(r'mkdir "%LOCALAPPDATA%\Calandria"')
    fallback = text.index(r'if not exist "%LOCALAPPDATA%\Calandria" set "LOG=%~dp0calandria.log"')
    assert mkdir < fallback < text.index('>>"%LOG%"')


def test_launcher_refreshes_a_shortcut_with_the_icon_after_starting_the_app():
    """A .cmd cannot carry an icon; a shortcut can. After the app is started (so the launch is not
    delayed) the launcher rewrites Calandria.lnk beside itself with Calandria.ico, through an inline
    PowerShell command (the Restricted execution policy blocks script files, not -Command). Rewriting
    on every launch keeps the shortcut right after the folder is moved."""
    text = CMD.read_bytes().decode("ascii")
    start = text.index('start "" "%PYW%"')
    guard = text.index(r'if exist "%~dp0Calandria.ico"')
    assert start < guard                                                     # the app first
    ps = text[guard:]
    assert "powershell" in ps and "-NoProfile" in ps and "-NonInteractive" in ps and "-Command" in ps
    assert "WScript.Shell" in ps and "CreateShortcut" in ps and "$s.Save()" in ps
    # the paths reach PowerShell through the environment, never spliced into its command line
    # (an apostrophe or a quote in the folder name would break a literal)
    assert "$env:CAL_LNK" in ps and "$env:CAL_CMD" in ps and "$env:CAL_ICO" in ps and "$env:CAL_DIR" in ps
    assert r'set "CAL_LNK=%~dp0Calandria.lnk"' in text and r'set "CAL_ICO=%~dp0Calandria.ico"' in text
    assert r'set "CAL_CMD=%~f0"' in text and r'set "CAL_DIR=%~dp0"' in text
    assert "%~dp0" not in ps.split("-Command", 1)[1].split("\r\n", 1)[0]     # nothing of the path in the literal
    assert '>>"%LOG%" 2>&1' in ps                                             # a failure is diagnosable, never visible
