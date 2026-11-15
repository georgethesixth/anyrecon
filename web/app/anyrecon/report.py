"""Excel report + JSON audit trail."""
from __future__ import annotations

import json
import platform
from datetime import datetime, timezone

import pandas as pd
from openpyxl.styles import Font

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


def write_excel(path: str, datasets: dict[str, Dataset], results: dict[str, PairResult], chain: pd.DataFrame | None = None) -> str:
    used: set[str] = set()
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        summ = pd.DataFrame([{k: v for k, v in r.summary.items() if not isinstance(v, dict)} for r in results.values()])
        summ.to_excel(xw, sheet_name=_sheet("Summary", used), index=False)
        start = len(summ) + 3
        ins = [(k, i) for k, r in results.items() for i in r.insights]
        if ins:
            pd.DataFrame(ins, columns=["pair", "insight"]).to_excel(xw, sheet_name="Summary", startrow=start, index=False)
        if chain is not None:
            chain.to_excel(xw, sheet_name=_sheet("Chains", used), index=False)
        for key, r in results.items():
            tag = f"{r.config.left[:6]}-{r.config.right[:6]}"
            r.matches.to_excel(xw, sheet_name=_sheet(f"{tag} matches", used), index=False)
            r.exceptions.to_excel(xw, sheet_name=_sheet(f"{tag} exceptions", used), index=False)
            r.left_unmatched.to_excel(xw, sheet_name=_sheet(f"{tag} L-only", used), index=False)
            r.right_unmatched.to_excel(xw, sheet_name=_sheet(f"{tag} R-only", used), index=False)
        pci = [dict(dataset=d.name, column=f.column, kind=f.kind, action=f.action, count=f.count, detail=f.detail)
               for d in datasets.values() for f in d.findings]
        pd.DataFrame(pci or [dict(dataset="-", column="-", kind="none", action="-", count=0, detail="No card data found")]
                     ).to_excel(xw, sheet_name=_sheet("PCI log", used), index=False)
        audit = [dict(item="engine", value=f"anyrecon {__version__}"),
                 dict(item="run_at_utc", value=datetime.now(timezone.utc).isoformat(timespec="seconds"))]
        for d in datasets.values():
            audit.append(dict(item=f"input:{d.name}", value=f"{d.source} sha256={d.file_sha256} rows={len(d)} fmt={d.fmt}"))
            for n in d.notes:
                audit.append(dict(item=f"note:{d.name}", value=n))
        for r in results.values():
            audit.append(dict(item=f"config:{r.config.left}⟷{r.config.right}", value=json.dumps(r.config.to_dict(), default=str)))
        pd.DataFrame(audit).to_excel(xw, sheet_name=_sheet("Audit", used), index=False)

        for ws in xw.book.worksheets:
            ws.freeze_panes = "A2"
            for col in ws.columns:
                width = max((len(str(c.value)) for c in list(col)[:200] if c.value is not None), default=8)
                ws.column_dimensions[col[0].column_letter].width = min(max(10, width + 2), 60)
            for c in ws[1]:
                c.font = Font(bold=True)
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
