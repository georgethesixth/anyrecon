#!/bin/bash
# anyrecon - Desktop edition for Linux. Run:  bash start-anyrecon-linux.sh
# The first run sets itself up (2–5 minutes). Everything is installed inside this folder (.venv);
# delete the folder to remove it.
cd "$(dirname "$0")" || exit 1
echo ""
echo "  anyrecon · Desktop edition"
echo "  --------------------------"
echo ""

finish() { echo ""; [ -t 0 ] && read -r -p "  Press Enter to close." _; exit "${1:-1}"; }

PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >/dev/null 2>&1; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "  Python 3.10 or newer is needed. Install it with your package manager, for example:"
  echo "    sudo apt install python3 python3-venv      (Debian / Ubuntu)"
  echo "    sudo dnf install python3                   (Fedora)"
  echo "  Or use the browser version: https://anyrecon.vercel.app"
  finish 1
fi
if ! "$PY" -c "import venv, ensurepip" >/dev/null 2>&1; then
  echo "  Python's venv module is missing. On Debian / Ubuntu: sudo apt install python3-venv"
  finish 1
fi

if [ ! -f ".venv/anyrecon-ready" ]; then
  echo "  First run: setting up. This happens once and takes 2–5 minutes."
  echo ""
  if [ ! -x ".venv/bin/python" ]; then
    "$PY" -m venv .venv || { echo "  Could not create the environment in this folder."; finish 1; }
  fi
  ./.venv/bin/python -m pip install --upgrade pip --disable-pip-version-check -q
  if ! ./.venv/bin/python -m pip install -e ".[ui,ocr]" --disable-pip-version-check; then
    echo ""
    echo "  Setup could not download what it needs. Check your connection (pypi.org must be reachable)"
    echo "  and run this again; it picks up where it stopped. After the first run anyrecon works offline."
    finish 1
  fi
  echo ok > .venv/anyrecon-ready
  echo ""
fi

command -v tesseract >/dev/null 2>&1 || echo "  Note: reading scanned documents needs Tesseract (optional): sudo apt install tesseract-ocr"
echo "  Starting. anyrecon will open in your browser. Press Ctrl+C here to stop it."
echo ""
./.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
