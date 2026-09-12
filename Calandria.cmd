@echo off
setlocal
cd /d "%~dp0"
set "PYW=%~dp0_internal\python\pythonw.exe"
if not exist "%PYW%" set "PYW=%~dp0.venv\Scripts\pythonw.exe"
if not exist "%PYW%" (
  echo Calandria could not find its Python ^(_internal\python\pythonw.exe^) next to this file.
  echo Extract the whole zip, then double-click Calandria.cmd inside the extracted folder.
  pause
  exit /b 1
)
set "LOG=%LOCALAPPDATA%\Calandria\calandria.log"
if "%LOCALAPPDATA%"=="" set "LOG=%~dp0calandria.log"
if not "%LOCALAPPDATA%"=="" if not exist "%LOCALAPPDATA%\Calandria" mkdir "%LOCALAPPDATA%\Calandria" 2>nul
if not "%LOCALAPPDATA%"=="" if not exist "%LOCALAPPDATA%\Calandria" set "LOG=%~dp0calandria.log"
>>"%LOG%" echo === launching "%PYW%"
start "" "%PYW%" -m calandria serve --log="%LOG%"
rem A .cmd cannot carry an icon, a shortcut can: refresh Calandria.lnk beside this file with
rem Calandria.ico (every launch, so a moved folder is followed). Paths go through the environment.
if exist "%~dp0Calandria.ico" (
  set "CAL_LNK=%~dp0Calandria.lnk"
  set "CAL_CMD=%~f0"
  set "CAL_ICO=%~dp0Calandria.ico"
  set "CAL_DIR=%~dp0"
  powershell -NoProfile -NonInteractive -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:CAL_LNK); $s.TargetPath=$env:CAL_CMD; $s.WorkingDirectory=$env:CAL_DIR; $s.IconLocation=$env:CAL_ICO + ',0'; $s.Description='Calandria'; $s.Save()" >>"%LOG%" 2>&1
)
endlocal
