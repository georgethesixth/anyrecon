"""Load any supported document into a clean, headered table.

Supported: CSV/TSV/TXT, XLSX/XLSM/XLS, JSON, text PDFs (table extraction),
scanned PDFs and images (OCR; every OCR row carries a confidence score).
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from pathlib import Path

import logging

import pandas as pd

from . import pci

# pdfminer logs at DEBUG level on every token. Harmless on a desktop, but in the Browser edition each log
# record is forwarded to the page, which slowed PDF parsing ~80x and could crash the tab.
for _name in ("pdfminer", "pdfplumber", "PIL", "fontTools"):
    logging.getLogger(_name).setLevel(logging.WARNING)
from .models import OCR_CONF, ROWID, Dataset, norm_name

TOTAL_RE = re.compile(r"^(grand\s*)?(sub\s*-?\s*)?totals?\b|^(opening|closing)\s+balance|balance\s+(b/?f|c/?f|brought|carried)|^brought forward|^carried forward", re.I)
DATE_LIKE = re.compile(r"^\d{1,4}[/\-.]\d{1,2}[/\-.]\d{1,4}")
NUM_LIKE = re.compile(r"^[\s(+-]*[₦$€£]?\s*[\d,]+(\.\d+)?\)?\s*(cr|dr)?$", re.I)


def sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class UnreadableFile(ValueError):
    pass


def load(path: str | Path, name: str | None = None, sheet: str | None = None,
         pci_mode: str = "strict", mask_columns=(), keep_columns=()) -> Dataset:
    """Load one file into one dataset.

    Excel: sheet=None picks the visible sheet with most data; sheet="<name>" picks that sheet;
    sheet="*" stacks every visible sheet that shares the same layout (e.g. monthly tabs).
    Use load_each_sheet() to get one dataset per sheet."""
    p = Path(path)
    if not p.exists():
        raise UnreadableFile(f"file not found: {p}")
    ext = p.suffix.lower()
    notes: list[str] = []
    warnings: list[str] = []
    conf: dict[str, float] = {}
    try:
        if ext in (".csv", ".tsv", ".txt"):
            df = frame_from_raw(_read_delimited(p), notes)
            fmt = "csv"
        elif ext in (".xlsx", ".xlsm", ".xls"):
            if ext != ".xls" and p.read_bytes()[:4] == b"\xd0\xcf\x11\xe0":
                raise UnreadableFile(f"{p.name}: the file is password-protected or encrypted. Open it, save an unprotected copy, and load that.")
            df = _excel_frame(p, sheet, notes)
            fmt = "excel"
        elif ext == ".json":
            df = _read_json(p)
            fmt = "json"
        elif ext == ".pdf":
            raw, conf = _read_pdf(p, notes)
            df = frame_from_raw(raw, notes, merge_continuations=True, warnings=warnings)
            fmt = "pdf+ocr" if conf else "pdf"
        elif ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"):
            from PIL import Image
            rows, conf = _ocr_image(Image.open(p), "IMG")
            df = frame_from_raw(_rows_to_raw(rows), notes, merge_continuations=True, warnings=warnings)
            fmt = "image+ocr"
        else:
            raise UnreadableFile(f"Unsupported file type: {ext}")
    except UnreadableFile:
        raise
    except Exception as e:  # turn library errors into something a user can act on
        msg = f"{type(e).__name__}: {e}".lower()
        if any(w in msg for w in ("password", "encrypt", "badzipfile", "not a zip file", "pdfpassword")):
            raise UnreadableFile(f"{p.name}: the file is password-protected or encrypted. Open it, save an unprotected copy, and load that.") from e
        raise UnreadableFile(f"{p.name}: could not be read ({type(e).__name__}: {e}). If it opens normally on your computer, re-export it as CSV or XLSX.") from e
    if df.empty:
        import sys
        hint = ("Scanned documents need the Desktop or Server edition." if sys.platform == "emscripten"
                else "If this is a scanned document, install Tesseract (see editions/desktop/README.md).")
        raise UnreadableFile(f"{p.name}: no table found. {hint}")

    df = df.copy()
    df.insert(0, ROWID, [str(i) for i in df.index])
    if conf:
        df[OCR_CONF] = [conf.get(str(i)) for i in df.index]
        low = int((df[OCR_CONF].fillna(0) < 80).sum())
        notes.append(f"OCR used: {len(df)} rows read from images; {low} rows below 80% confidence. "
                     "OCR rows are never auto-confirmed; see exceptions.")
    df = df.reset_index(drop=True)
    sanity_fix(df, notes, warnings)
    _derive_debit_credit(df, notes)

    ds = Dataset(name=name or p.stem, df=df, source=str(p), fmt=fmt, notes=notes, warnings=warnings, file_sha256=sha256(p))
    pci.guard(ds, pci_mode, mask_columns, keep_columns)
    return ds


def list_sheets(path: str | Path) -> list[dict]:
    """[{name, rows, hidden}] for an Excel workbook."""
    book, hidden = _read_excel_book(Path(path))
    return [dict(name=k, rows=int(v.dropna(how="all").shape[0]), hidden=k in hidden) for k, v in book.items()]


def load_each_sheet(path: str | Path, name: str | None = None, **kw) -> list[Dataset]:
    """One dataset per visible, non-empty sheet, named '<name>:<sheet>'."""
    base = name or Path(path).stem
    out = []
    for sh in list_sheets(path):
        if sh["hidden"] or sh["rows"] < 2:
            continue
        out.append(load(path, name=f"{base}:{sh['name']}", sheet=sh["name"], **kw))
    return out


# ---------------------------------------------------------------- readers

def _read_delimited(p: Path) -> pd.DataFrame:
    raw_bytes = p.read_bytes()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    lines = text.splitlines()
    sample = [l for l in lines[:60] if l.strip()]
    best, best_score = ",", -1.0
    for d in [",", ";", "\t", "|"]:
        counts = sorted(l.count(d) for l in sample)
        if not counts:
            continue
        median = counts[len(counts) // 2]
        consistency = sum(1 for c in counts if c == median) / len(counts)
        score = median * consistency
        if score > best_score:
            best, best_score = d, score
    rows = list(csv.reader(io.StringIO(text), delimiter=best))
    return _rows_to_raw([(f"L{i + 1}", r) for i, r in enumerate(rows)])


def _read_excel_book(p: Path) -> tuple[dict[str, pd.DataFrame], set[str]]:
    book = pd.read_excel(p, sheet_name=None, header=None, dtype=str)
    hidden: set[str] = set()
    if p.suffix.lower() in (".xlsx", ".xlsm"):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(p, read_only=False)
            hidden = {ws.title for ws in wb.worksheets if ws.sheet_state != "visible"}
            wb.close()
        except Exception:
            pass
    out = {}
    for name, df in book.items():
        df = df.copy()
        df.index = [f"{name}!R{i + 1}" for i in range(len(df))]
        out[name] = df.map(lambda v: None if pd.isna(v) else str(v))
    return out, hidden


def _excel_frame(p: Path, sheet: str | None, notes: list[str]) -> pd.DataFrame:
    book, hidden = _read_excel_book(p)
    visible = {k: v for k, v in book.items() if k not in hidden and v.notna().sum().sum() > 0}
    if hidden:
        notes.append(f"Ignored hidden sheet(s): {', '.join(sorted(hidden))}.")
    if sheet and sheet != "*":
        if sheet not in book:
            raise UnreadableFile(f"{p.name}: no sheet named '{sheet}'. Sheets: {', '.join(book)}")
        return frame_from_raw(book[sheet], notes)
    if not visible:
        return pd.DataFrame()
    if sheet == "*":
        frames, groups = {}, {}
        for k, raw in visible.items():
            f = frame_from_raw(raw, [])
            if f.empty:
                continue
            frames[k] = f
            groups.setdefault(tuple(norm_name(c) for c in f.columns), []).append(k)
        best = max(groups.values(), key=lambda ks: sum(len(frames[k]) for k in ks))
        stacked = pd.concat([frames[k].assign(Sheet=k) for k in best])
        skipped = [k for k in frames if k not in best]
        notes.append(f"Stacked {len(best)} sheet(s) with the same layout: {', '.join(best)}."
                     + (f" Skipped (different layout): {', '.join(skipped)}." if skipped else ""))
        return stacked
    name = max(visible, key=lambda k: int(visible[k].notna().sum().sum()))
    if len(visible) > 1:
        notes.append(f"Workbook has {len(visible)} sheets with data; used '{name}' (most data). "
                     "Choose a sheet, stack same-layout sheets, or load each sheet separately.")
    return frame_from_raw(visible[name], notes)


def _read_json(p: Path) -> pd.DataFrame:
    data = json.loads(p.read_text(encoding="utf-8-sig"))
    if isinstance(data, dict):
        lists = [v for v in data.values() if isinstance(v, list) and v and isinstance(v[0], dict)]
        if not lists:
            raise ValueError("JSON has no list of records")
        data = max(lists, key=len)
    df = pd.json_normalize(data)
    df.index = [f"J{i + 1}" for i in range(len(df))]
    return df.map(lambda v: None if v is None or (isinstance(v, float) and pd.isna(v)) else str(v))


def _read_pdf(p: Path, notes: list[str]) -> tuple[pd.DataFrame, dict[str, float]]:
    import pdfplumber
    rows: list[tuple[str, list]] = []
    conf: dict[str, float] = {}
    with pdfplumber.open(p) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if len(text.strip()) < 20:
                img = page.to_image(resolution=300).original
                orows, oconf = _ocr_image(img, f"P{pno}")
                rows.extend(orows)
                conf.update(oconf)
                continue
            tables = page.extract_tables()
            if not tables or max(len(t) for t in tables) < 2:
                tables = page.extract_tables({"vertical_strategy": "text", "horizontal_strategy": "text"})
            r = 0
            for t in tables:
                for row in t:
                    r += 1
                    rows.append((f"P{pno}:R{r}", [None if c is None else str(c).replace("\n", " ") for c in row]))
    if conf:
        notes.append("Some PDF pages had no text layer and were OCR'd.")
    return _rows_to_raw(rows), conf


def _ocr_image(img, prefix: str) -> tuple[list[tuple[str, list]], dict[str, float]]:
    """OCR an image into rows. Columns are anchored to the detected header line."""
    import os
    import shutil
    import sys
    if sys.platform == "emscripten":
        raise UnreadableFile("This is a scanned document. Scans need the Desktop or Server edition; "
                             "or use a digital export of the file.")
    try:
        import pytesseract
    except ImportError as e:
        raise UnreadableFile("This looks like a scanned document. Install OCR support: pip install pytesseract, plus Tesseract (editions/desktop/README.md).") from e
    if not shutil.which("tesseract"):
        win = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(win):
            pytesseract.pytesseract.tesseract_cmd = win
        else:
            raise UnreadableFile("This looks like a scanned document, and Tesseract (the OCR program) is not installed. See editions/desktop/README.md, step 5.")
    d = pytesseract.image_to_data(img.convert("L"), config="--psm 6", output_type=pytesseract.Output.DICT)
    words = [dict(text=d["text"][i].strip(), left=d["left"][i], width=d["width"][i], top=d["top"][i],
                  height=d["height"][i], conf=float(d["conf"][i]), line=(d["block_num"][i], d["par_num"][i], d["line_num"][i]))
             for i in range(len(d["text"])) if d["text"][i].strip() and float(d["conf"][i]) >= 0]
    lines: dict[tuple, list[dict]] = {}
    for w in words:
        lines.setdefault(w["line"], []).append(w)
    ordered = sorted(lines.values(), key=lambda ws: min(w["top"] for w in ws))
    if not ordered:
        return [], {}
    heights = sorted(w["height"] for w in words)
    gap = max(heights[len(heights) // 2] * 1.2, 12)

    def cells(ws):
        ws = sorted(ws, key=lambda w: w["left"])
        out = [[ws[0]]]
        for w in ws[1:]:
            prev = out[-1][-1]
            if w["left"] - (prev["left"] + prev["width"]) > gap:
                out.append([w])
            else:
                out[-1].append(w)
        return [dict(text=" ".join(x["text"] for x in c), x0=c[0]["left"], x1=c[-1]["left"] + c[-1]["width"],
                     conf=min(x["conf"] for x in c)) for c in out]

    header_idx, header = None, None
    for i, ws in enumerate(ordered):
        cs = cells(ws)
        alpha = sum(1 for c in cs if re.search(r"[A-Za-z]", c["text"]) and not NUM_LIKE.match(c["text"]))
        if len(cs) >= 3 and alpha >= len(cs) - 1:
            header_idx, header = i, cs
            break
    rows, conf = [], {}
    for i, ws in enumerate(ordered):
        cs = cells(ws)
        key = f"{prefix}:O{i + 1}"
        if header is None or i <= header_idx:
            rows.append((key, [c["text"] for c in cs]))
            continue
        out = [None] * len(header)
        for c in cs:
            def overlap(h):
                return min(c["x1"], h["x1"] + gap) - max(c["x0"], h["x0"] - gap)
            j = max(range(len(header)), key=lambda k: (overlap(header[k]), -abs((c["x0"] + c["x1"]) / 2 - (header[k]["x0"] + header[k]["x1"]) / 2)))
            out[j] = c["text"] if out[j] is None else out[j] + " " + c["text"]
        rows.append((key, out))
        conf[key] = round(min(c["conf"] for c in cs), 1)
    return rows, conf


def _rows_to_raw(rows: list[tuple[str, list]]) -> pd.DataFrame:
    width = max((len(r) for _, r in rows), default=0)
    data = [list(r) + [None] * (width - len(r)) for _, r in rows]
    return pd.DataFrame(data, index=[k for k, _ in rows], dtype=object)


# ---------------------------------------------------------------- header detection & cleanup

def _is_labelish(v: str) -> bool:
    return bool(re.search(r"[A-Za-z]", v)) and len(v) <= 40 and not DATE_LIKE.match(v) and not NUM_LIKE.match(v)


def frame_from_raw(raw: pd.DataFrame, notes: list[str], merge_continuations: bool = False,
                   warnings: list[str] | None = None) -> pd.DataFrame:
    raw = raw.map(lambda v: None if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == "" else str(v).strip())
    raw = raw.dropna(how="all").dropna(axis=1, how="all")
    if raw.empty:
        return pd.DataFrame()
    width = raw.shape[1]
    best_i, best_score = 0, -1.0
    limit = min(30, len(raw))
    for i in range(limit):
        vals = [v for v in raw.iloc[i].tolist() if isinstance(v, str)]
        if len(vals) < 2:
            continue
        fill = len(vals) / width
        alpha = sum(_is_labelish(v) for v in vals) / len(vals)
        uniq = len(set(vals)) / len(vals)
        below = raw.iloc[i + 1:i + 6]
        below_fill = below.notna().sum(axis=1).mean() / width if len(below) else 0
        score = fill * alpha * uniq * (0.5 + 0.5 * min(1.0, below_fill / fill if fill else 0))
        if score > best_score + 1e-9:
            best_i, best_score = i, score
    if best_i:
        notes.append(f"Skipped {best_i} preamble row(s) above the header.")
    header_vals = [v if isinstance(v, str) else None for v in raw.iloc[best_i].tolist()]
    names, seen = [], {}
    for j, v in enumerate(header_vals):
        n = (v or f"col_{j + 1}").strip()
        if n in seen:
            seen[n] += 1
            n = f"{n}_{seen[n]}"
        else:
            seen[n] = 1
        names.append(n)
    body = raw.iloc[best_i + 1:].copy()
    body.columns = names
    # repeated headers (multi-page PDFs)
    rep = body.apply(lambda r: sum(1 for a, b in zip(r.tolist(), header_vals) if isinstance(a, str) and a == b) >= max(2, len([h for h in header_vals if h]) // 2), axis=1)
    if rep.any():
        notes.append(f"Removed {int(rep.sum())} repeated header row(s).")
        body = body[~rep]
    tot = body.apply(lambda r: any(isinstance(v, str) and TOTAL_RE.search(v) for v in r.tolist()), axis=1)
    if tot.any():
        notes.append(f"Removed {int(tot.sum())} total / balance row(s).")
        body = body[~tot]
    body = body.dropna(how="all").dropna(axis=1, how="all")
    if merge_continuations and len(body) > 1:
        body = _merge_continuations(body, notes)
    if warnings is not None and len(body) >= 10:
        filled = body.notna().sum(axis=1)
        odd = int((filled < max(2, 0.4 * filled.median())).sum())
        if odd:
            warnings.append(f"{odd} row(s) have far fewer filled cells than the rest; they may belong to a different "
                            "table on the same page (e.g. a summary box). Check them in the unmatched lists.")
    return body


def _merge_continuations(body: pd.DataFrame, notes: list[str]) -> pd.DataFrame:
    """PDF statements wrap long narrations onto a second line that arrives as its own row with only
    the narration cell filled. Glue it back onto the row above."""
    rows = body.to_dict("index")
    keys = list(rows)
    keep, merged = [], 0
    for k in keys:
        r = rows[k]
        filled = [c for c, v in r.items() if isinstance(v, str)]
        if keep and len(filled) == 1 and re.search(r"[A-Za-z]", r[filled[0]]) and not NUM_LIKE.match(r[filled[0]]):
            prev = rows[keep[-1]]
            c = filled[0]
            if isinstance(prev.get(c), str):
                prev[c] = f"{prev[c]} {r[c]}"
                merged += 1
                continue
        keep.append(k)
    if merged:
        notes.append(f"Joined {merged} wrapped line(s) back onto the row above (multi-line narrations).")
    return pd.DataFrame.from_dict({k: rows[k] for k in keep}, orient="index")[list(body.columns)]


SCI_RE = re.compile(r"^-?\d+(\.\d+)?[eE][+-]?\d+$")
CURRENCY_RE = re.compile(r"(\b(?:NGN|USD|EUR|GBP|KES|GHS|ZAR|XOF|CAD)\b|[₦$€£])")


def sanity_fix(df: pd.DataFrame, notes: list[str], warnings: list[str]) -> None:
    """Catch the parsing problems that silently corrupt a reconciliation."""
    from .profile import semantic_label
    for col in [c for c in df.columns if not c.startswith("__")]:
        s = df[col]
        nn = s.dropna().astype(str).str.strip()
        nn = nn[nn != ""]
        if nn.empty:
            continue
        # 1. Long IDs shown in scientific notation have lost digits for good (Excel keeps 15 significant digits).
        sci = nn.str.fullmatch(SCI_RE)
        if sci.any() and semantic_label(col) not in ("amount", "fee", "balance"):
            warnings.append(f"'{col}': {int(sci.sum())} value(s) are in scientific notation (e.g. {nn[sci].iloc[0]}). "
                            "Digits beyond the 15th are lost and cannot be recovered; long references such as NIP "
                            "session IDs will not match. Re-export the source as CSV/text without opening it in Excel.")
        # 2. Whole numbers stored as floats: 42833770659.0 -> 42833770659
        dot0 = nn.str.fullmatch(r"-?\d+\.0+")
        if dot0.mean() >= 0.9:
            df[col] = s.map(lambda v: re.sub(r"\.0+$", "", v) if isinstance(v, str) and re.fullmatch(r"-?\d+\.0+", v) else v)
            notes.append(f"'{col}': removed trailing '.0' from {int(dot0.sum())} whole numbers stored as decimals.")
            nn = df[col].dropna().astype(str)
        # 3. Excel serial dates (45931 = 2025-10-01)
        if semantic_label(col) == "date":
            num = pd.to_numeric(nn, errors="coerce")
            if num.notna().mean() >= 0.9 and num.between(20000, 80000).mean() >= 0.9:
                conv = pd.to_datetime(pd.to_numeric(df[col], errors="coerce"), unit="D", origin="1899-12-30")
                df[col] = conv.dt.strftime("%Y-%m-%d").where(conv.notna(), df[col])
                notes.append(f"'{col}': converted Excel serial numbers to dates.")
        # 4. Mixed currencies in one amount column
        cur = nn.str.extract(CURRENCY_RE.pattern, expand=False).dropna().replace({"₦": "NGN", "$": "USD", "€": "EUR", "£": "GBP"})
        if cur.nunique() > 1 and nn.str.contains(r"\d").mean() > 0.9:
            warnings.append(f"'{col}': mixes currencies ({', '.join(sorted(cur.unique()))}). Amounts are compared as numbers; "
                            "FX is not handled yet. Split the file by currency first.")


def _derive_debit_credit(df: pd.DataFrame, notes: list[str]) -> None:
    """Bank statements often split amounts into Debit/Credit columns; add a combined column."""
    from .profile import parse_amount
    lower = {c: c.lower() for c in df.columns if not c.startswith("__")}
    deb = [c for c, l in lower.items() if re.search(r"\bdebit|withdrawal|\bdr\b|money out|paid out", l)]
    cre = [c for c, l in lower.items() if re.search(r"\bcredit|deposit|lodgement|\bcr\b|money in|paid in", l)]
    if len(deb) == 1 and len(cre) == 1 and deb[0] != cre[0]:
        d, c = parse_amount(df[deb[0]]), parse_amount(df[cre[0]])
        if d.notna().any() and c.notna().any():
            amt = c.where(c.notna() & (c != 0), d)
            df["Amount (Dr/Cr)"] = amt.map(lambda v: None if pd.isna(v) else f"{abs(v):.2f}")
            df["Direction"] = [("CR" if pd.notna(ci) and ci != 0 else ("DR" if pd.notna(di) else None)) for ci, di in zip(c, d)]
            notes.append(f"Combined '{deb[0]}' and '{cre[0]}' into 'Amount (Dr/Cr)' + 'Direction'.")
