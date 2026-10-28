@echo off
setlocal
cd /d "%~dp0"
set "PYW=%~dp0_internal\python\pythonw.exe"
if not exist "%PYW%" set "PYW=%~dp0.venv\Scripts\pythonw.exe"
if not exist "%PYW%" (
  echo Delta could not find its Python ^(_internal\python\pythonw.exe^) next to this file.
  echo Extract the whole zip, then double-click Delta.cmd inside the extracted folder.
  pause
  exit /b 1
)
set "LOG=%LOCALAPPDATA%\Delta\delta.log"
if "%LOCALAPPDATA%"=="" set "LOG=%~dp0delta.log"
if not "%LOCALAPPDATA%"=="" if not exist "%LOCALAPPDATA%\Delta" mkdir "%LOCALAPPDATA%\Delta" 2>nul
if not "%LOCALAPPDATA%"=="" if not exist "%LOCALAPPDATA%\Delta" set "LOG=%~dp0delta.log"
>>"%LOG%" echo === launching "%PYW%"
rem The shortcut with the icon (Delta.lnk beside this file) is written by the app itself.
start "" "%PYW%" -m delta serve --log="%LOG%" --shortcut="%~f0"
endlocal
