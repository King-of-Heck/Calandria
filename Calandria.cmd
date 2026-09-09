@echo off
setlocal
cd /d "%~dp0"
set "PY="
if exist "%~dp0python\python.exe" set "PY=%~dp0python\python.exe"
if not defined PY if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
if not defined PY set "PY=python"
echo Starting Calandria (close this window or use Quit in the browser to stop it) ...
"%PY%" -m calandria serve
if errorlevel 1 (
  echo.
  echo Calandria could not start ^(exit code %errorlevel%^).
  pause
)
endlocal
