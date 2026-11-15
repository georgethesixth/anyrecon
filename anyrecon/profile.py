"""Column profiling: type inference, parsing of amounts/dates, semantic labels."""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict

import pandas as pd

from .models import Dataset, norm_name

DATE_FORMATS = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%Y/%m/%d", "%d-%b-%Y", "%d %b %Y",
                "%d-%b-%y", "%d/%m/%y", "%b %d, %Y", "%d %B %Y", "%m/%d/%Y", "%m-%d-%Y", "%Y%m%d"]

SEMANTIC = {
    "rrn": ["rrn", "retrieval reference", "retrieval ref"],
    "session_id": ["session id", "sessionid", "session", "nip session"],
    "stan": ["stan", "system trace"],
    "reference": ["reference", "ref", "txn ref", "transaction ref", "payment ref", "trans ref", "transaction id",
                  "txn id", "order id", "invoice", "receipt", "paymentreference", "tx ref"],
    "batch": ["batch", "settlement id", "payout id", "settlement ref"],
    "amount": ["amount", "amt", "value", "gross", "net", "credit", "debit", "settled", "principal"],
    "fee": ["fee", "charge", "commission", "mdr", "vat"],
    "balance": ["balance"],
    "date": ["date", "time", "posted", "created", "value date", "timestamp"],
    "narration": ["narration", "description", "details", "remark", "memo", "particulars", "narrative", "comment"],
    "merchant": ["merchant", "customer", "beneficiary", "payee", "account name"],
    "status": ["status", "response", "state"],
    "pan": ["pan", "card number", "card no", "masked pan", "card"],
}


def semantic_label(col: str) -> str | None:
    n = norm_name(col)
    if col.startswith("__tok_"):
        return "pan_token"
    best, best_len = None, 0
    for label, words in SEMANTIC.items():
        for w in words:
            if re.search(rf"(^|\s){re.escape(w)}(\s|$)", n) and len(w) > best_len:
                best, best_len = label, len(w)
    return best


def parse_amount(s: pd.Series) -> pd.Series:
    s = s.astype("string").str.strip()
    neg = s.str.match(r"^\(.*\)$", na=False) | s.str.startswith("-", na=False) | s.str.upper().str.endswith("DR", na=False)
    euro = s.str.fullmatch(r"[^\d]*\d{1,3}(\.\d{3})+,\d{1,2}[^\d]*", na=False)
    clean = s.str.replace(r"[^\d.,]", "", regex=True)
    clean = clean.where(~euro, clean.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
    clean = clean.where(euro, clean.str.replace(",", "", regex=False))
    out = pd.to_numeric(clean, errors="coerce")
    return out.where(~neg, -out.abs())


def parse_date(s: pd.Series, allow_compact: bool = False, allow_mixed: bool = True) -> tuple[pd.Series, str | None, float]:
    s = s.astype("string").str.strip()
    nn = s.dropna()
    if nn.empty:
        return pd.Series(pd.NaT, index=s.index), None, 0.0
    sample = nn.head(300)
    first_tok = sample.str.split(r"[ T]", n=1, regex=True).str[0]
    best_fmt, best_rate, best_on_tok = None, 0.0, False
    for fmt in DATE_FORMATS:
        if fmt == "%Y%m%d" and not allow_compact:
            continue
        for on_tok, src in ((False, sample), (True, first_tok)):
            if on_tok and " " in fmt:
                continue
            rate = pd.to_datetime(src, format=fmt, errors="coerce").notna().mean()
            if rate > best_rate + 1e-9:
                best_fmt, best_rate, best_on_tok = fmt, rate, on_tok
    if best_fmt is None or best_rate < 0.5:
        if not allow_mixed:
            return pd.Series(pd.NaT, index=s.index), None, 0.0
        try:
            parsed = pd.to_datetime(s, format="mixed", dayfirst=True, errors="coerce")
            return parsed, "mixed(dayfirst)", float(parsed[s.notna()].notna().mean())
        except (ValueError, TypeError):
            return pd.Series(pd.NaT, index=s.index), None, 0.0
    src = s.str.split(r"[ T]", n=1, regex=True).str[0] if best_on_tok else s
    parsed = pd.to_datetime(src, format=best_fmt, errors="coerce")
    return parsed, best_fmt, float(parsed[s.notna()].notna().mean())


def shape(v: str) -> str:
    return re.sub(r"[A-Za-z]", "A", re.sub(r"\d", "9", v))


@dataclass
class ColumnProfile:
    name: str
    kind: str              # id | amount | date | text | category | other
    semantic: str | None
    non_null: int
    distinct: int
    uniqueness: float
    avg_len: float
    top_shape: str
    shape_share: float
    amount_rate: float
    date_rate: float
    date_format: str | None
    note: str = ""

    def as_dict(self):
        return asdict(self)


def profile_column(name: str, s: pd.Series) -> ColumnProfile:
    nn = s.dropna().astype(str)
    nn = nn[nn.str.strip() != ""]
    n = len(nn)
    sem = semantic_label(name)
    if n == 0:
        return ColumnProfile(name, "other", sem, 0, 0, 0, 0, "", 0, 0, 0, None)
    distinct = nn.nunique()
    uniq = distinct / n
    avg_len = float(nn.str.len().mean())
    shapes = nn.head(500).map(shape).value_counts()
    amt = parse_amount(nn)
    amount_rate = float(amt.notna().mean())
    decimals = float(nn.str.contains(r"\.\d{1,2}\b|,\d{2}$", regex=True).mean())
    max_digits = int(nn.str.replace(r"\D", "", regex=True).str.len().max())
    all_digits = bool(nn.str.fullmatch(r"\d+").all())
    _, fmt, date_rate = parse_date(nn, allow_compact=sem == "date", allow_mixed=sem == "date")
    alpha_share = float(nn.str.contains(r"[A-Za-z]{3,}").mean())
    note = ""
    swapped = {"%d/%m/%Y": "%m/%d/%Y", "%d-%m-%Y": "%m-%d-%Y", "%m/%d/%Y": "%d/%m/%Y", "%m-%d-%Y": "%d-%m-%Y"}.get(fmt or "")
    if swapped and date_rate >= 0.8:
        tok = nn.head(300).str.split(r"[ T]", n=1, regex=True).str[0]
        if pd.to_datetime(tok, format=swapped, errors="coerce").notna().mean() >= date_rate - 1e-9:
            note = f"Ambiguous day/month order; assumed {fmt}."

    if name.startswith("__tok_"):
        kind = "id"
    elif sem == "narration" or (avg_len > 28 and alpha_share > 0.5):
        kind = "text"
    elif date_rate >= 0.8 and not (all_digits and sem != "date"):
        kind = "date"
    elif amount_rate >= 0.9 and max_digits <= 13 and (decimals >= 0.3 or sem in ("amount", "fee", "balance")) and sem not in ("rrn", "session_id", "stan", "reference"):
        kind = "amount"
    elif uniq >= 0.5 and avg_len >= 5:
        kind = "id"
    elif distinct <= max(20, 0.05 * n):
        kind = "category"
    else:
        kind = "other"
    return ColumnProfile(name, kind, sem, n, distinct, round(uniq, 3), round(avg_len, 1),
                         shapes.index[0] if len(shapes) else "", round(float(shapes.iloc[0] / shapes.sum()), 3) if len(shapes) else 0,
                         round(amount_rate, 3), round(date_rate, 3), fmt, note)


def profile(ds: Dataset) -> dict[str, ColumnProfile]:
    return {c: profile_column(c, ds.df[c]) for c in ds.columns}


AMOUNT_PREF = ("amount", "amt", "gross", "value", "settled", "net", "credit", "principal")
AMOUNT_AVOID = ("fee", "charge", "vat", "commission", "balance", "mdr", "tax")


def pick_amount(profiles: dict[str, ColumnProfile]) -> str | None:
    cands = [p for p in profiles.values() if p.kind == "amount"]
    if not cands:
        return None

    def score(p):
        n = norm_name(p.name)
        s = p.amount_rate
        if p.name == "Amount (Dr/Cr)":
            s += 3
        if any(w in n for w in AMOUNT_PREF):
            s += 1
        if any(w in n for w in AMOUNT_AVOID):
            s -= 2
        if "net" in n.split():
            s -= 0.3   # prefer gross when both exist; the user can switch
        return s
    return max(cands, key=score).name


def pick_date(profiles: dict[str, ColumnProfile]) -> str | None:
    cands = [p for p in profiles.values() if p.kind == "date"]
    if not cands:
        return None

    def score(p):
        n = norm_name(p.name)
        s = p.date_rate
        if any(w in n for w in ("transaction", "txn", "trans", "value", "posting", "posted")):
            s += 0.5
        if "settle" in n:
            s -= 0.2
        return s
    return max(cands, key=score).name
