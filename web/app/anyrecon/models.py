"""Core data structures shared across the engine."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

import pandas as pd

ROWID = "__row"          # provenance of each row in its source file (line / page:row / sheet!row)
OCR_CONF = "__ocr_conf"  # min OCR word confidence for the row (only present for OCR-derived data)


@dataclass
class Finding:
    """Something the PCI guard or loader did / noticed. Never contains raw sensitive values."""
    column: str
    kind: str        # PAN | PAN_IN_TEXT | SAD_CVV | SAD_TRACK | SAD_PIN | PAN_EXEMPT | MASKED_PAN | OCR
    action: str      # masked | tokenised | dropped | exempted | flagged | blocked
    count: int
    detail: str = ""
    review: str = ""  # "" = final | "can_keep" (suspected SAD dropped; user may restore) | "can_mask" (exempted; user may mask)


@dataclass
class Dataset:
    name: str
    df: pd.DataFrame
    source: str
    fmt: str
    notes: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)   # data-quality problems the user must see
    file_sha256: str = ""

    @property
    def columns(self) -> list[str]:
        """User-visible columns (internal columns start with '__' except PAN tokens)."""
        return [c for c in self.df.columns if not c.startswith("__") or c.startswith("__tok_")]

    @property
    def is_ocr(self) -> bool:
        return OCR_CONF in self.df.columns

    def fingerprint(self) -> str:
        cols = sorted(norm_name(c) for c in self.columns)
        return hashlib.sha1("|".join(cols).encode()).hexdigest()[:12]

    def __len__(self) -> int:
        return len(self.df)


def norm_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(name).lower()).strip()
