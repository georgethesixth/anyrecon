# anyrecon: how it works and how it handles data

This is the full technical guide. It explains what the tool does at each step, exactly where your data goes
(and doesn't), and how the code is organised, in enough detail for someone else to maintain or improve it.

- **Users:** read [What it does](#what-it-does) and [Data handling](#data-handling).
- **Contributors:** read everything; [Working on the code](#working-on-the-code) has the practical steps.

Source: [github.com/georgethesixth/anyrecon](https://github.com/georgethesixth/anyrecon). Licence: MIT.
Card-data compliance detail lives in [PCI_DSS.md](https://github.com/georgethesixth/anyrecon/blob/main/docs/PCI_DSS.md);
this guide summarises it.

## Contents

1. [What it does](#what-it-does)
2. [Design rules](#design-rules)
3. [Data handling](#data-handling)
4. [Card data (PCI DSS)](#card-data-pci-dss)
5. [The pipeline, step by step](#the-pipeline-step-by-step)
6. [The app](#the-app)
7. [The two versions](#the-two-versions)
8. [Data size and speed](#data-size-and-speed)
9. [Use it as an app](#use-it-as-an-app)
10. [Download for your computer](#download-for-your-computer)
11. [Outputs](#outputs)
12. [Command line](#command-line)
13. [Configuration](#configuration)
14. [Working on the code](#working-on-the-code)
15. [Known limitations](#known-limitations)
16. [Glossary](#glossary)

## What it does

You give anyrecon two or more files that should agree with each other: a processor export, a general ledger, a
bank statement, a settlement report. They can be CSV, Excel, JSON, PDF or (in the download version)
scanned images. anyrecon:

1. **Reads** each file into a clean table, whatever its layout.
2. **Protects card data** in it before anything else happens.
3. **Works out how the files connect**: which column in one file corresponds to which column in another, even
   when the values are formatted differently or buried inside free text such as a bank narration.
4. **Shows you the proposed connections** with how many rows each one matches and real example values, so you
   can confirm them or pick a different match.
5. **Matches the rows** using fixed rules, in tiers.
6. **Explains everything that doesn't match**, with a reason for each row, and spots patterns such as a
   percentage fee taken at settlement.
7. **Produces** an Excel report, a JSON audit trail and, optionally, a reusable setup file.

## Design rules

These are the rules every change should keep.

| Rule | Why | Where it's enforced |
|---|---|---|
| **Matching is deterministic.** Same inputs and same settings always give the same result. | Reconciliations get audited. A result you can't reproduce is worthless. | `anyrecon/match.py` uses no randomness, no AI, no network. |
| **Every match records the rule that made it.** | An auditor must be able to see *why* two rows were paired. | `Matcher.record()` writes `tier`, `rule` and `confidence` on every match. |
| **Card data is handled before anything else sees the file.** | Nothing downstream (profiling, matching, reports, AI) can leak what it never received. | `ingest.load()` calls `pci.guard()` as its last step, before returning the dataset. |
| **Nothing is stored.** | No database means nothing to breach, back up or delete. | No module writes data to disk except short-lived temporary files, deleted in `finally:` blocks. |
| **AI may explain; it never decides a match.** | Language models are not reproducible. | `anyrecon/llm.py` is only called for commentary and column labels, never from `match.py` or `discover.py`. |
| **Proposals are measured on the data, not guessed from column names.** | Column names lie; the values don't. | `discover.py` scores every candidate by value overlap and uniqueness. |

## Data handling

This section answers: where does a file go, what is kept, and what could leave the machine?

### "Choose files" is not an upload

In the web app, picking or dragging in a file lets the page *open* it, the way a desktop program opens a file from
your disk. The file is read into memory inside the tab and processed there; it is never sent anywhere. Quick
proof: wait for **Ready** in the top bar, switch off your internet connection, and reconcile. It still works. The
download version does the same on your own computer. The picker says so (Streamlit's default "Upload" label is
replaced in `ui_theme.css()`).

### The lifecycle of a file

| Stage | What happens | Where the data is |
|---|---|---|
| 1. You pick files | The browser reads them. | Web app: inside the page. Download version: handed to anyrecon running on the same computer. |
| 2. Held for the session | The raw bytes are kept in the session's memory (`st.session_state.uploads`). | Memory only. |
| 3. Parsing | Each file is written to a **temporary file** so the parsing libraries can open it, parsed, and the temporary file is **deleted immediately** (`app._from_bytes`, `finally: tmp.unlink()`). | Web app: Pyodide's in-memory file system, never your disk. Download version: the operating system's temp folder for a fraction of a second. |
| 4. Card-data guard | Card numbers masked, security codes and PIN data removed (see next section). | Memory. |
| 5. Matching and results | Parsed tables, proposals and results are cached in the session so changing a setting doesn't re-read every file. | Memory. |
| 6. Downloads | The Excel report is built once per run, in memory, and offered as a download. | Saved only where *you* save it. |
| 7. End of session | **Clear all** deletes everything immediately. Closing the tab ends the session; the download version drops it shortly after (Streamlit's disconnected-session timeout). | Gone. |

**Not kept anywhere:** no database, no data logs, no analytics, no caches of your data on disk. The web app's
offline copy (see [Use it as an app](#use-it-as-an-app)) holds only the app's own files, never yours.

**One caveat to be precise about:** in the download version, if the program is killed in the split second
between writing a temporary file and deleting it, that file stays in the temp folder until the OS cleans it. The
file holds the original, before masking.

### What can leave the machine

| Version | Network traffic | Your files |
|---|---|---|
| **Web app** (in a tab or added as an app) | The page downloads its own code (Python runtime, engine, UI) from the site that served it, and checks for an updated version when online. Nothing else. | **Never sent anywhere.** The page's security policy (`Content-Security-Policy: connect-src 'self'`) stops it from sending data to any other site, and the site has no endpoint that accepts uploads. |
| **Download version** | First run downloads Python packages from PyPI. After that, none. The app listens on `127.0.0.1` only, so other computers can't reach it. Streamlit usage statistics are switched off. | Stay on your computer. |
| **Command line, with AI commentary** (`--explain`, off by default) | One request to the AI provider per explanation. | Only summary figures, match rules and column names. Row values only with `--share-samples`, then at most 15 exception rows, already masked. |

The public site at anyrecon.vercel.app is the web app. Vercel, like any web host, logs that a visit happened
(time, address, which file was requested). Your files are not part of any request, so they are not in those logs.

### How the web app is locked down

- **Everything is served from the same site.** The Python runtime (Pyodide), the UI framework (stlite/Streamlit)
  and every Python package are copied into the site at build time. No CDNs, no package downloads at runtime. This
  also means it works behind corporate proxies that block PyPI or CDNs.
- **Security headers** (set in `vercel.json` and repeated in the page itself):
  - `connect-src 'self'`: the page may only fetch from its own site.
  - `form-action 'none'`, `base-uri 'none'`, `object-src 'none'`.
  - `script-src` allows `blob:` and `data:` because the Python worker is started from one; `'wasm-unsafe-eval'`
    and `'unsafe-eval'` because Pyodide compiles WebAssembly and Python bytecode.
  - `Referrer-Policy: no-referrer`, `X-Content-Type-Options: nosniff`, `Cross-Origin-Opener-Policy: same-origin`,
    and a `Permissions-Policy` that switches off camera, microphone and geolocation.
- **A known harmless console message:** before a download, stlite checks a placeholder address
  (`stlite.invalid`). The policy blocks it, as intended; downloads still work.

## Card data (PCI DSS)

Code: `anyrecon/pci.py`, function `guard()`. It runs on every dataset straight after parsing.

### What it detects and does (default `strict` mode)

| Data | How it's detected | What happens |
|---|---|---|
| **Card security codes (CVV/CVC/CID)** | Column name contains a CVV word (cvv, cvc, cvv2, cid, csc, "security code"…) and ≥80% of values are 3–4 digits. | Column **removed**. Security codes are never kept, not even masked (PCI DSS 3.3.1). |
| **PIN / PIN block** | Column name contains pin / pin block. | Column **removed**. |
| **Magnetic-stripe track data** | Column name says track/magstripe, or values match the track-1/track-2 pattern. | Column **removed**. |
| **Full card numbers (PAN)** | 13–19 digits (spaces or dashes allowed), first digit 2–6, passes the Luhn check. | **Masked** to first 6 and last 4 (`510510******4101`), in every column including free text (PCI DSS 3.4.1). |
| **A column that *is* card numbers** | ≥50% of values are pure 13–19 digit numbers and ≥90% of those pass Luhn. | Masked, plus a hidden token column `__tok_<column>`: a keyed HMAC-SHA256 of the full number, so the card number can still be used to match rows without being kept (PCI DSS 3.5.1.1). |
| **Already-masked card numbers** | Values look like `123456******1234`. | Left as they are and noted. |
| **References that happen to pass Luhn** | A digit column where most values are 13–19 digits but under half pass Luhn: these are transaction references, and a few will pass Luhn by chance (1 in 10). | Left as they are, and flagged with a **"Mask anyway"** option. |
| **Unlabelled columns next to card numbers** that look like CVVs (3–4 digits, generic or hinting name) or PIN blocks (16 hex characters) | Only checked when the file has card numbers. | **Removed to be safe**, with an option for you to restore it after confirming it isn't card security data. Your decision is recorded in the report. |

Every action is recorded as a *finding* (`models.Finding`): column, kind, action, count, explanation. Findings
never contain the sensitive values themselves. They appear on the file cards and in the optional
audit trail.

### Modes

| Mode | Behaviour |
|---|---|
| `strict` (default) | As above. |
| `paranoid` | Also masks Luhn-passing values in reference columns. Safer, but can break matching on references that look like card numbers. |
| `block` | Refuses to load any file that contains a full card number or security data. |

Change it under **Advanced → Settings → Card data**, or with `--pci` on the command line.

### Tokens

Tokens are keyed with a random secret generated when the program starts, so they only match within one run.
Set `ANYRECON_PAN_KEY` (download version and command line) for tokens that stay the same across runs.

### Who is responsible for what

See [PCI_DSS.md](https://github.com/georgethesixth/anyrecon/blob/main/docs/PCI_DSS.md) for the full scenario
table. In short: the guard makes sure the tool's *outputs* never contain full card numbers or security data,
but the *input* files you load are your organisation's responsibility. Run the download version on a computer inside
your card-data environment, or use the web app, which never sends the files anywhere.

## The pipeline, step by step

```
files ─▶ ingest ─▶ PCI guard ─▶ profile ─▶ discover ─▶ connect ─▶ match ─▶ insights ─▶ chains ─▶ report
         ingest.py  pci.py      profile.py discover.py  chain.py   match.py match.py    chain.py   report.py
```

### 1. Ingest: `anyrecon/ingest.py`

`load(path, name, sheet, pci_mode, mask_columns, keep_columns) → Dataset`

**Readers by format**

| Format | How |
|---|---|
| CSV / TSV / TXT | Encoding tried in order: UTF-8 (with BOM), cp1252, Latin-1. Delimiter picked from `,` `;` tab `\|` by which gives the most consistent column count over the first 60 lines. |
| Excel (.xlsx/.xlsm/.xls) | All sheets read as text. Hidden sheets ignored. Default: the visible sheet with the most data. Options: one named sheet; stack all sheets with the same layout (monthly tabs; adds a `Sheet` column); or one dataset per sheet (`load_each_sheet`). Password-protected files are detected and explained. |
| JSON | A list of records, or an object containing one (the longest list is used). Nested fields flattened (`pd.json_normalize`). |
| PDF | `pdfplumber` table extraction per page; falls back to text-aligned extraction when no ruled table is found. Pages with no text layer are OCR'd (Desktop/Server). |
| Images (.png/.jpg/.tif) | Tesseract OCR. Columns are anchored to the detected header line by horizontal position. Every row keeps its lowest word confidence in `__ocr_conf`. |

**Turning raw rows into a table** (`frame_from_raw`)

1. Drop empty rows and columns.
2. **Find the header row** in the first 30 rows: the row scoring highest on fill × share of label-like cells ×
   uniqueness × how well the rows below it are filled. Rows above it (report titles, account details) are skipped.
3. Name blank headers `col_N`; de-duplicate repeated names (`Amount`, `Amount_2`).
4. Remove **repeated header rows** (multi-page PDFs) and **total / balance rows** (`Total`, `Opening balance`,
   `Balance b/f`, `Carried forward`…).
5. PDFs and scans: **join wrapped narrations** back onto the row above (a row with only one text cell filled).
6. Warn when some rows have far fewer cells than the rest (often a summary box on the same page).

**Every row keeps its origin** in the hidden `__row` column: `L12` (line 12), `Sheet1!R40`, `P3:R7` (page 3,
row 7), `J5` (JSON record 5), `P2:O14` (page 2, OCR line 14). Reports use these so you can find the row in the
original file.

**Sanity fixes** (`sanity_fix`), each logged as a note or warning on the file:

| Problem | Fix |
|---|---|
| Long IDs in scientific notation (`4.28E+11`) | **Warning**: digits are already lost (Excel keeps 15 significant digits) and can't be recovered; re-export without opening in Excel. |
| Whole numbers stored as decimals (`42833770659.0`) | Trailing `.0` removed. |
| Excel serial dates (`45931`) in a date column | Converted to dates. |
| Several currencies in one column | **Warning**: amounts are compared as plain numbers; split by currency first. |
| Separate Debit and Credit columns | Combined into `Amount (Dr/Cr)` plus `Direction` (DR/CR). |

Errors a user can act on are raised as `UnreadableFile` with a plain explanation (encrypted file, no table
found, scanned document in the web app).

### 2. Profile: `anyrecon/profile.py`

`profile(dataset) → {column: ColumnProfile}`. For each column:

- **kind**: `id`, `amount`, `date`, `text`, `category` or `other`, decided from the values (share parseable as
  amount or date, uniqueness, length, letters vs digits), with the column name as a tie-breaker.
- **semantic** label from the name: rrn, session_id, stan, reference, batch, amount, fee, balance, date,
  narration, merchant, status, pan.
- Statistics used later: uniqueness, average length, most common *shape* (`A-9999` style), date format.
- **Ambiguous day/month order** (e.g. all dates ≤ 12th) is noted; day-first is assumed, which fits Nigerian and
  most non-US exports.

`parse_amount` handles `1,234.56`, `(1,234.56)` for negatives, `1.234,56`, currency symbols and codes, `CR`/`DR`
suffixes. `parse_date` tries the formats in `DATE_FORMATS` and keeps the one that parses the most values.

`pick_amount` and `pick_date` choose each file's main amount and date column (prefers names like amount, gross,
transaction date; avoids fee, balance, VAT). These are the "Amount" and "Date" shown on each file card.

### 3. Discover how two files connect: `anyrecon/discover.py`

`discover(left, right) → [KeyCandidate…]`, best first. Three families of candidate, all measured on the data:

**a) Column = column.** For every likely identifier column on each side, try each transform on both sides and
measure the overlap:

| Transform | Turns | Into |
|---|---|---|
| `exact` | ` TX-00123 ` | `TX-00123` |
| `alnum` | `tx 00123` | `TX00123` |
| `nozeros` | `00042833770659` | `42833770659` |
| `noprefix` | `NX-0004283` | `4283` |
| `digits` | `RRN:0428-3377` | `4283377` |
| `last12` / `last10` / `last8` | long reference | its last N characters |

Simpler transforms win ties (each has a weight just under 1). Columns of free text only use `exact`/`alnum`
here; finding IDs inside text is the next family's job.

**b) Identifier inside free text** (bank narrations, descriptions). For an ID column on one side and a text column
on the other, `find_in_text` looks for any of the *known* IDs inside each text, in two passes: as a whole token
(`POS SETTL/042833770659/X`), then by scanning the text with separators removed (`0428 3377 0659`). It never
tries to parse the narration's format; it only looks for IDs it already knows, so wording and position don't
matter. Keys shorter than 8 characters are only accepted as whole tokens, because a short number appears inside
a long one by chance too often.

**c) Amount + date** (when no shared identifier exists): each row's amount must appear on the other side within
the date window. Rows where several candidates qualify count as ambiguous and lower the score.

**Scoring.** For each candidate:

- `cov_left`, `cov_right`: share of rows on each side whose transformed value is found on the other side.
- Coverage score = **0.8 × coverage of the smaller file + 0.2 × coverage of the larger file**. A 14-row extract
  that fully matches a 300-row export is a perfect connection even though it covers 5% of the export.
- Multiplied by √(uniqueness) (an ID shared by many rows is a weak link), the transform weight, and a small bonus
  when both column names mean the same thing. Text extraction is weighted 0.96–0.97; amount + date 0.85 and
  reduced by its ambiguity.
- Up to 3 example value pairs are kept for display.

Only the best transform per column pair is kept; the top 8 candidates are returned. For speed, the left file is
sampled to 20,000 rows during discovery (matching itself always uses every row).

### 4. Decide which files to connect: `anyrecon/chain.py`

- `pair_score(candidates)`: the best identifier score, or half the amount + date score when there's no
  identifier.
- `auto_pairs(datasets)`: scores every pair of files and keeps the strongest links that connect every file once,
  a maximum spanning tree (Kruskal). Two files give one connection; *n* files give at most *n − 1*. Links scoring
  under 0.3 are left out, and a file with no good link shows as "not connected".
- `auto_config(left, right)`: turns the candidates into a matching setup. Keys used: identifier candidates
  scoring ≥ 0.15, in score order, while each is at least half as good as the best, up to 2 (the second runs as a
  fallback tier). Amount and date columns from `pick_amount` / `pick_date`. Date window 3 days. Amount tolerance
  0.01.

The user sees these proposals and can change or remove any of them before anything runs (see [The app](#the-app)).

### 5. Match: `anyrecon/match.py`

`reconcile(left, right, PairConfig) → PairResult`. Matching runs in **tiers**. Each tier only sees rows that no
earlier tier matched, so the strongest evidence always wins.

| Tier | Pairs rows by | Base confidence |
|---|---|---|
| `key1`, `key2`… | One per key in the setup: identical transformed values, or an ID found inside the other side's text. | 1.00 exact, 0.98 transformed, 0.95 found in text (×0.95 if found only by scanning with separators removed) |
| `aggregate` (optional) | Many rows on one side summing to one row on the other, grouped by a column such as settlement batch. | 0.85 |
| `composite` | Same amount within the date window, **only when the pairing is unique both ways** and the signs agree (a refund never pairs with a sale). | 0.70 |

**Within a key tier**, for each key value:

- 1 row vs 1 row: a match.
- 1 row vs many (e.g. one settlement line vs the batch's transactions): if the many sum to the one, a 1:n match;
  otherwise if exactly one of them matches the amount, that one is matched and the rest are flagged
  `duplicate_key`; otherwise the group is recorded with its variance (e.g. a short-paid batch).
- Many vs many: paired off by amount; leftovers flagged `duplicate_key`.

**Each match gets a status:**

| Status | Meaning |
|---|---|
| `matched` | Amount within tolerance and dates within the window. |
| `amount_variance` | Linked, but the amounts differ by more than the tolerance. |
| `date_variance` | Linked, but the dates are further apart than the window. |
| `needs_review` | A row came from OCR with confidence under 80%. OCR rows are never auto-confirmed. |

Confidence is multiplied by 0.6 for anything not `matched`.

**Amount rules.** Amounts are compared as absolute values by default. A match is within tolerance when the
difference is ≤ the absolute tolerance (default 0.01) **or** ≤ the percentage tolerance (default 0). With an
expected fee *f*%, the right side is expected to be left × (1 − *f*/100), e.g. a bank credit net of a 1.5% MDR.

**Unmatched rows** become exceptions: `missing_in_<other file>`, or a more specific reason recorded during
matching (`duplicate_key`, `ambiguous_amount` when several rows on the other side share the amount and date).

**Near-miss suggestions** for unmatched rows (`_suggestions`):

- possible key typo: an unmatched key ≥ 85% similar to an unmatched key on the other side;
- for narration matches: a narration that *nearly* contains an unmatched ID (≥ 90% similar) where the amount
  and date also agree, which usually means a typo or an OCR misread.

Similarity uses `rapidfuzz` when installed, otherwise Python's `difflib` (`anyrecon/fuzzy.py`).

### 6. Insights and automatic fee detection

`Matcher._insights` looks at the amount variances (needs at least 5):

- If ≥ 70% of them sit within ±0.05 percentage points of the same percentage, it reports a **percentage fee**
  (e.g. MDR) and records it as `detected_fee_pct`.
- If ≥ 70% differ by the same fixed amount, it reports a **fixed per-transaction fee**.
- If the median date gap of matches is ≥ 1 day, it reports the **settlement lag** (T+1, T+2).

`chain.reconcile_auto` uses this: when a percentage fee between 0 and 20% is detected and no fee was set, it
re-runs the pair with that fee and keeps the re-run **only if it matches more**. Results then say
"1.5% fee deducted in bank (detected)".

### 7. Chains across three or more files: `chain.build_chains`

With several connections, every match is a link between rows of two files. The chain view picks an **anchor**
file (the one in the most connections), and for each anchor row follows the links through every other file. A
row reaching every file is `complete` (or `complete_with_variance`); otherwise `partial` with the missing files
listed. Rows in other files that never reach the anchor are listed as `only_in_<file>`.

Tracing never passes back through another anchor row, so one settlement batch that covers 30 transactions does
not merge those 30 transactions into one chain.

### 8. Reports: `anyrecon/report.py`, `anyrecon/templates.py`

See [Outputs](#outputs).

## The app

`app.py` (Streamlit) is one script that reruns top to bottom on every interaction; expensive steps are cached in
`st.session_state` under keys built from the file hash and settings, so a rerun only recomputes what changed.
`ui_theme.py` holds the look (CSS) and the HTML pieces: landing page, file cards, connection diagram and cards.

### Flow

1. **Landing page.** In the web app this is plain HTML in `index.html`, shown instantly while the
   engine loads behind it (see [Web app](#browser)).
2. **Add files.** One upload box; files are named after their file name.
3. **Your files.** A card per file: format, rows, columns, detected amount and date columns, card-data actions,
   and a **Preview** of the first 20 rows (already masked). Anything needing a decision (a suspected security-code
   column, a warning) opens automatically.
4. **How your files connect.** The proposals from `auto_pairs` / `auto_config`:
   - a diagram: files as boxes, connections as lines labelled with the key and match %; colour green ≥ 90%,
     amber ≥ 60%, red below; **1** or **\*** at each end shows whether the key is unique on that side (uniqueness
     ≥ 98%) or repeats (e.g. one batch ID on many transactions);
   - a card per connection: the rule, "Matches X of Y rows" for both files with bars, and three real example
     pairs. The headline % is judged on the smaller file;
   - **Change** (pick the two files and the match from the ranked candidates, each with its match %),
     **Remove**, **Add a connection**;
   - **Confirm and reconcile**. Nothing runs before this.
5. **Results.** A summary line, **Excel report** and **Audit trail** downloads, a tab per connection (busiest
   first) and an **All documents** tab for chains. Each connection shows what it matched on, five figures,
   insights, and a switch between Exceptions, Matches and each side's unmatched rows.

Confirmation is tied to a signature of the files and the connections. Change a file or a connection and you're
asked to confirm again; change nothing and the results come straight from the cache.

### Advanced

The **Advanced** switch shows every choice the simple flow makes for you: card-data mode, date window, amount
tolerance; sheet handling for multi-sheet workbooks; per-file previews and column profiles; pairs; the keys for
each pair in priority order; amount and date columns; expected fee (0 means detect automatically); percentage
tolerance; the amount + date fallback; and saving or loading a setup file.

## The two versions

Both run the same engine and the same app, and give the same results. The difference is where they run, and so
how much data they handle comfortably (measured in the next section).

| | Web app | Download version |
|---|---|---|
| Runs | In a browser tab, or in its own window once added as an app (Pyodide: Python compiled to WebAssembly) | On your computer (regular Python + Streamlit), opened in your browser |
| Install | Nothing. Optionally "add as an app" from Chrome or Edge in two clicks | Download a 1 MB ZIP; needs Python 3.10+; the first run sets itself up |
| Comfortable size | See [Data size and speed](#data-size-and-speed) | See [Data size and speed](#data-size-and-speed) |
| Works offline | Once added as an app and opened once | After the first run |
| Scanned documents (OCR) | No: Tesseract can't run in a browser | Yes, with Tesseract installed |
| Updates | Automatic | Download the new ZIP |

**Why the web app handles less data:** it runs inside the browser's WebAssembly sandbox, which gives a page at
most 4 GB of memory (in practice Chrome allows less), runs Python on a single thread, and is typically 2–3 times
slower than native Python. Adding it as an app doesn't change this: the installed app *is* the same page in its own
window. The download version uses regular Python with all of the computer's memory.

<a id="browser"></a>
### Web app: `browser/`

`browser/build.py` assembles a static site in `web/`:

1. Downloads stlite (Streamlit for the browser) from npm at a pinned version, and Pyodide (the Python runtime).
2. Works out the Python packages the app needs. Pure-Python wheels are bundled and imported straight from the
   wheel at start-up (`app.py` adds them to `sys.path`), including `pdfplumber` and `pdfminer`.
3. Copies the app (`app.py`, `ui_theme.py`, `anyrecon/*.py`) into the site.
4. Writes `index.html` with:
   - the landing page as static HTML (`ui_theme.landing_page`), shown at once;
   - the security policy;
   - `boot.js`, which starts the engine underneath the landing page, shows "Preparing engine" → "Ready" in the
     top bar, carries a click made before it's ready through once it is, and **prefetches the UI pieces** listed
     in `prefetch.txt` in the background (with retries), so nothing has to be downloaded when results appear;
   - a fallback notice with a **Reload** button if a piece still fails to load.
5. Makes it installable (see [Use it as an app](#use-it-as-an-app)): `manifest.webmanifest`, icons from
   `browser/assets/`, and `sw.js`.
6. Renders this guide (`docs/GUIDE.md`) to `guide.html` and the changelog (`CHANGELOG.md`) to `changelog.html`.

The site is published by committing the built `web/` folder; Vercel serves it as static files
(`vercel.json`: no build step, security headers, long cache for the immutable runtime files, no cache for
`sw.js` and the manifest; `.vercelignore`: only `web/` and `vercel.json` are uploaded).

Browser-specific behaviour in the code: `sys.platform == "emscripten"`. Things to know:

- **pdfminer's debug logging is switched off** (`ingest.py`). In the browser every log line is forwarded to the
  page, which made PDF parsing about 80 times slower and could crash the tab.
- Scanned documents raise a clear "use the download version" message.
- The first visit downloads tens of megabytes (the Python runtime and packages); the runtime files are marked
  immutable, so later visits load them from the browser cache.

### Download version: launchers at the repository root, user guide in `editions/desktop/`

Three launchers sit at the top of the download so users find them straight away: `Start anyrecon (Windows).bat`,
`Start anyrecon (Mac).command` and `start-anyrecon-linux.sh`. Each one:

1. Finds a Python that actually runs and is 3.10 or newer. Windows tries the `py` launcher, then `python`, and
   runs each (the Microsoft Store puts a `python` shortcut on PATH that exists but doesn't run). Mac and Linux try
   `python3.13` down to `python3`; on a fresh Mac `/usr/bin/python3` is only a stub that offers to install Apple's
   developer tools. If none works: opens python.org (Windows/Mac) and explains what to tick, or prints the package
   command (Linux), and points to the web app.
2. On first run, creates `.venv` inside the folder and runs `pip install -e ".[ui,ocr]"`. Success writes the marker
   file `.venv/anyrecon-ready`; without it, the next start resumes setup, so an interrupted install never leaves a
   broken copy.
3. Starts Streamlit on `127.0.0.1` (not reachable from other computers) with usage statistics off.

No administrator rights are needed. `START HERE.txt` at the root repeats the steps for people who open the ZIP
before reading anything else. `.gitattributes` keeps Windows line endings in the `.bat` and leaves the built
website (`web/`) out of GitHub's ZIP download, which keeps it at about 1 MB. Tesseract is optional, for scans.
`.streamlit/config.toml` holds the theme and settings.

## Data size and speed

How much data each version handles comfortably, measured with `scripts/benchmark.py`. The benchmark builds three
realistic files of the same length (a processor export; a ledger with prefixed references; a bank statement with
the reference buried in the narration and a 1.5% fee deducted; a few percent of breaks on each side) and times
what a user waits for: reading the files, proposing the connections, matching, and the Excel report.

**Comfortable sizes:** the web app up to about **250,000 rows per file** (37 MB for three files), at most about
500,000. The download version up to about **1,000,000 rows per file** (150 MB) on a computer with 8 GB of memory,
and further with more memory.

| Rows per file | Data (3 files) | Web app | Download version | Download version memory |
|---|---|---|---|---|
| 10,000 | 1.5 MB | 17 s | 6 s | 0.2 GB |
| 50,000 | 7.5 MB | 57 s | 25 s | 0.4 GB |
| 100,000 | 15 MB | 1.8 min | 48 s | 0.6 GB |
| 250,000 | 37 MB | 4.2 min | 2.0 min | 1.3 GB |
| 500,000 | 75 MB | 8.9 min, close to its memory limit | 3.8 min | 2.7 GB |
| 1,000,000 | 150 MB | Doesn't fit (see below) | 8.0 min | 5.3 GB |

**Why the web app stops sooner.** The web app's engine runs inside the browser, which gives it at most 4 GB of
memory per tab, whatever the computer has. At 500,000 rows per file the browser used about 3.7 GB; 1,000,000 rows
need about 5.3 GB even in the more frugal download version, so they don't fit (an estimate from the measurements
above, not a crash test). It is also about twice as slow: the same Python code runs compiled for the browser. The
installed app is the same engine in its own window, with the same limits. The download version uses the
computer's own Python, so it can use all of the computer's memory.

**Time and memory grow in proportion to the data**, roughly 0.5 s and 5 MB per 1,000 rows per file in the download
version, so the table can be extended in a straight line.

**Reading the table:**

- *Rows per file* is the length of each of the three files; the total is three times that.
- Times are end to end, from choosing the files to seeing results, on a modest machine (2 CPU cores, 8 GB of
  memory); the web app's one-off engine start on first visit (about 20 s) isn't included. A recent laptop is faster.
- Measured 16 Nov 2026 (version 0.3.0); the download version's 500,000 and 1,000,000 rows re-measured 27 Nov
  (0.3.1), after the report change.
- Two files are quicker than three: one connection to propose and match instead of two. Wide files (many columns)
  take longer than narrow ones, and PDFs are slower to read than CSV or Excel (about a tenth of a second per page).
- The Excel report holds up to 1,048,576 rows per sheet; longer tables continue on extra sheets.

Re-run it on your own machine: `python scripts/benchmark.py` (download version) or
`python scripts/benchmark.py --browser` (web app, needs `web/` built and Playwright).

## Use it as an app

In Chrome or Edge, the web app can be added as an app: the install icon at the right end of the address bar, or
the **Install app** button at the top of the page. It then opens in its own window from the Start menu, Dock or
desktop. It is a Progressive Web App:

- `manifest.webmanifest` gives the name, icons and "open in its own window" (`display: standalone`).
- `sw.js`, a service worker, keeps a copy of the app's own files (the page, the engine, the UI). The page and the
  app's Python files are fetched from the network first so updates arrive, falling back to the copy when offline;
  the versioned runtime files (`/pyodide/`, `/stlite/`, `/wheels/`) are served from the copy. Each build has a new
  version number, and old copies are deleted when it activates.
- The service worker never sees user files: those are opened inside the page and never requested over the network.

Once added and opened once, it starts with no internet connection (tested: opened offline in 0.2 seconds and
reconciled four files). It handles the same amount of data as the web page, because it is the same page.
Remove it from the app's ⋮ menu → **Uninstall**. Safari on Mac can add it to the Dock (File → Add to Dock); Firefox
doesn't install web apps.

## Download for your computer

For large files, scanned documents, or working offline from the first run. Same app, same results; files never
leave the computer. The home page offers it under **Download for your computer**, with the visitor's system
pre-selected. Full user instructions:
[editions/desktop/README.md](https://github.com/georgethesixth/anyrecon/blob/main/editions/desktop/README.md).

**Download:** [the ZIP](https://github.com/georgethesixth/anyrecon/archive/refs/heads/main.zip) (about 1 MB). It
unzips into a folder called `anyrecon-main`.

| | Windows | Mac | Linux |
|---|---|---|---|
| Start | Double-click `Start anyrecon (Windows).bat` | Right-click `Start anyrecon (Mac).command` → Open → Open | `bash start-anyrecon-linux.sh` |
| First-time warning | "Windows protected your PC" → More info → Run anyway | "unidentified developer" → the right-click handles it | none |
| Python | python.org installer, tick "Add python.exe to PATH"; installs for your user, no admin rights | python.org installer; may ask for your password | `sudo apt install python3 python3-venv` or equivalent |
| Stop | Close the black window | Close the Terminal window | Ctrl+C |

**What it needs:**

- **Python 3.10 or newer.** The launcher checks and helps install it.
- **Internet on the first run only**, to download its components from pypi.org into the folder (2–5 minutes).
  After that it works offline.
- **Optional:** Tesseract, to read scanned documents.

**What it changes on the computer:** nothing outside its own folder. Delete the folder to remove it.

**When it won't work, and what to do:**

| Situation | What happens | What to do |
|---|---|---|
| IT doesn't allow installing Python | The launcher can't find Python | Use the web app, or ask IT |
| IT blocks `.bat` or `.command` files | Nothing runs | Same |
| The company network blocks pypi.org | "Setup could not download what it needs" | Ask IT to allow pypi.org once, or do the first run on another network; the launcher resumes where it stopped |
| The folder is read-only (e.g. inside a ZIP preview, or a synced drive) | "Could not create the environment" | Unzip properly and move the folder to Documents |
| Port 8501 is in use | Streamlit says so | anyrecon is already running in another window |

**Updating:** download the new ZIP, copy any saved setups (`.json`) across, delete the old folder. The first start
sets itself up again. What changed in each version: [changelog](https://anyrecon.vercel.app/changelog.html).

**Tested:** the Linux launcher, end to end from a clean download, including resuming an interrupted setup. The
Windows and Mac launchers follow the same steps but have not yet been run on real machines by the maintainer.
Reports welcome.

## Outputs

**Excel report** (`report.write_excel`, tables built in `anyrecon/export.py`). The user picks the sheets under
**Download report**; Matched and Exceptions are ticked by default. Sheets that don't apply to the run aren't offered.

| Sheet | Default | Contents |
|---|---|---|
| **Matched** | ✓ | Records that link and agree: key, date and amount on each side, how they were linked, and a group number when one record links to several. |
| **Exceptions** | ✓ | Everything that didn't reconcile, one row each: key, where (only in one file, or in both but different), date and amount on each side, the **likely reason** and the **action**. Rows with no clear reason come first: those are the true exceptions. |
| Groups | optional; offered when some links aren't one-to-one | Each reference that links more than one record: how many records on each side, totals, whether they agree. |
| Overview | optional | Counts for each comparison: records, matched, different, only in each file, with a likely reason, no clear reason. |
| Only in each file | optional | The full original rows found in one file only. |
| Across all files | optional; offered with 3+ files | Each record traced across every file. |

With one comparison, columns carry the file names ("Amount (processor)"). With several, they share one sheet, the
columns say A and B, and a **Compared** column names the files ("processor (A) ↔ bank (B)").

**Reasons the Exceptions sheet gives today**, each with its action:

| Reason | Action |
|---|---|
| Amount differs in line with the file-wide percentage the matcher found (a fee taken or a charge added) | Confirm the rate is agreed |
| Timing: dates N days apart (beyond the date window) | Confirm the dates; it should clear |
| Dated outside the other file's date range | Check the next (or previous) file |
| Possible typo: a near-identical reference on the other side | Check the reference |
| Same reference appears more than once | Check for a duplicate entry |
| Several possible matches with the same amount and date | Choose the right match |
| Read from a scan with low confidence | Check against the original |
| **No clear reason** | **Investigate** |

When a percentage difference is consistent across a file, it is applied automatically (in either direction) and
those records move to Matched, with "2% higher in bank" in **Linked by**.

The report contains rows from your files (with card numbers masked), so treat it like the source files.

**Audit trail (JSON, optional tick under Download report)** (`report.audit_json`): engine and Python version, run time, each input's hash, rows,
format, column fingerprint, notes and card-data findings, and each connection's setup, summary and insights.
**No row data.**

**Setup file** (`templates.py`, Advanced → Save setup): file names, column names, layout fingerprints and the
matching rules. **No data values**, so it is safe to share or commit. Loading it on next month's files checks the
layout and warns about missing or changed columns.

## Command line

`anyrecon` (installed with the package) does everything the app does, for scripting and scheduled jobs.

```bash
anyrecon inspect FILE...                       # parse; show card-data actions, notes, column profiles
anyrecon suggest LEFT RIGHT [--window 3]       # ranked identifier candidates for one pair
anyrecon run -f processor=proc.csv -f bank=bank.pdf \
             [-p processor:bank]               # pairs (default: first file vs each other)
             [--fee processor:bank=1.5]        # expected fee on the right side
             [--window 3] [--tol 0.01]
             [--template setup.json] [--save-template setup.json]
             [-i]                              # confirm keys and columns interactively
             [--out report.xlsx] [--audit audit.json]
             [--explain [--share-samples]]     # AI commentary (needs ANTHROPIC_API_KEY)
# on every command:
             [--pci strict|paranoid|block] [--mask-col name:column] [--keep-col name:column]
```

Exit codes: 2 = blocked by card-data `block` mode; 3 = a file couldn't be read.

## Configuration

| Variable | Effect |
|---|---|
| `ANYRECON_PAN_KEY` | Secret for card-number tokens that stay the same across runs. |
| `ANYRECON_EDITION` | `desktop` (default) or `server`; changes the wording only. |
| `ANTHROPIC_API_KEY` | Turns on optional AI commentary (Desktop/Server, needs `pip install anthropic`). |
| `ANYRECON_LLM_MODEL` | Model for the commentary. |

## Working on the code

### Repository layout

| Path | What it is |
|---|---|
| `anyrecon/` | The engine (no UI code). `models` data structures · `ingest` reading files · `pci` card-data guard · `profile` column types · `discover` connection candidates · `chain` pairing, fee re-run, chains · `match` matching tiers · `report` Excel and audit · `templates` setup files · `llm` optional AI · `fuzzy` similarity · `cli` command line |
| `app.py` | The Streamlit app used by all three editions. |
| `ui_theme.py` | CSS and HTML pieces for the app and the static landing page. |
| `.streamlit/config.toml` | Streamlit theme and settings (Desktop/Server). |
| `editions/browser/` | `build.py` (builds the static site), `check.py` (end-to-end test), `prefetch.txt` (UI pieces to preload). |
| `Start anyrecon (Windows).bat`, `Start anyrecon (Mac).command`, `start-anyrecon-linux.sh`, `START HERE.txt` | Desktop edition launchers and instructions, at the root so users find them in the download. |
| `editions/desktop/` | User guide for the download version. |
| `.gitattributes` | Keeps `web/` out of GitHub's ZIP download and Windows line endings in the `.bat`. |
| `web/` | The built web app, served by Vercel. Generated: rebuild, don't edit. |
| `examples/generate_samples.py` | Writes synthetic, deliberately messy test files (CSV, Excel, PDF, JSON, a scan) to `examples/data/`. Fake card numbers use test-only ranges. |
| `tests/test_engine.py` | Engine tests. |
| `scripts/pan_scan.py` | Pre-commit hook that blocks commits containing card numbers. |
| `docs/` | This guide and the PCI DSS notes. |

### Set up

```bash
git clone https://github.com/georgethesixth/anyrecon && cd anyrecon
python -m venv .venv && . .venv/bin/activate
pip install -e ".[ui,ocr,dev]"
pre-commit install                     # card-number check on every commit (pip install pre-commit)
python examples/generate_samples.py    # test files in examples/data/
pytest                                 # engine tests
streamlit run app.py                   # the app, as the download version runs it
```

### Change the web app

```bash
pip install markdown playwright && python -m playwright install chromium
python editions/browser/build.py --out web && rm web/_headers     # needs npm and internet
python editions/browser/check.py                                  # end-to-end test, outside network blocked
git add -A && git commit && git push                              # Vercel redeploys
```

After upgrading stlite (`STLITE_VERSION` in `build.py`) or using a widget the app didn't use before, run
`check.py --record-prefetch`, then rebuild, so the new UI pieces are preloaded. `build.py` warns when names in
`prefetch.txt` no longer exist.

### Common changes

- **A new file format:** add a reader in `ingest.load()` that returns raw rows, pass them through
  `frame_from_raw` (header detection and cleanup come free), give each row an origin id, and add a test.
  The PCI guard runs automatically.
- **A new identifier transform:** add it to `TRANSFORMS` in `discover.py` with a weight just under the simpler
  ones, and to `apply_transform`. It is then tried for every column pair and usable as a key.
- **A new matching tier:** add a method to `Matcher` that only looks at rows where `used` is false, calls
  `self.record(...)` with a clear rule text and a base confidence, and call it from `run()` in the right order
  (stronger evidence first).
- **A new insight:** add it to `Matcher._insights`; keep it to facts computed from the matches.
- **UI:** keep Simple mode free of choices that the data can answer; put manual control under Advanced.
  New HTML pieces go in `ui_theme.py`; escape every value with `esc()`.

### Rules for contributions

- Never let raw card data past `pci.guard`, and never add a code path that reads files without going through
  `ingest.load`.
- Never commit real data. Use `examples/generate_samples.py` or invent values; the pre-commit hook blocks
  card numbers.
- Matching stays deterministic: no randomness, no AI, no network in `match.py` / `discover.py`.
- Every new kind of match or exception explains itself in its `rule` or `detail` text.
- Add a test in `tests/` for every engine change. Run `editions/browser/check.py` for UI changes.

## Known limitations

Honest list of what doesn't work yet, roughly in order of impact. Good places to contribute.

- **No currency conversion.** Mixed currencies are flagged, not converted.
- **Only percentage fees are applied automatically.** Fixed per-transaction fees are detected and reported but
  not applied; and with automatic detection on, you can't force "no fee" (Advanced treats a fee of 0 as
  "detect").
- **Scans need the download version.** OCR quality depends on the scan; low-confidence rows are always
  sent for review.
- **Web app limits:** the first visit downloads the Python runtime (about 20 seconds on a good line);
  very large files (hundreds of thousands of rows) are slow or run out of memory in a browser tab.
- **Discovery samples 20,000 rows** of the left file; near-miss suggestions look at up to 5,000 unmatched rows.
- **Day/month order** is assumed day-first when the data can't tell.
- **The Change panel** covers the key and the files; amount/date columns and fees are under Advanced.
- **Untested platforms:** the Windows and Mac start files have not been run end to end by the
  maintainer yet. Reports welcome.
- **The download version needs Python and, on first run, access to pypi.org.** A ready-to-run app per system (no
  Python needed) is on the roadmap; without paid code-signing it would show the same "unidentified developer"
  warnings.

Ideas on the roadmap: FX rates; applying fixed fees; connectors that pull files from processor APIs or SFTP; a
local AI option with no data leaving the machine; saved setups selectable from the Simple flow.

## Glossary

| Term | Meaning |
|---|---|
| **Connection** | A pair of files that should agree, plus the rule that links their rows. |
| **Key / identifier** | A value both files share for the same transaction (RRN, STAN, session ID, reference). |
| **Transform** | A normalisation applied before comparing keys (strip zeros, prefixes, punctuation). |
| **Tier** | One matching pass. Later tiers only see rows earlier tiers left unmatched. |
| **Exception / break** | A row or group that didn't reconcile, with its reason. |
| **Coverage** | Share of a file's rows whose key is found in the other file. |
| **Cardinality (1 / \*)** | Whether a key is unique in a file (1) or repeats (\*), e.g. a batch ID across many transactions. |
| **MDR** | Merchant discount rate: the percentage fee deducted before settlement. |
| **PAN** | Primary account number: the full card number. |
| **SAD** | Sensitive authentication data: security codes, PIN data, magnetic-stripe track data. Never kept. |
| **Luhn check** | The checksum every real card number passes. |
| **Chain** | One transaction traced across three or more files. |
