"""Identifier discovery.

For a chosen pair of documents, find which column(s) link them, and how the values
must be transformed to agree. Every candidate is *measured* on the actual data
(value overlap, uniqueness) rather than guessed from column names.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict

import pandas as pd

from .models import Dataset
from .profile import ColumnProfile, parse_amount, parse_date, pick_amount, pick_date, profile

# name -> (function, simplicity weight). Simpler transforms win ties.
TRANSFORMS = {
    "exact": 1.000,
    "alnum": 0.999,       # upper-case, strip spaces/punctuation
    "nozeros": 0.998,     # alnum + strip leading zeros
    "noprefix": 0.995,    # alnum + strip leading letters + leading zeros (TXN-000123 -> 123)
    "digits": 0.994,      # digits only
    "last12": 0.98,
    "last10": 0.975,
    "last8": 0.97,
}
TOKEN_RE = re.compile(r"[A-Z0-9]{6,}")
DIGIT_RUN_RE = re.compile(r"\d{6,}")
MIN_KEY_LEN = 4


def apply_transform(s: pd.Series, tf: str, min_len: int = MIN_KEY_LEN) -> pd.Series:
    s = s.astype("string")
    if tf == "exact":
        out = s.str.strip()
    else:
        out = s.str.upper().str.replace(r"[^A-Z0-9]", "", regex=True)
        if tf == "nozeros":
            out = out.str.lstrip("0")
        elif tf == "noprefix":
            out = out.str.replace(r"^[A-Z]+", "", regex=True).str.lstrip("0")
        elif tf == "digits":
            out = s.str.replace(r"\D", "", regex=True).str.lstrip("0")
        elif tf.startswith("last"):
            out = out.str[-int(tf[4:]):]
    return out.where(out.str.len() >= max(1, min_len))


def text_tokens(v) -> list[str]:
    if not isinstance(v, str):
        return []
    u = v.upper()
    toks = TOKEN_RE.findall(re.sub(r"[^A-Z0-9]", " ", u)) + DIGIT_RUN_RE.findall(u)
    out, seen = [], set()
    for t in toks:
        for v in (t.lstrip("0"), re.sub(r"^[A-Z]+", "", t).lstrip("0")):
            if len(v) >= MIN_KEY_LEN and v not in seen:
                seen.add(v)
                out.append(v)
    return out


SUBSTRING_MIN = 8   # shorter keys are only matched as whole tokens: a 6-digit key inside a long number is too often chance


def find_in_text(v, keyset: set[str], lengths: list[int]) -> tuple[str | None, str]:
    """Find a known identifier inside free text that follows no fixed structure.

    1. token:     split on anything that isn't a letter/digit; strip leading zeros / alpha prefixes
                  ('POS SETTL/042833770659/X', 'Ref: NX-42833770659', 'TRF 42833770659 FROM ADA')
    2. substring: scan the text with letters/digits joined, then digits only, for any known key
                  ('0428 3377 0659', 'POS042833770659NGN', '0428-337-70659', 'REF#042833770659.')
    The engine never parses a pattern; it looks for identifiers it already knows from the other
    document, so position, separators and wording don't matter."""
    if not isinstance(v, str):
        return None, ""
    for t in text_tokens(v):
        if t in keyset:
            return t, "token"
    u = v.upper()
    for s in (re.sub(r"[^A-Z0-9]", "", u), re.sub(r"\D", "", u)):
        for L in lengths:
            for i in range(0, len(s) - L + 1):
                w = s[i:i + L]
                if w[0] != "0" and w in keyset:
                    return w, "substring"
    return None, ""


def prepare_text(text: pd.Series) -> list:
    """Tokenise each text cell once (tokens, letters+digits joined, digits only), so several key sets can
    be searched without re-reading the text."""
    out = []
    for v in text.tolist():
        if not isinstance(v, str):
            out.append(None)
            continue
        u = v.upper()
        out.append((text_tokens(v), re.sub(r"[^A-Z0-9]", "", u), re.sub(r"\D", "", u)))
    return out


def _find_prepared(p, keyset: set[str], lengths: list[int]) -> tuple[str | None, str]:
    """find_in_text() on a prepare_text() entry."""
    if p is None:
        return None, ""
    toks, alnum, digits = p
    for t in toks:
        if t in keyset:
            return t, "token"
    for s in (alnum, digits):
        for L in lengths:
            for i in range(0, len(s) - L + 1):
                w = s[i:i + L]
                if w[0] != "0" and w in keyset:
                    return w, "substring"
    return None, ""


def extract_against(text: pd.Series, keyset: set[str], with_how: bool = False, prepared: list | None = None):
    """For each text cell, the first known identifier it contains."""
    lengths = sorted({len(k) for k in keyset if len(k) >= SUBSTRING_MIN}, reverse=True)[:12]
    prep = prepared if prepared is not None else prepare_text(text)
    found = [_find_prepared(p, keyset, lengths) for p in prep]
    keys = pd.Series([f[0] for f in found], index=text.index, dtype=object)
    return (keys, pd.Series([f[1] for f in found], index=text.index, dtype=object)) if with_how else keys


def _isin(s: pd.Series, values) -> pd.Series:
    """Membership test that avoids pandas' slow path for Arrow-backed strings."""
    return s.astype(object).isin(values)


@dataclass
class KeyCandidate:
    left_col: str | None
    right_col: str | None
    left_tf: str
    right_tf: str
    mode: str                 # key | extract_left | extract_right | composite
    cov_left: float           # share of left rows whose key is found on the right
    cov_right: float
    uniq_left: float
    uniq_right: float
    score: float
    examples: list = field(default_factory=list)
    note: str = ""

    def describe(self) -> str:
        if self.mode == "composite":
            return f"amount + date window ({self.note})"
        if self.mode == "extract_right":
            return f"{self.left_col} [{self.left_tf}]  ⟷  found inside text of {self.right_col}"
        if self.mode == "extract_left":
            return f"found inside text of {self.left_col}  ⟷  {self.right_col} [{self.right_tf}]"
        tf = self.left_tf if self.left_tf == self.right_tf else f"{self.left_tf} / {self.right_tf}"
        return f"{self.left_col}  ⟷  {self.right_col}  [{tf}]"

    def as_dict(self):
        d = asdict(self)
        d["description"] = self.describe()
        return d


def _uniq(s: pd.Series) -> float:
    nn = s.dropna()
    return float(nn.nunique() / len(nn)) if len(nn) else 0.0


def _f1(a: float, b: float) -> float:
    return 2 * a * b / (a + b) if a + b else 0.0


def _cov_score(cl: float, cr: float, nl: int, nr: int) -> float:
    """Coverage of the smaller document matters most: a 14-row scan that fully matches a
    300-row export is a perfect identifier even though it covers 5% of the export."""
    small, large = (cl, cr) if nl <= nr else (cr, cl)
    return 0.8 * small + 0.2 * large


def _key_cols(profiles: dict[str, ColumnProfile]) -> list[str]:
    return [c for c, p in profiles.items() if p.non_null > 0 and p.avg_len >= MIN_KEY_LEN and
            (p.kind in ("id", "other", "category") or (p.kind == "text" and p.uniqueness >= 0.8))]


def _text_cols(profiles: dict[str, ColumnProfile]) -> list[str]:
    return [c for c, p in profiles.items() if p.kind in ("text", "other") and p.non_null > 0]


def discover(left: Dataset, right: Dataset, top: int = 8, sample: int = 20000,
             date_window_days: int = 3) -> list[KeyCandidate]:
    lp, rp = profile(left), profile(right)
    L = left.df if len(left.df) <= sample else left.df.sample(sample, random_state=0)
    R = right.df
    cands: list[KeyCandidate] = []

    # 1) column ⟷ column with the same transform on both sides
    for lc in _key_cols(lp):
        for rc in _key_cols(rp):
            best, best_raw = None, -1.0
            textual = lp[lc].kind == "text" or rp[rc].kind == "text"
            for tf, weight in TRANSFORMS.items():
                if textual and tf not in ("exact", "alnum"):
                    continue   # pulling an ID out of free text is the extract path's job
                if textual:
                    weight *= 0.97
                lk, rk = apply_transform(L[lc], tf), apply_transform(R[rc], tf)
                ln, rn = lk.dropna(), rk.dropna()
                if len(ln) == 0 or len(rn) == 0:
                    continue
                ul, ur = _uniq(ln), _uniq(rn)
                if max(ul, ur) < 0.3:
                    continue
                rset, lset = set(rn), set(ln)
                cl = float(_isin(lk, rset).sum() / max(1, L[lc].notna().sum()))
                cr = float(_isin(rk, lset).sum() / max(1, R[rc].notna().sum()))
                if cl == 0 and cr == 0:
                    continue
                sem_bonus = 1.03 if lp[lc].semantic and lp[lc].semantic == rp[rc].semantic else 1.0
                score = _cov_score(cl, cr, int(L[lc].notna().sum()), int(R[rc].notna().sum())) * (max(ul, ur) ** 0.5) * weight * sem_bonus
                if best is None or score > best_raw:
                    best_raw = score
                    hits = [v for v in ln.head(2000) if v in rset][:3]
                    ex = [(L.loc[lk == h, lc].iloc[0], R.loc[rk == h, rc].iloc[0]) for h in hits]
                    best = KeyCandidate(lc, rc, tf, tf, "key", round(cl, 4), round(cr, 4), round(ul, 3), round(ur, 3), round(min(score, 1.0), 4), ex)
            if best and best_raw > 0.02:
                best.score = round(min(best_raw, 1.0), 4)
                cands.append(best)

    # 2) identifier embedded in free text (bank narrations etc.)
    prepared: dict[tuple[int, str], list] = {}

    def extract(id_df, id_profiles, text_df, text_profiles, id_is_left):
        for ic in _key_cols(id_profiles):
            for tc in _text_cols(text_profiles):
                if tc == ic:
                    continue
                best = None
                for tf, weight in (("nozeros", 0.97), ("noprefix", 0.965), ("digits", 0.96)):
                    ids = apply_transform(id_df[ic], tf)
                    idset = set(ids.dropna())
                    if not idset or _uniq(ids) < 0.5:
                        continue
                    pk = (id(text_df), tc)
                    if pk not in prepared:
                        prepared[pk] = prepare_text(text_df[tc])
                    found = extract_against(text_df[tc], idset, prepared=prepared[pk])
                    if found.notna().sum() == 0:
                        continue
                    nt, ni = int(text_df[tc].notna().sum()), int(id_df[ic].notna().sum())
                    ct = float(found.notna().sum() / max(1, nt))
                    ci = float(_isin(ids, set(found.dropna())).sum() / max(1, ni))
                    score = _cov_score(ci, ct, ni, nt) * weight
                    if best is None or score > best[0]:
                        ex = [(id_df.loc[ids == found[idx], ic].iloc[0], text_df.at[idx, tc]) for idx in found.dropna().index[:3]]
                        best = (score, tf, ci, ct, _uniq(ids), ex)
                if not best:
                    continue
                score, tf, ci, ct, u, ex = best
                if id_is_left:
                    cands.append(KeyCandidate(ic, tc, tf, "extract", "extract_right", round(ci, 4), round(ct, 4),
                                              round(u, 3), 1.0, round(min(score, 1.0), 4), ex))
                else:
                    cands.append(KeyCandidate(tc, ic, "extract", tf, "extract_left", round(ct, 4), round(ci, 4),
                                              1.0, round(u, 3), round(min(score, 1.0), 4), [(b, a) for a, b in ex]))

    extract(L, lp, R, rp, True)
    extract(R, rp, L, lp, False)

    # 3) composite fallback: amount + date window
    la, ra, ld, rd = pick_amount(lp), pick_amount(rp), pick_date(lp), pick_date(rp)
    if la and ra:
        lam = parse_amount(L[la]).abs().round(2)
        ram = parse_amount(R[ra]).abs().round(2)
        counts = ram.value_counts()
        found = lam.map(counts).fillna(0)
        cov = float((found > 0).mean())
        ambiguous = float((found > 1).sum() / max(1, (found > 0).sum()))
        if ld and rd:
            ldt, _, _ = parse_date(L[ld])
            rdt, _, _ = parse_date(R[rd])
            rmap: dict[float, list] = {}
            for a, d in zip(ram, rdt):
                rmap.setdefault(a, []).append(d)
            ok, amb = 0, 0
            for a, d in zip(lam, ldt):
                ds = [x for x in rmap.get(a, []) if pd.notna(x) and pd.notna(d) and abs((x - d).days) <= date_window_days]
                ok += len(ds) >= 1
                amb += len(ds) > 1
            cov = ok / max(1, len(lam))
            ambiguous = amb / max(1, ok)
        rev = float(ram.isin(set(lam.dropna())).mean())
        score = _cov_score(cov, rev, len(lam), len(ram)) * (1 - ambiguous) * 0.85
        if cov > 0:
            cands.append(KeyCandidate(None, None, "amount", "amount", "composite", round(cov, 4), round(rev, 4), 0, 0, round(score, 4),
                                      note=f"{la} ⟷ {ra}" + (f", {ld} ⟷ {rd} ±{date_window_days}d" if ld and rd else "")
                                      + f"; {ambiguous:.0%} ambiguous"))

    cands.sort(key=lambda c: c.score, reverse=True)
    # one candidate per column pair
    seen, out = set(), []
    for c in cands:
        k = (c.left_col, c.right_col, c.mode)
        if k not in seen:
            seen.add(k)
            out.append(c)
    return out[:top]
