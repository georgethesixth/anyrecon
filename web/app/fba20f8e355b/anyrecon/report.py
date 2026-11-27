"""Excel report (sheets built in export.py) + JSON audit trail."""
from __future__ import annotations

import json
import platform
from datetime import datetime, timezone

import pandas as pd

from . import __version__
from .match import PairResult
from .models import Dataset


def _sheet(name: str, used: set[str]) -> str:
    base = "".join(ch for ch in name if ch not in "[]:*?/\\")[:31]
    n, out = 2, base
    while out in used:
        suffix = f"~{n}"
        out = base[:31 - len(suffix)] + suffix
        n += 1
    used.add(out)
    return out


EXCEL_MAX_ROWS = 1_048_575   # Excel's sheet limit, less the header row


def _cell(v):
    """A pandas/numpy value as something xlsxwriter writes natively; None for blanks."""
    if v is None:
        return None
    if isinstance(v, float) and v != v:
        return None
    if v is pd.NaT:
        return None
    if isinstance(v, pd.Timestamp):
        v = v.to_pydatetime()
    if isinstance(v, datetime) and v.tzinfo is not None:
        v = v.replace(tzinfo=None)
    if hasattr(v, "item") and not isinstance(v, (str, bytes)):   # numpy scalars
        try:
            v = v.item()
        except (ValueError, AttributeError):
            pass
    return v


def _write(xw, df: pd.DataFrame, sheet: str, used: set[str], startrow: int = 0) -> None:
    """One sheet with a bold, frozen header and sensible column widths. Tables longer than Excel's row
    limit continue on '<sheet> (2)', '(3)'...

    Cells are written row by row, in order. The workbook streams each row to disk (constant_memory), which
    only works if a row is finished before the next starts; pandas' to_excel writes column by column and
    so silently lost every column after the first (the 0.3.0 blank-report bug). Text is always written as
    text, never as a formula, so a cell starting with "=" from a file can't run as a formula in Excel."""
    book = xw.book
    bold = book.add_format({"bold": True})
    datefmt = book.add_format({"num_format": "yyyy-mm-dd hh:mm:ss"})
    parts = max(1, -(-len(df) // EXCEL_MAX_ROWS))
    for part in range(parts):
        chunk = df.iloc[part * EXCEL_MAX_ROWS:(part + 1) * EXCEL_MAX_ROWS]
        name = sheet if part == 0 else _sheet(f"{sheet[:25]} ({part + 1})", used)
        ws = book.get_worksheet_by_name(name) or book.add_worksheet(name)
        if startrow == 0:
            ws.freeze_panes(1, 0)
            for j, col in enumerate(chunk.columns):
                sample = [len(str(v)) for v in chunk[col].head(200).tolist() if _cell(v) is not None]
                ws.set_column(j, j, min(max(10, max([len(str(col))] + sample) + 2), 60))
        ws.write_row(startrow, 0, [str(c) for c in chunk.columns], bold)
        for i, row in enumerate(chunk.itertuples(index=False, name=None), start=startrow + 1):
            for j, v in enumerate(row):
                v = _cell(v)
                if v is None:
                    continue
                if isinstance(v, bool):
                    ws.write_boolean(i, j, v)
                elif isinstance(v, (int, float)):
                    if v != v or v in (float("inf"), float("-inf")):
                        continue
                    ws.write_number(i, j, v)
                elif isinstance(v, datetime):
                    ws.write_datetime(i, j, v, datefmt)
                else:
                    ws.write_string(i, j, str(v)[:32767])


def write_excel(path: str, datasets: dict[str, Dataset], results: dict[str, PairResult], chain: pd.DataFrame | None = None,
                include=None) -> str:
    """The report. `include` is the set of sheets the user ticked (see export.SHEETS); default Matched and
    Exceptions. Sheets that don't apply to this run (Groups with only one-to-one links, Across all files with
    two files) are skipped."""
    from .export import DEFAULT, SHEETS, available, tables
    want = [k for k in SHEETS if k in set(include or DEFAULT) and k in available(results, chain)]
    t = tables(datasets, results, chain)
    used: set[str] = set()
    # xlsxwriter, streaming each row to disk (constant_memory): faster than openpyxl and flat on memory.
    with pd.ExcelWriter(path, engine="xlsxwriter", engine_kwargs={"options": {"constant_memory": True}}) as xw:
        for k in want:
            if k == "only":
                for label, df in t["only"].items():
                    _write(xw, df, _sheet(label, used), used)
            else:
                _write(xw, t[k], _sheet(SHEETS[k], used), used)
    return path


def audit_json(datasets: dict[str, Dataset], results: dict[str, PairResult]) -> dict:
    return dict(
        engine=f"anyrecon {__version__}", python=platform.python_version(),
        run_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        inputs=[dict(name=d.name, source=d.source, sha256=d.file_sha256, rows=len(d), format=d.fmt,
                     fingerprint=d.fingerprint(), notes=d.notes,
                     pci=[f.__dict__ for f in d.findings]) for d in datasets.values()],
        pairs=[dict(config=r.config.to_dict(), summary=r.summary, insights=r.insights) for r in results.values()],
    )
