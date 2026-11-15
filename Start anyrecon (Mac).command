#!/bin/bash
# anyrecon - Desktop edition. Double-click to start (the first time: right-click → Open → Open).
# The first run sets itself up (2–5 minutes). Everything is installed inside this folder (.venv);
# delete the folder to remove it.
cd "$(dirname "$0")" || exit 1
clear
echo ""
echo "  anyrecon · Desktop edition"
echo "  --------------------------"
echo ""

finish() { echo ""; read -r -p "  Press Enter to close this window." _; exit "${1:-1}"; }

# 1. A working Python 3.10 or newer. On a fresh Mac, /usr/bin/python3 is only a stub that offers to
#    install Apple's developer tools, so the version is actually tested.
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >/dev/null 2>&1; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "  Python 3.10 or newer is needed and was not found."
  echo ""
  echo "  1. The download page will open. Download the macOS installer and run it."
  echo "     (It may ask for your Mac password.)"
  echo "  2. Double-click this file again."
  echo ""
  echo "  If you can't install Python on this Mac, use the browser version instead:"
  echo "  https://anyrecon.vercel.app  (nothing to install; files never leave your computer)"
  open "https://www.python.org/downloads/macos/"
  finish 1
fi

# 2. First run, or an earlier setup that did not finish.
if [ ! -f ".venv/anyrecon-ready" ]; then
  echo "  First run: setting up. This happens once and takes 2–5 minutes."
  echo ""
  if [ ! -x ".venv/bin/python" ]; then
    "$PY" -m venv .venv || { echo "  Could not create the environment. Move the anyrecon folder to Documents and try again."; finish 1; }
  fi
  ./.venv/bin/python -m pip install --upgrade pip --disable-pip-version-check -q
  if ! ./.venv/bin/python -m pip install -e ".[ui,ocr]" --disable-pip-version-check; then
    echo ""
    echo "  Setup could not download what it needs."
    echo "  - Check your internet connection and double-click this file again; it picks up where it stopped."
    echo "  - On a company network, the download site pypi.org may be blocked. Ask IT to allow it once,"
    echo "    or run this first time on another network. After that, anyrecon works offline."
    echo "  - Or use the browser version: https://anyrecon.vercel.app"
    finish 1
  fi
  echo ok > .venv/anyrecon-ready
  echo ""
fi

command -v tesseract >/dev/null 2>&1 || echo "  Note: reading scanned documents needs Tesseract (optional). See editions/desktop/README.md."
echo "  Starting. anyrecon will open in your browser."
echo "  Keep this window open while you work. Close it to stop anyrecon."
echo ""
./.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
echo ""
echo "  anyrecon has stopped."
finish 0
