#!/bin/bash
# Double-click to start anyrecon on a Mac. First run installs what it needs (2–5 minutes).
cd "$(dirname "$0")/../.." || exit 1
echo "== anyrecon · Desktop edition =="
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is not installed. Opening the download page: install it, then double-click this file again."
  open "https://www.python.org/downloads/"
  read -r -p "Press Enter to close."
  exit 1
fi
if [ ! -d ".venv" ]; then
  echo "First run: setting up (this happens once)..."
  python3 -m venv .venv || { echo "Could not create the environment."; read -r -p "Press Enter to close."; exit 1; }
  ./.venv/bin/python -m pip install --upgrade pip >/dev/null
  ./.venv/bin/python -m pip install -e ".[ui,ocr]" || { echo "Install failed: check your internet connection and try again."; read -r -p "Press Enter to close."; exit 1; }
fi
if ! command -v tesseract >/dev/null 2>&1; then
  echo "Note: scanned documents need Tesseract (optional). See editions/desktop/README.md."
fi
echo "Starting... your browser will open. Keep this window open while you work; close it to stop."
./.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
