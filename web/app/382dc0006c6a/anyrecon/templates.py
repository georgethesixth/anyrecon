"""Save / reuse a reconciliation setup. Templates store column names and rules only,
never data values, so they are safe to commit and share."""
from __future__ import annotations

import json
from pathlib import Path

from .match import PairConfig
from .models import Dataset


def save(path: str | Path, datasets: dict[str, Dataset], configs: list[PairConfig]) -> None:
    doc = dict(version=1,
               datasets={n: dict(fingerprint=d.fingerprint(), columns=d.columns, format=d.fmt) for n, d in datasets.items()},
               pairs=[c.to_dict() for c in configs])
    Path(path).write_text(json.dumps(doc, indent=2, default=str), encoding="utf-8")


def load(path: str | Path) -> tuple[list[PairConfig], dict]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    return [PairConfig.from_dict(p) for p in doc["pairs"]], doc.get("datasets", {})


def check(datasets: dict[str, Dataset], expected: dict) -> list[str]:
    """Warnings when the files given don't look like the ones the template was built on."""
    warns = []
    for name, meta in expected.items():
        if name not in datasets:
            warns.append(f"template expects a dataset named '{name}'")
            continue
        missing = [c for c in meta.get("columns", []) if c not in datasets[name].columns]
        if missing:
            warns.append(f"{name}: columns missing vs template: {', '.join(missing[:8])}")
        elif datasets[name].fingerprint() != meta.get("fingerprint"):
            warns.append(f"{name}: layout differs slightly from template (extra columns); rules still apply")
    return warns
