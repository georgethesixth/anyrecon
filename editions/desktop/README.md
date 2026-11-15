# anyrecon · Desktop edition

For large files and scanned documents. Runs on your own computer.

> On a locked-down work laptop where you can't install software? Use the **[Browser edition](../browser/README.md)** instead.

Your files never leave your computer. About 10 minutes the first time; after that, one double-click.

## 1. Download anyrecon

1. Open the project page on GitHub.
2. Click the green **Code** button → **Download ZIP**.
3. Find the ZIP in your Downloads folder and unzip it (double-click on Mac; right-click → **Extract All** on Windows).
4. Move the unzipped `anyrecon` folder somewhere easy to find, e.g. Documents.

## 2. Install Python (one time)

Python is the free program anyrecon runs on.

**Windows**
1. Go to <https://www.python.org/downloads/> and click the yellow **Download Python** button.
2. Open the downloaded file.
3. **Important:** on the first screen, tick **"Add python.exe to PATH"** at the bottom, then click **Install Now**.

**Mac**
1. Go to <https://www.python.org/downloads/> and click **Download Python**.
2. Open the downloaded file and click through the installer.

Already have Python 3.10 or newer? Skip this step.

## 3. Start anyrecon

**Windows:** open `anyrecon` → `editions` → `desktop` and double-click **`Start anyrecon (Windows).bat`**.
If Windows shows "Windows protected your PC", click **More info → Run anyway**. It's a plain text
script; you can open it in Notepad to see exactly what it does.

**Mac:** open `anyrecon` → `editions` → `desktop`, **right-click** `Start anyrecon (Mac).command` → **Open** → **Open**.
(Right-click is needed only the first time, because macOS is cautious with downloaded scripts.)
If nothing happens: open the **Terminal** app, type `bash ` (with a space), drag the file into the window, and press Enter.

**Linux:** `editions/desktop/start-anyrecon-linux.sh`

The **first run** installs what anyrecon needs; this takes 2–5 minutes and needs internet. After that,
it starts in seconds, and works offline (except the optional AI commentary).

A browser tab opens at `http://localhost:8501`. That address is **your own computer**, not a website.
Keep the black window open while you work. **Close it to stop anyrecon.**

## 4. Reconcile

1. **Add your files**: drag in two or more. CSV, Excel, PDF statements, JSON, even photos/scans.
2. Check each file's panel. anyrecon tells you what it did: skipped title rows, removed totals,
   masked card numbers. **Red messages need your attention** (e.g. a column whose long numbers were
   damaged by Excel). Workbooks with several tabs let you pick one tab, stack monthly tabs, or use each tab separately.
3. **Choose which files to compare** (e.g. *processor ⟷ bank*). Choose as many pairs as you like;
   three or more files are linked into one end-to-end view automatically.
4. For each pair, anyrecon shows the **matching options it found**, best first, with how much of each file
   each option covers and an example. The best ones are pre-selected; change them if you know better.
   Adjust the amount, date, fee % (e.g. 1.5 for a 1.5% charge the bank deducts) and tolerance if needed.
5. Click **Reconcile**. Review exceptions, matches and unmatched items on screen.
6. Download the **Excel report**. Click **Save setup as template** to reuse the same settings next month in one step.
7. When you're done, click **Clear all data from this session** (or just close the browser tab and the black window).

## 5. Optional: reading scanned documents (OCR)

Only needed for photos, scans, or PDFs that are images rather than text.

- **Windows:** download the installer from <https://github.com/UB-Mannheim/tesseract/wiki> and install
  with default options. anyrecon finds it automatically.
- **Mac:** install Homebrew from <https://brew.sh>, then in Terminal: `brew install tesseract`.

Scanned rows are always marked for review, never matched automatically, because a misread digit in
an amount can't be detected by the computer. Use the original digital export whenever you can.

## 6. Optional: AI commentary

Plain-English explanation of the results. Off by default. Needs an Anthropic API key and sends only
summary figures and column names, never your rows. See the README.

## Troubleshooting

| What you see | What to do |
|---|---|
| "Python is not installed" | Do step 2. On Windows, reinstall and tick **Add python.exe to PATH** |
| "Install failed" on first run | Check your internet connection and double-click the starter again |
| Browser didn't open | Open your browser and go to `http://localhost:8501` |
| "password-protected or encrypted" | Open the file, save a copy without a password, and use that |
| "scientific notation … digits are lost" | The file was opened and saved in Excel, which damaged long references. Get the original export again and don't open it in Excel first, or export it as CSV/text from the source system |
| "Tesseract is not installed" | Do step 5, or use a digital (non-scanned) version of the file |
| Port already in use | anyrecon is already running in another window; use that one or close it |
| Something else | Open an issue on GitHub with the message shown (never attach your real files) |

## Updating

Download the new ZIP, unzip it, and **copy your saved templates** (`.json` files) into it. Delete the old
folder. The first start after an update reinstalls (2–5 minutes).
