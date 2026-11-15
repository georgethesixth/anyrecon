# anyrecon · Desktop edition

For large files, scanned documents and working offline. Runs on your own computer; your files never leave it.

> Can't install anything on your work laptop? Use the **[Browser edition](https://anyrecon.vercel.app)**: nothing
> to install, and files never leave the browser tab.

About 10 minutes the first time; after that, one double-click.

## 1. Download

Go to **[anyrecon.vercel.app → Run it on your computer](https://anyrecon.vercel.app/#download)** and click
**Download** (a ZIP of about 1 MB). Or on GitHub: green **Code** button → **Download ZIP**.

Unzip it (double-click on Mac; right-click → **Extract All** on Windows). You get a folder called
**`anyrecon-main`**. Move it somewhere easy to find, such as Documents. Inside, **`START HERE.txt`** has these
steps in short.

## 2. Start anyrecon

**Windows:** in `anyrecon-main`, double-click **`Start anyrecon (Windows).bat`**.
If Windows shows "Windows protected your PC", click **More info → Run anyway**. It's a plain text script; open it in
Notepad to see exactly what it does.

**Mac:** in `anyrecon-main`, **right-click** `Start anyrecon (Mac).command` → **Open** → **Open**.
(The right-click is needed the first time only, because macOS is cautious with downloaded scripts.)
If nothing happens: open the **Terminal** app, type `bash ` (with a space), drag the file into the window, press Enter.

**Linux:** in a terminal, in the `anyrecon-main` folder: `bash start-anyrecon-linux.sh`

### If Python isn't installed

The starter checks for Python 3.10 or newer. If it's missing, it opens the download page and tells you what to do:

- **Windows:** run the installer and, on the first screen, **tick "Add python.exe to PATH"**, then **Install Now**.
  This installs for your user only and needs no administrator rights. Then double-click the starter again.
- **Mac:** run the installer (it may ask for your Mac password), then start anyrecon again.
- **Linux:** `sudo apt install python3 python3-venv` (Debian/Ubuntu) or your distribution's equivalent.

### The first run

The **first run sets itself up** in 2–5 minutes: it creates a private `.venv` folder inside `anyrecon-main` and
downloads anyrecon's components from pypi.org into it. Nothing is installed anywhere else on your computer and no
administrator rights are needed. If setup is interrupted, the next start picks up where it stopped.

After that, anyrecon starts in seconds and **works offline**.

A browser tab opens at `http://localhost:8501`. That address is **your own computer**, not a website; other
computers on the network can't reach it. Keep the black (Windows) or Terminal (Mac) window open while you work.
**Close it to stop anyrecon.**

## 3. Reconcile

1. Click **Start reconciling** and **add your files**: two or more. CSV, Excel, PDF statements, JSON, even scans.
2. **Your files:** a card per file shows what was read, which columns hold the amount and date, and any card
   numbers that were masked. Click **Preview** to see the first rows. Anything that needs your decision opens by itself.
3. **How your files connect:** anyrecon proposes which files to compare and how, with how many rows each
   connection matches and real examples. **Change** any that look wrong, then click **Confirm and reconcile**.
4. **Results:** one tab per connection with exceptions, matches and unmatched rows. Download the **Excel report**
   and the **Audit trail**.
5. Need full control (sheets, matching columns, fees, tolerances, saved setups)? Switch on **Advanced** at the top.
6. When you're done, click **Clear all**, or close the browser tab and the black window.

## 4. Optional: reading scanned documents (OCR)

Only needed for photos, scans, or PDFs that are images rather than text.

- **Windows:** download the installer from <https://github.com/UB-Mannheim/tesseract/wiki> and install with default
  options. anyrecon finds it automatically.
- **Mac:** install Homebrew from <https://brew.sh>, then in Terminal: `brew install tesseract`.
- **Linux:** `sudo apt install tesseract-ocr`

Scanned rows are always marked for review, never matched automatically, because a misread digit in an amount can't
be detected by the computer. Use the original digital export whenever you can.

## 5. Optional: AI commentary

Plain-English explanation of the results. Off by default. Needs an Anthropic API key and sends only summary figures
and column names, never your rows. See the [guide](https://anyrecon.vercel.app/guide.html#data-handling).

## Troubleshooting

| What you see | What to do |
|---|---|
| "Python 3.10 or newer is needed" | Install Python (see above). On Windows, reinstall and tick **Add python.exe to PATH** |
| "Setup could not download what it needs" | Check your internet connection and start again; it resumes. On a company network, pypi.org may be blocked: ask IT to allow it once, or do the first run on another network |
| "Could not create the environment" | Move the `anyrecon-main` folder to Documents (some folders are read-only) and try again |
| Windows: "Windows protected your PC" | **More info → Run anyway** |
| Windows: the file opens in Notepad instead of running | Right-click it → **Open** |
| Mac: "cannot be opened because it is from an unidentified developer" | Right-click → **Open** → **Open** |
| Browser didn't open | Open your browser and go to `http://localhost:8501` |
| "Port 8501 is already in use" | anyrecon is already running in another window; use that one or close it |
| "password-protected or encrypted" | Open the file, save a copy without a password, and use that |
| "scientific notation … digits are lost" | The file was opened and saved in Excel, which damaged long references. Get the original export again and don't open it in Excel first |
| "Tesseract is not installed" | See step 4, or use a digital (non-scanned) version of the file |
| Something else | Open an issue on GitHub with the message shown (never attach your real files) |

## Updating

Download the new ZIP and unzip it. Copy any saved setups (`.json` files) across, then delete the old folder. The
first start after an update sets itself up again (2–5 minutes).

## Removing

Delete the `anyrecon-main` folder. Nothing else was installed. (Python stays installed if you installed it for
anyrecon; remove it from your system's apps list if you no longer need it.)
