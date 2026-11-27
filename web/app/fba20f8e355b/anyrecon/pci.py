"""PCI DSS guard.

Runs on every dataset immediately after parsing and BEFORE profiling, matching,
reporting, template saving or any LLM call. Nothing downstream ever sees a full PAN
or sensitive authentication data (SAD).

Modes
-----
strict   (default) Drop SAD columns. Mask PANs (first 6 + last 4) in every column,
         including free text. Pure-PAN columns also get a keyed-hash token column
         (``__tok_<col>``) so card numbers can still be used as a join key.
         Fixed-length digit columns whose Luhn pass rate is low are treated as
         references, not card numbers, and exempted (logged).
paranoid Same as strict but no reference exemption: every Luhn-valid PAN-shaped
         number is masked, even if that breaks some matches.
block    Refuse to load a file that contains any full PAN or SAD.

Relevant PCI DSS v4.0.1 requirements: 3.3.1 (SAD not stored after authorisation,
even if encrypted), 3.4.1 (PAN masked when displayed, max BIN + last 4),
3.5.1 (PAN unreadable wherever stored), 3.5.1.1 (hashes must be keyed).
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets

import pandas as pd

from .models import Dataset, Finding, norm_name

PAN_RE = re.compile(r"(?<![0-9])(?:[0-9][ -]?){12,18}[0-9](?![0-9])")
TRACK_RE = re.compile(r"%B\d{13,19}\^|;\d{13,19}=\d{4}")
MASKED_RE = re.compile(r"^\d{4,8}[ -]?[*Xx#•]{2,9}[ -]?[*Xx#•]*[ -]?\d{4}$")

SAD_CVV_TOKENS = {"cvv", "cvc", "cvv2", "cvc2", "cav2", "cid", "csc"}
SAD_NAME_PHRASES = ("security code", "card verification", "verification value")
SAD_PIN_TOKENS = {"pin", "pinblock", "pin block"}
SAD_TRACK_PHRASES = ("track1", "track2", "track 1", "track 2", "track data", "magstripe", "mag stripe")

_EPHEMERAL_KEY = secrets.token_bytes(32)


class PCIBlocked(Exception):
    pass


def luhn(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = ord(ch) - 48
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


def is_pan(digits: str) -> bool:
    return 13 <= len(digits) <= 19 and digits[0] in "23456" and luhn(digits)


def mask_pan(digits: str) -> str:
    return digits[:6] + "*" * (len(digits) - 10) + digits[-4:]


def pan_key() -> tuple[bytes, bool]:
    """Key for PAN tokens. Set ANYRECON_PAN_KEY to make tokens stable across runs."""
    env = os.environ.get("ANYRECON_PAN_KEY")
    if env:
        return env.encode(), True
    return _EPHEMERAL_KEY, False


def tokenise(digits: str, key: bytes) -> str:
    return "TOK" + hmac.new(key, digits.encode(), hashlib.sha256).hexdigest()[:20].upper()


def _mask_text(val: str) -> tuple[str, int]:
    hits = 0

    def repl(m: re.Match) -> str:
        nonlocal hits
        digits = re.sub(r"\D", "", m.group(0))
        if is_pan(digits):
            hits += 1
            return mask_pan(digits)
        return m.group(0)

    return PAN_RE.sub(repl, val), hits


GENERIC_NAME = re.compile(r"^(col\s?\d+|unnamed.*|column\s*\d+|[a-z]|field\s*\d+|)$")   # names are normalised: col_5 -> "col 5"
CVV_HINT = re.compile(r"cv|sec|verif|check|cid")
HEX16 = re.compile(r"^[0-9A-Fa-f]{16}$")


def guard(ds: Dataset, mode: str = "strict", mask_columns=(), keep_columns=()) -> Dataset:
    """mask_columns: columns the user wants masked even though the guard exempted them.
    keep_columns: suspected-SAD columns the user has confirmed are NOT card security data.
    Named CVV/PIN/track columns and confirmed PANs can never be kept."""
    if mode not in ("strict", "paranoid", "block"):
        raise ValueError(f"unknown PCI mode {mode!r}")
    df = ds.df
    key, stable = pan_key()
    mask_columns, keep_columns = set(mask_columns), set(keep_columns)
    pan_columns: list[str] = []

    for col in list(df.columns):
        if col.startswith("__"):
            continue
        s = df[col]
        nn = s.dropna().astype(str)
        if nn.empty:
            continue
        name = norm_name(col)
        tokens = set(name.split())

        # --- Sensitive authentication data: never kept, even encrypted (Req 3.3.1)
        kind = None
        if tokens & SAD_CVV_TOKENS or any(p in name for p in SAD_NAME_PHRASES):
            if nn.str.fullmatch(r"\d{3,4}").mean() >= 0.8:
                kind = "SAD_CVV"
        if tokens & SAD_PIN_TOKENS or "pin block" in name or "pinblock" in name:
            kind = "SAD_PIN"
        if any(p in name for p in SAD_TRACK_PHRASES) or nn.str.contains(TRACK_RE).any():
            kind = "SAD_TRACK"
        if kind:
            if mode == "block":
                raise PCIBlocked(f"{ds.name}: column '{col}' looks like {kind}; refusing to load (block mode)")
            df.drop(columns=[col], inplace=True)
            ds.findings.append(Finding(col, kind, "dropped", int(len(nn)),
                                       "Sensitive authentication data is never retained (PCI DSS 3.3.1)."))
            continue

        # --- PAN detection
        stripped = nn.str.replace(r"[ -]", "", regex=True)
        pure_digit = stripped.str.fullmatch(r"\d{13,19}").fillna(False).astype(bool)
        pure_pan = stripped[pure_digit].map(is_pan).astype(bool)
        n_pure_pan = int(pure_pan.sum())
        luhn_rate = float(pure_pan.mean()) if pure_digit.sum() else 0.0
        reference_like = pure_digit.mean() >= 0.8 and luhn_rate < 0.5

        if MASKED_RE.match(nn.iloc[0]) and nn.str.match(MASKED_RE).mean() > 0.8:
            ds.findings.append(Finding(col, "MASKED_PAN", "noted", int(len(nn)),
                                       "Already-masked card numbers; out of PCI storage scope if no more than BIN + last 4 are visible."))
            continue

        if reference_like and mode == "strict" and col not in mask_columns:
            if n_pure_pan:
                ds.findings.append(Finding(col, "PAN_EXEMPT", "left as-is", n_pure_pan,
                    f"{n_pure_pan} value(s) pass the card-number check, but only {luhn_rate:.0%} of this column does, "
                    "which indicates transaction references, not card numbers. Mask them if you disagree.",
                    review="can_mask"))
            continue

        masked_vals = {}
        total_hits = 0
        # Only cells with a 13-19 digit run can hold a card number: filter fast, then check those cells.
        nn = nn[nn.str.contains(PAN_RE, na=False)]
        for idx, val in nn.items():
            new, hits = _mask_text(val)
            if hits:
                masked_vals[idx] = new
                total_hits += hits
        if not total_hits:
            continue
        if mode == "block":
            raise PCIBlocked(f"{ds.name}: column '{col}' contains {total_hits} full card number(s); refusing to load (block mode)")

        is_pan_column = pure_digit.mean() >= 0.5 and luhn_rate >= 0.9
        if is_pan_column:
            pan_columns.append(col)
            digits = df[col].astype("string").str.replace(r"[ -]", "", regex=True)
            df["__tok_" + col] = digits.map(
                lambda d: tokenise(d, key) if isinstance(d, str) and is_pan(d) else None)
            ds.findings.append(Finding(col, "PAN", "masked + tokenised", total_hits,
                "Full card numbers masked to first 6 / last 4 (Req 3.4.1). Keyed HMAC-SHA256 token column "
                f"'__tok_{col}' added so the card number can still be a matching key (Req 3.5.1.1). "
                + ("Tokens stable across runs (ANYRECON_PAN_KEY set)." if stable
                   else "Tokens valid for this run only; set ANYRECON_PAN_KEY for stable tokens.")))
        else:
            ds.findings.append(Finding(col, "PAN_IN_TEXT", "masked", total_hits,
                                       "Card numbers found inside text and masked to first 6 / last 4."
                                       + (" (masked at your request)" if col in mask_columns else "")))
        for idx, new in masked_vals.items():
            df.at[idx, col] = new

    # --- Suspected SAD: unlabelled columns next to card numbers that look like CVV or PIN blocks.
    if pan_columns:
        for col in list(df.columns):
            if col.startswith("__") or col in pan_columns:
                continue
            nn = df[col].dropna().astype(str).str.strip()
            if len(nn) < 3:
                continue
            name = norm_name(col)
            kind = None
            if nn.str.fullmatch(r"\d{3,4}").mean() >= 0.95 and (GENERIC_NAME.match(name) or CVV_HINT.search(name)):
                kind = "SAD_SUSPECTED_CVV"
            elif nn.str.fullmatch(HEX16).mean() >= 0.95 and nn.str.contains(r"[A-Fa-f]").mean() >= 0.3:
                kind = "SAD_SUSPECTED_PINBLOCK"
            if not kind:
                continue
            if mode == "block":
                raise PCIBlocked(f"{ds.name}: column '{col}' looks like {kind}; refusing to load (block mode)")
            if col in keep_columns:
                ds.findings.append(Finding(col, kind, "kept (user confirmed not card security data)", int(len(nn)),
                                           "Restored at the user's instruction; recorded for audit."))
                continue
            df.drop(columns=[col], inplace=True)
            ds.findings.append(Finding(col, kind, "dropped", int(len(nn)),
                "Unlabelled column sitting next to card numbers with "
                + ("3–4 digit values (CVV pattern)." if kind.endswith("CVV") else "16-character hex values (PIN-block pattern).")
                + " Dropped to be safe. Restore it only if you are sure it is something else.", review="can_keep"))
    return ds


def scan_file_for_pans(path: str) -> int:
    """Used by the pre-commit hook: count Luhn-valid PANs in a text file."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
    except OSError:
        return 0
    return sum(1 for m in PAN_RE.finditer(text) if is_pan(re.sub(r"\D", "", m.group(0))))
