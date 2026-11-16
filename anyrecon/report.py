"""Excel report + JSON audit trail."""
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


def _write(xw, df: pd.DataFrame, sheet: str, used: set[str], startrow: int = 0) -> None:
    """One sheet with a bold, frozen header and sensible column widths. Tables longer than Excel's row
    limit continue on '<sheet> (2)', '(3)'..."""
    parts = max(1, -(-len(df) // EXCEL_MAX_ROWS))
    for part in range(parts):
        chunk = df.iloc[part * EXCEL_MAX_ROWS:(part + 1) * EXCEL_MAX_ROWS]
        name = sheet if part == 0 else _sheet(f"{sheet[:25]} ({part + 1})", used)
        chunk.to_excel(xw, sheet_name=name, index=False, startrow=startrow)
        ws = xw.sheets[name]
        if startrow == 0:
            ws.freeze_panes(1, 0)
        if startrow == 0:   # pandas already writes a bold header row
            for j, col in enumerate(chunk.columns):
                sample = [len(str(v)) for v in chunk[col].head(200).tolist() if v is not None and not (isinstance(v, float) and pd.isna(v))]
                ws.set_column(j, j, min(max(10, max([len(str(col))] + sample) + 2), 60))


def write_excel(path: str, datasets: dict[str, Dataset], results: dict[str, PairResult], chain: pd.DataFrame | None = None) -> str:
    used: set[str] = set()
    # xlsxwriter, streaming each row to disk (constant_memory): faster than openpyxl and flat on memory.
    with pd.ExcelWriter(path, engine="xlsxwriter", engine_kwargs={"options": {"constant_memory": True}}) as xw:
        summ = pd.DataFrame([{k: v for k, v in r.summary.items() if not isinstance(v, dict)} for r in results.values()])
        summary_sheet = _sheet("Summary", used)
        _write(xw, summ, summary_sheet, used)
        ins = [(k, i) for k, r in results.items() for i in r.insights]
        if ins:
            _write(xw, pd.DataFrame(ins, columns=["pair", "insight"]), summary_sheet, used, startrow=len(summ) + 3)
        if chain is not None:
            _write(xw, chain, _sheet("Chains", used), used)
        for key, r in results.items():
            tag = f"{r.config.left[:6]}-{r.config.right[:6]}"
            _write(xw, r.matches, _sheet(f"{tag} matches", used), used)
            _write(xw, r.exceptions, _sheet(f"{tag} exceptions", used), used)
            _write(xw, r.left_unmatched, _sheet(f"{tag} L-only", used), used)
            _write(xw, r.right_unmatched, _sheet(f"{tag} R-only", used), used)
        pci = [dict(dataset=d.name, column=f.column, kind=f.kind, action=f.action, count=f.count, detail=f.detail)
               for d in datasets.values() for f in d.findings]
        _write(xw, pd.DataFrame(pci or [dict(dataset="-", column="-", kind="none", action="-", count=0, detail="No card data found")]),
               _sheet("PCI log", used), used)
        audit = [dict(item="engine", value=f"anyrecon {__version__}"),
                 dict(item="run_at_utc", value=datetime.now(timezone.utc).isoformat(timespec="seconds"))]
        for d in datasets.values():
            audit.append(dict(item=f"input:{d.name}", value=f"{d.source} sha256={d.file_sha256} rows={len(d)} fmt={d.fmt}"))
            for n in d.notes:
                audit.append(dict(item=f"note:{d.name}", value=n))
        for r in results.values():
            audit.append(dict(item=f"config:{r.config.left}⟷{r.config.right}", value=json.dumps(r.config.to_dict(), default=str)))
        _write(xw, pd.DataFrame(audit), _sheet("Audit", used), used)
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
