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
if "%LOCALAPPDATA%"=="" (
  set "LOG=%~dp0calandria.log"
) else (
  if not exist "%LOCALAPPDATA%\Calandria" mkdir "%LOCALAPPDATA%\Calandria" 2>nul
)
>>"%LOG%" echo === launching %PYW%
start "" "%PYW%" -m calandria serve --log="%LOG%"
endlocal
