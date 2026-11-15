@echo off
REM anyrecon - Desktop edition. Double-click to start. The first run sets itself up (2-5 minutes).
REM Everything is installed inside this folder (.venv). No administrator rights needed. Delete the folder to remove it.
setlocal
cd /d "%~dp0"
title anyrecon
echo.
echo  anyrecon - Desktop edition
echo  ---------------------------
echo.

REM 1. Find a working Python 3.10 or newer. "py" is the python.org launcher; "python" may be the
REM    Microsoft Store shortcut, which exists but does not run, so each candidate is actually tested.
set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PY=py -3"
if not defined PY python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PY=python"
if not defined PY (
  echo  Python 3.10 or newer is needed and was not found.
  echo.
  echo  1. The download page will open. Download Python and run the installer.
  echo  2. On the first screen, TICK "Add python.exe to PATH", then click "Install Now".
  echo     This installs for your user only and does not need administrator rights.
  echo  3. Double-click this file again.
  echo.
  echo  If your company does not allow installing Python, use the browser version instead:
  echo  https://anyrecon.vercel.app  - nothing to install, files never leave your computer.
  start "" https://www.python.org/downloads/windows/
  echo.
  pause
  exit /b 1
)

REM 2. First run, or an earlier setup that did not finish: set up the private environment.
if not exist ".venv\anyrecon-ready" (
  echo  First run: setting up. This happens once and takes 2-5 minutes.
  echo.
  if not exist ".venv\Scripts\python.exe" (
    %PY% -m venv .venv
    if errorlevel 1 (
      echo  Could not create the environment in this folder.
      echo  Move the anyrecon folder somewhere you can write to, such as Documents, and try again.
      pause
      exit /b 1
    )
  )
  ".venv\Scripts\python.exe" -m pip install --upgrade pip --disable-pip-version-check -q
  ".venv\Scripts\python.exe" -m pip install -e ".[ui,ocr]" --disable-pip-version-check
  if errorlevel 1 (
    echo.
    echo  Setup could not download what it needs.
    echo  - Check your internet connection and double-click this file again; it picks up where it stopped.
    echo  - On a company network, the download site pypi.org may be blocked. Ask IT to allow it once,
    echo    or run this first time on another network. After that, anyrecon works offline.
    echo  - Or use the browser version: https://anyrecon.vercel.app
    pause
    exit /b 1
  )
  echo ok> ".venv\anyrecon-ready"
  echo.
)

where tesseract >nul 2>nul || if not exist "C:\Program Files\Tesseract-OCR\tesseract.exe" echo  Note: reading scanned documents needs Tesseract (optional). See editions\desktop\README.md.
echo  Starting. anyrecon will open in your browser.
echo  Keep this window open while you work. Close it to stop anyrecon.
echo.
".venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
echo.
echo  anyrecon has stopped.
pause
