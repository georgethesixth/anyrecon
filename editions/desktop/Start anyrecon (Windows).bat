@echo off
REM Double-click to start anyrecon on Windows. First run installs what it needs (2-5 minutes).
cd /d "%~dp0..\.."
echo == anyrecon - Desktop edition ==
set PY=
where py >nul 2>nul && set PY=py -3
if "%PY%"=="" ( where python >nul 2>nul && set PY=python )
if "%PY%"=="" (
  echo Python is not installed. Opening the download page.
  echo Install it, TICK "Add python.exe to PATH", then double-click this file again.
  start https://www.python.org/downloads/
  pause
  exit /b 1
)
if not exist ".venv" (
  echo First run: setting up - this happens once...
  %PY% -m venv .venv || ( echo Could not create the environment. & pause & exit /b 1 )
  .venv\Scripts\python -m pip install --upgrade pip >nul
  .venv\Scripts\python -m pip install -e ".[ui,ocr]" || ( echo Install failed - check your internet connection and try again. & pause & exit /b 1 )
)
where tesseract >nul 2>nul || if not exist "C:\Program Files\Tesseract-OCR\tesseract.exe" echo Note: scanned documents need Tesseract (optional). See editions\desktop\README.md.
echo Starting... your browser will open. Keep this window open while you work; close it to stop.
.venv\Scripts\python -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
pause
