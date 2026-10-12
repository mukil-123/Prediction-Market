@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%\src"
set "LIVE_TRADING=false"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m pm_alpha --root "%CD%" research-loop --open-browser %*
) else (
  py -3 -m pm_alpha --root "%CD%" research-loop --open-browser %*
)
if errorlevel 1 (
  echo Research app stopped with an error. Read the message above.
  echo Python 3.11+ and America/New_York timezone data are required.
)
pause
