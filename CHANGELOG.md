# What's new in anyrecon

| Version | Latest | Updated |
|---|---|---|
| **Web app** (anyrecon.vercel.app, also installable as an app) | 0.3.1 | 27 Nov 2026 |
| **Download version** (Windows, Mac, Linux) | 0.3.1 | 27 Nov 2026 |

Both versions run the same engine and give the same results. The web app updates itself; for the download
version, download the new ZIP. Dates are when a change went live.

## 0.3.1 · 27 Nov 2026

**Fixed**

- **The Excel report was blank after the first column** in every report downloaded since 16 Nov (0.3.0). Each
  sheet now has its data; the release check opens the report and fails on any empty column.

**Report (both versions)**

- **Simpler report, chosen at download.** **Download report** opens a short list: **Matched** and **Exceptions**
  are ticked; Groups, Overview, Only in each file, Across all files and the audit trail are optional.
- **Exceptions explain themselves.** One row per record that didn't reconcile, with the likely reason and what to
  do. Records with no clear reason come first.

**Engine (both versions)**

- **Charges added on top are applied automatically**, not just fees taken off. When one file is consistently
  higher by the same percentage (e.g. +2%), those records now count as matched, labelled "2% higher".
- Records dated outside the other file's period are marked as such ("check the next file").

## 0.3.0 · 16 Nov 2026

**Web app**

- **Add it as an app** from Chrome or Edge: the install icon at the right of the address bar, or the
  **Install app** button. It opens in its own window and, once opened, works with no internet connection.
- **Which version?** table on the home page, with the data size each version handles comfortably, measured.
- This changelog, linked from every page.

**Engine (both versions)**

- **More than twice as fast on large files, using less than half the memory** (100,000 rows per file: 109 s and
  1.5 GB before, 48 s and 0.6 GB after, same results). File cleanup, the card-number check, the search for references in
  narrations and the Excel report were reworked. Near-miss suggestions no longer slow down as files grow.
- The Excel report is built once per run (it was rebuilt on every screen refresh). Tables longer than Excel's
  1,048,576-row limit continue on extra sheets.

**Removed**

- The Server (Docker) edition.
- Optional AI commentary from the app (the command line keeps it).

## 0.2.1 · 15 Nov 2026

**Web app**

- The file picker says **Choose files** and explains that files open in the tab and are never uploaded.
- Sample data removed: the tool works on your own files.
- Full technical guide at [/guide.html](guide.html).
- The parts of the screen the app needs are fetched in the background, with retries; if one still fails to load,
  a plain notice offers **Reload** instead of error boxes.

**Download version**

- **Download for your computer** section on the home page, with steps for Windows, Mac and Linux.
- Start files sit at the top of the download, with a `START HERE.txt`.
- Checks for a working Python 3.10 or newer (including the Windows Store and Mac placeholders that look like
  Python but don't run), resumes an interrupted first-run setup, and explains each problem in plain words.
- The download is about 1 MB.

## 0.2.0 · 15 Nov 2026

**Web app and download version**

- **Simple by default:** add files, check the proposed connections, confirm, see results. Pairs, matching rules
  and fees are worked out automatically; every manual choice is under **Advanced**.
- **Connection preview**, in the style of Power BI's merge preview: a diagram of how the files link, how many rows
  each connection matches on both sides, and real example values. Confirm, change or remove each one.
- A card per file with row and column counts, the detected amount and date columns, card-data actions, and a
  preview of the first rows.
- The home page shows instantly; the engine loads in the background.
- A plain, practical look.

**Engine**

- Chooses which files to compare: the strongest links that connect every file once.
- Detects a consistent percentage fee (for example MDR) and applies it, keeping the result only if more matches.

## 0.1.0 · 15 Nov 2026

First release.

- **Engine:** reads CSV, Excel (several sheets), JSON, PDF statements and scans; masks card numbers and removes
  security codes and PIN data on load; finds the identifiers that link two files, including references buried
  in bank narrations; matches in tiers with fixed rules; traces transactions across three or more files; Excel
  report, audit trail and reusable setups.
- **Editions:** in the browser (anyrecon.vercel.app), on your computer (Windows, Mac, Linux), and a Server edition
  for organisations.
- **Command line** for scripted runs.
