"""Deterministic, tiered matching engine for one pair of documents.

Tiers (each only sees rows not matched by an earlier tier):
  1..k  key tiers       one per KeySpec, in the order given (exact > transformed > extracted)
  agg   aggregate tier  many rows on one side vs one row on the other (e.g. daily settlement)
  comp  composite tier  amount + date window, only when the pairing is unambiguous both ways

Every match records the rule that produced it so the result is auditable and reproducible.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field, asdict

import numpy as np
import pandas as pd

from .discover import apply_transform, extract_against
from .models import OCR_CONF, ROWID, Dataset
from .profile import parse_amount, parse_date

OCR_REVIEW_BELOW = 80.0


@dataclass
class KeySpec:
    left_col: str | None
    right_col: str | None
    left_tf: str = "alnum"
    right_tf: str = "alnum"
    mode: str = "key"          # key | extract_left | extract_right

    def label(self) -> str:
        if self.mode == "extract_right":
            return f"{self.left_col}[{self.left_tf}] found in text {self.right_col}"
        if self.mode == "extract_left":
            return f"text {self.left_col} contains {self.right_col}[{self.right_tf}]"
        return f"{self.left_col}[{self.left_tf}] = {self.right_col}[{self.right_tf}]"


@dataclass
class AggregateSpec:
    side: str = "left"                 # side with MANY rows per single row on the other side
    group_by: str = ""                 # grouping column on the many side (settlement date, batch id...)
    other_col: str | None = None       # optional column on the single side holding the same group value
    amount_tol_pct: float = 0.0


@dataclass
class PairConfig:
    left: str
    right: str
    keys: list[KeySpec] = field(default_factory=list)
    left_amount: str | None = None
    right_amount: str | None = None
    left_date: str | None = None
    right_date: str | None = None
    amount_tol: float = 0.01
    amount_tol_pct: float = 0.0
    expected_fee_pct: float = 0.0      # right ≈ left × (1 − fee%) e.g. MDR deducted at settlement
    date_window_days: int = 3
    compare_abs: bool = True
    use_composite: bool = True
    one_to_many: bool = True
    aggregate: AggregateSpec | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PairConfig":
        d = dict(d)
        d["keys"] = [KeySpec(**k) for k in d.get("keys", [])]
        if d.get("aggregate"):
            d["aggregate"] = AggregateSpec(**d["aggregate"])
        return cls(**d)

    def rule_text(self) -> str:
        parts = [f"amount tol ±{self.amount_tol}" + (f" or {self.amount_tol_pct}%" if self.amount_tol_pct else "")]
        if self.expected_fee_pct:
            parts.append(f"expected fee {self.expected_fee_pct}%")
        parts.append(f"date window ±{self.date_window_days}d")
        return "; ".join(parts)


@dataclass
class PairResult:
    config: PairConfig
    matches: pd.DataFrame
    exceptions: pd.DataFrame
    left_unmatched: pd.DataFrame
    right_unmatched: pd.DataFrame
    summary: dict
    insights: list[str]
    links: list[tuple[list[str], list[str], str]]   # (left rowids, right rowids, status) for chaining


class _Side:
    def __init__(self, ds: Dataset, amount_col, date_col, compare_abs):
        self.ds = ds
        self.df = ds.df
        n = len(self.df)
        self.ids = self.df[ROWID].astype(str).tolist()
        self.amt = parse_amount(self.df[amount_col]).to_numpy(dtype=float) if amount_col else np.full(n, np.nan)
        self.raw = self.amt.copy()          # signed, before abs: used to stop refunds pairing with sales
        if compare_abs:
            self.amt = np.abs(self.amt)
        self.date = parse_date(self.df[date_col])[0].to_numpy() if date_col else np.full(n, np.datetime64("NaT", "ns"))
        self.conf = self.df[OCR_CONF].to_numpy(dtype=float) if OCR_CONF in self.df.columns else None
        self.used = np.zeros(n, dtype=bool)
        self.flags: dict[int, tuple[str, str]] = {}

    def total(self, idx):
        vals = self.amt[idx]
        return float(np.nansum(vals)) if not np.all(np.isnan(vals)) else float("nan")


class Matcher:
    def __init__(self, left: Dataset, right: Dataset, cfg: PairConfig):
        self.cfg = cfg
        self.L = _Side(left, cfg.left_amount, cfg.left_date, cfg.compare_abs)
        self.R = _Side(right, cfg.right_amount, cfg.right_date, cfg.compare_abs)
        self.rows: list[dict] = []
        self.n = 0

    # ---------------------------------------------------------------- helpers
    def expected(self, left_amount: float) -> float:
        return left_amount * (1 - self.cfg.expected_fee_pct / 100.0)

    def amount_ok(self, al: float, ar: float, extra_pct: float = 0.0) -> bool:
        if np.isnan(al) or np.isnan(ar):
            return True
        exp = self.expected(al)
        diff = abs(ar - exp)
        pct = max(self.cfg.amount_tol_pct, extra_pct)
        return diff <= self.cfg.amount_tol + 1e-9 or (pct > 0 and diff <= abs(exp) * pct / 100 + 1e-9)

    def date_gap(self, li, ri) -> float:
        ld = [d for d in self.L.date[li] if not pd.isna(d)]
        rd = [d for d in self.R.date[ri] if not pd.isna(d)]
        if not ld or not rd:
            return float("nan")
        gaps = [min(abs((a - b) / np.timedelta64(1, "D")) for b in rd) for a in ld]
        return float(max(gaps))

    def record(self, li, ri, tier: str, rule: str, key, base_conf: float, extra_pct: float = 0.0):
        al, ar = self.L.total(li), self.R.total(ri)
        a_ok = self.amount_ok(al, ar, extra_pct)
        gap = self.date_gap(li, ri)
        d_ok = np.isnan(gap) or gap <= self.cfg.date_window_days
        low_ocr = any(s.conf is not None and np.nanmin(np.append(s.conf[idx], 100)) < OCR_REVIEW_BELOW
                      for s, idx in ((self.L, li), (self.R, ri)))
        if not a_ok:
            status = "amount_variance"
        elif not d_ok:
            status = "date_variance"
        elif low_ocr:
            status = "needs_review"
        else:
            status = "matched"
        conf = base_conf * (1.0 if status == "matched" else 0.6)
        self.n += 1
        exp = self.expected(al) if not np.isnan(al) else np.nan
        self.rows.append(dict(
            match_id=f"M{self.n:06d}", tier=tier, cardinality=f"{len(li)}:{len(ri)}", status=status,
            key=key, left_rows=";".join(self.L.ids[i] for i in li), right_rows=";".join(self.R.ids[i] for i in ri),
            left_amount=None if np.isnan(al) else round(al, 2), right_amount=None if np.isnan(ar) else round(ar, 2),
            expected_right=None if np.isnan(exp) or not self.cfg.expected_fee_pct else round(exp, 2),
            difference=None if np.isnan(al) or np.isnan(ar) else round(ar - (exp if self.cfg.expected_fee_pct else al), 2),
            date_gap_days=None if np.isnan(gap) else round(gap, 1), confidence=round(conf, 2),
            rule=f"{rule}; {self.cfg.rule_text()}"))
        self.L.used[li] = True
        self.R.used[ri] = True

    def flag(self, side: _Side, idx, category, detail):
        for i in idx:
            side.flags.setdefault(i, (category, detail))

    # ---------------------------------------------------------------- tiers
    def key_tier(self, spec: KeySpec, tier: str):
        L, R, cfg = self.L, self.R, self.cfg
        if spec.mode == "key":
            kl = apply_transform(L.df[spec.left_col], spec.left_tf, min_len=1)
            kr = apply_transform(R.df[spec.right_col], spec.right_tf, min_len=1)
            base = 1.0 if spec.left_tf == spec.right_tf == "exact" else 0.98
        elif spec.mode == "extract_right":
            kl = apply_transform(L.df[spec.left_col], spec.left_tf if spec.left_tf != "extract" else "nozeros")
            kr, how = extract_against(R.df[spec.right_col], set(kl.dropna()), with_how=True)
            self._how = {k: h for k, h in zip(kr, how) if isinstance(k, str)}
            base = 0.95
        elif spec.mode == "extract_left":
            kr = apply_transform(R.df[spec.right_col], spec.right_tf if spec.right_tf != "extract" else "nozeros")
            kl, how = extract_against(L.df[spec.left_col], set(kr.dropna()), with_how=True)
            self._how = {k: h for k, h in zip(kl, how) if isinstance(k, str)}
            base = 0.95
        else:
            raise ValueError(spec.mode)
        lg, rg = defaultdict(list), defaultdict(list)
        for i, k in enumerate(kl.tolist()):
            if isinstance(k, str) and not L.used[i]:
                lg[k].append(i)
        for i, k in enumerate(kr.tolist()):
            if isinstance(k, str) and not R.used[i]:
                rg[k].append(i)
        rule = spec.label()
        how = getattr(self, "_how", {}) if spec.mode != "key" else {}
        for k in lg.keys() & rg.keys():
            li, ri = lg[k], rg[k]
            if how.get(k) == "substring":
                rule_k, base_k = rule + " (found by scanning text with separators removed)", base * 0.95
            else:
                rule_k, base_k = rule, base
            if len(li) == 1 and len(ri) == 1:
                self.record(li, ri, tier, rule_k, k, base_k)
            elif len(li) == 1 and cfg.one_to_many:
                self._one_vs_many(li, ri, k, tier, rule_k, base_k, single_left=True)
            elif len(ri) == 1 and cfg.one_to_many:
                self._one_vs_many(ri, li, k, tier, rule_k, base_k, single_left=False)
            else:
                self._many_vs_many(li, ri, k, tier, rule_k, base_k)
        self._key_cache = (kl, kr)
        self._how = {}

    def _one_vs_many(self, one, many, k, tier, rule, base, single_left):
        S1, SM = (self.L, self.R) if single_left else (self.R, self.L)
        a1, am = S1.total(one), SM.total(many)
        ok = self.amount_ok(a1, am) if single_left else self.amount_ok(am, a1)
        if ok:
            li, ri = (one, many) if single_left else (many, one)
            self.record(li, ri, tier, rule + " (1:n sum)", k, base * 0.95)
            return
        for m in many:
            single_ok = self.amount_ok(a1, SM.amt[m]) if single_left else self.amount_ok(SM.amt[m], a1)
            if single_ok:
                li, ri = ([one[0]], [m]) if single_left else ([m], [one[0]])
                self.record(li, ri, tier, rule, k, base)
                rest = [x for x in many if x != m]
                self.flag(SM, rest, "duplicate_key", f"key {k} also used by another row that was matched")
                return
        # The key links them unambiguously (one row vs a group), so record the group with its variance:
        # e.g. a settlement batch that was short-paid.
        li, ri = (one, many) if single_left else (many, one)
        self.record(li, ri, tier, rule + " (1:n sum, does not reconcile)", k, base * 0.95)

    def _many_vs_many(self, li, ri, k, tier, rule, base):
        free = list(ri)
        for l in li:
            hit = next((r for r in free if self.amount_ok(self.L.amt[l], self.R.amt[r])), None)
            if hit is not None:
                self.record([l], [hit], tier, rule + " (n:m by amount)", k, base * 0.9)
                free.remove(hit)
        self.flag(self.L, [l for l in li if not self.L.used[l]], "duplicate_key", f"key {k} duplicated on both sides")
        self.flag(self.R, free, "duplicate_key", f"key {k} duplicated on both sides")

    def aggregate_tier(self, agg: AggregateSpec):
        many_left = agg.side == "left"
        M, O = (self.L, self.R) if many_left else (self.R, self.L)
        gvals = M.df[agg.group_by].astype("string").str.strip()
        groups = defaultdict(list)
        for i, g in enumerate(gvals.tolist()):
            if isinstance(g, str) and g and not M.used[i]:
                groups[g].append(i)
        rule = f"aggregate: sum of {('left' if many_left else 'right')} rows grouped by {agg.group_by}"
        other_keys = None
        if agg.other_col:
            other_keys = apply_transform(O.df[agg.other_col], "alnum", min_len=1)
            rule += f" = {agg.other_col}"
        for g, idx in groups.items():
            total = M.total(idx)
            if other_keys is not None:
                gk = apply_transform(pd.Series([g]), "alnum", min_len=1).iloc[0]
                cands = [j for j, v in enumerate(other_keys.tolist()) if v == gk and not O.used[j]]
            else:
                cands = []
                for j in np.where(~O.used)[0]:
                    ok = self.amount_ok(total, O.amt[j], agg.amount_tol_pct) if many_left else self.amount_ok(O.amt[j], total, agg.amount_tol_pct)
                    if not ok:
                        continue
                    li, ri = (idx, [j]) if many_left else ([j], idx)
                    gap = self.date_gap(li, ri)
                    if np.isnan(gap) or gap <= self.cfg.date_window_days:
                        cands.append(j)
            if len(cands) == 1:
                li, ri = (idx, cands) if many_left else (cands, idx)
                self.record(li, ri, "aggregate", rule, g, 0.85, agg.amount_tol_pct)

    def composite_tier(self):
        L, R = self.L, self.R
        win = self.cfg.date_window_days

        def bucket(side, exp=False):
            b = defaultdict(list)
            for i in np.where(~side.used & ~np.isnan(side.amt))[0]:
                v = self.expected(side.amt[i]) if exp else side.amt[i]
                b[int(round(v * 100))].append(i)
            return b

        rb = bucket(R)
        lb = bucket(L, exp=True)

        def near(b, cents):
            return [x for c in (cents - 1, cents, cents + 1) for x in b.get(c, [])]

        def date_ok(dl, dr):
            return pd.isna(dl) or pd.isna(dr) or abs((dl - dr) / np.timedelta64(1, "D")) <= win

        def sign_ok(l, r):
            a, b = L.raw[l], R.raw[r]
            return np.isnan(a) or np.isnan(b) or a == 0 or b == 0 or np.sign(a) == np.sign(b)

        for l in np.where(~L.used & ~np.isnan(L.amt))[0]:
            if L.used[l]:
                continue
            cents = int(round(self.expected(L.amt[l]) * 100))
            rc = [r for r in near(rb, cents) if not R.used[r] and date_ok(L.date[l], R.date[r]) and sign_ok(l, r)]
            if len(rc) != 1:
                if len(rc) > 1:
                    self.flag(L, [l], "ambiguous_amount", f"{len(rc)} unmatched rows on the other side share this amount/date")
                continue
            r = rc[0]
            lc = [x for x in near(lb, int(round(R.amt[r] * 100))) if not L.used[x] and date_ok(L.date[x], R.date[r]) and sign_ok(x, r)]
            if len(lc) == 1 and lc[0] == l:
                self.record([l], [r], "composite", "amount + date window (no shared identifier)", None, 0.7)

    # ---------------------------------------------------------------- run
    def run(self) -> PairResult:
        cfg = self.cfg
        for i, spec in enumerate(cfg.keys, start=1):
            self.key_tier(spec, f"key{i}")
        if cfg.aggregate and cfg.aggregate.group_by:
            self.aggregate_tier(cfg.aggregate)
        if cfg.use_composite and (cfg.left_amount and cfg.right_amount):
            self.composite_tier()
        return self._finish()

    def _finish(self) -> PairResult:
        cfg, L, R = self.cfg, self.L, self.R
        matches = pd.DataFrame(self.rows, columns=["match_id", "tier", "cardinality", "status", "key", "left_rows", "right_rows",
                                                   "left_amount", "right_amount", "expected_right", "difference",
                                                   "date_gap_days", "confidence", "rule"])
        insights = self._insights(matches)
        exc = []
        for _, m in matches[matches.status != "matched"].iterrows():
            detail = {"amount_variance": f"amount differs by {m.difference}",
                      "date_variance": f"dates {m.date_gap_days} days apart (window ±{cfg.date_window_days}d)",
                      "needs_review": "OCR-derived row below confidence threshold; verify against the source image"}[m.status]
            exc.append(dict(category=m.status, side="both", rows=f"L[{m.left_rows}] R[{m.right_rows}]", key=m.key,
                            left_amount=m.left_amount, right_amount=m.right_amount, detail=detail, suggestion="", match_id=m.match_id))
        sugg_l, sugg_r = self._suggestions()
        for side, S, label, sugg in ((L, L, "left", sugg_l), (R, R, "right", sugg_r)):
            other = cfg.right if label == "left" else cfg.left
            for i in np.where(~S.used)[0]:
                cat, detail = S.flags.get(i, (f"missing_in_{other}", f"no counterpart found in {other}"))
                d = S.date[i]
                exc.append(dict(category=cat, side=label, rows=S.ids[i], key=None,
                                left_amount=None if label == "right" or np.isnan(S.amt[i]) else round(float(S.amt[i]), 2),
                                right_amount=None if label == "left" or np.isnan(S.amt[i]) else round(float(S.amt[i]), 2),
                                detail=detail + ("" if pd.isna(d) else f" (date {pd.Timestamp(d).date()})"),
                                suggestion=sugg.get(i, ""), match_id=None))
        exceptions = pd.DataFrame(exc, columns=["category", "side", "rows", "key", "left_amount", "right_amount", "detail", "suggestion", "match_id"])

        def visible(S):
            cols = [c for c in S.df.columns if c == ROWID or not c.startswith("__")]
            return S.df.loc[~S.used, cols]

        ok = matches.status == "matched"
        l_matched_rows = sum(len(x.split(";")) for x in matches.loc[ok, "left_rows"]) if ok.any() else 0
        r_matched_rows = sum(len(x.split(";")) for x in matches.loc[ok, "right_rows"]) if ok.any() else 0
        lt, rt = float(np.nansum(L.amt)), float(np.nansum(R.amt))
        lm = float(matches.loc[ok, "left_amount"].fillna(0).sum())
        rm = float(matches.loc[ok, "right_amount"].fillna(0).sum())
        summary = dict(
            pair=f"{cfg.left} ⟷ {cfg.right}",
            left_rows=len(L.ids), right_rows=len(R.ids),
            matched_groups=int(ok.sum()), exception_groups=int((~ok).sum()),
            left_rows_matched=l_matched_rows, right_rows_matched=r_matched_rows,
            left_unmatched=int((~L.used).sum()), right_unmatched=int((~R.used).sum()),
            left_match_rate_pct=round(100 * l_matched_rows / max(1, len(L.ids)), 2),
            right_match_rate_pct=round(100 * r_matched_rows / max(1, len(R.ids)), 2),
            left_total=round(lt, 2), right_total=round(rt, 2),
            left_value_matched_pct=round(100 * lm / lt, 2) if lt else None,
            right_value_matched_pct=round(100 * rm / rt, 2) if rt else None,
            by_tier=matches.groupby("tier").size().to_dict() if len(matches) else {},
            by_status=matches.groupby("status").size().to_dict() if len(matches) else {},
            exceptions_by_category=exceptions.groupby("category").size().to_dict() if len(exceptions) else {},
        )
        links = [(r.left_rows.split(";"), r.right_rows.split(";"), r.status) for r in matches.itertuples()]
        return PairResult(cfg, matches, exceptions, visible(L), visible(R), summary, insights, links)

    def _insights(self, matches: pd.DataFrame) -> list[str]:
        out = []
        var = matches[(matches.status == "amount_variance") & matches.left_amount.notna() & matches.right_amount.notna()]
        var = var[var.left_amount.astype(float) != 0]
        if len(var) >= 5:
            pct = (var.right_amount.astype(float) - var.left_amount.astype(float)) / var.left_amount.astype(float).abs() * 100
            med = float(pct.median())
            share = float((abs(pct - med) <= 0.05).mean())
            if share >= 0.7:
                out.append(f"{share:.0%} of amount variances sit at {med:+.2f}% of the left amount: consistent with a percentage fee/MDR. "
                           f"Re-run with expected_fee_pct={-med:.2f} to reconcile net of fees.")
            diff = var.right_amount.astype(float) - var.left_amount.astype(float)
            dmed = float(diff.median())
            dshare = float((abs(diff - dmed) <= 0.01).mean())
            if dshare >= 0.7 and share < 0.7:
                out.append(f"{dshare:.0%} of amount variances equal {dmed:+.2f}: consistent with a fixed per-transaction fee.")
        if len(matches):
            gaps = matches.date_gap_days.dropna()
            if len(gaps) and gaps.median() >= 1:
                out.append(f"Median date gap between matched rows is {gaps.median():.0f} day(s): settlement lag (T+{gaps.median():.0f}).")
        return out

    def _suggestions(self):
        """Near-miss hints for unmatched rows: similar keys, or same amount within the date window."""
        from .fuzzy import extract_one, partial_ratio
        sl, sr = {}, {}
        cache = getattr(self, "_key_cache", None)
        if cache is not None and self.cfg.keys and self.cfg.keys[0].mode == "key":
            kl, kr = cache
            lu = [i for i in np.where(~self.L.used)[0] if isinstance(kl.iloc[i], str)][:5000]
            ru = [i for i in np.where(~self.R.used)[0] if isinstance(kr.iloc[i], str)]
            choices = {i: kr.iloc[i] for i in ru}
            if choices:
                for i in lu:
                    hit = extract_one(kl.iloc[i], choices, 85)
                    if hit:
                        _, score, j = hit
                        sl[i] = f"possible key typo: right row {self.R.ids[j]} has '{kr.iloc[j]}' ({score:.0f}% similar)"
                        sr.setdefault(j, f"possible key typo: left row {self.L.ids[i]} has '{kl.iloc[i]}' ({score:.0f}% similar)")
        spec = self.cfg.keys[0] if self.cfg.keys else None
        if cache is not None and spec is not None and spec.mode in ("extract_right", "extract_left"):
            kl, kr = cache
            text_right = spec.mode == "extract_right"
            T, I = (self.R, self.L) if text_right else (self.L, self.R)
            tcol = spec.right_col if text_right else spec.left_col
            icol, itf = (spec.left_col, spec.left_tf) if text_right else (spec.right_col, spec.right_tf)
            ids = apply_transform(I.df[icol], itf if itf != "extract" else "nozeros")
            free_ids = [j for j in np.where(~I.used)[0] if isinstance(ids.iloc[j], str)]
            for t in np.where(~T.used)[0][:5000]:
                txt = T.df[tcol].iloc[t]
                if not isinstance(txt, str):
                    continue
                compact = re.sub(r"[^A-Z0-9]", "", txt.upper())
                for j in free_ids:
                    a_ok = self.amount_ok(I.amt[j], T.amt[t]) if text_right else self.amount_ok(T.amt[t], I.amt[j])
                    if not a_ok or np.isnan(T.amt[t]):
                        continue
                    gap = self.date_gap([j], [t]) if text_right else self.date_gap([t], [j])
                    if not (np.isnan(gap) or gap <= self.cfg.date_window_days):
                        continue
                    score = partial_ratio(ids.iloc[j], compact)
                    if score >= 90:
                        msg_t = f"narration nearly contains '{ids.iloc[j]}' ({score:.0f}% similar) from row {I.ids[j]}, and amount/date agree: likely typo or OCR misread"
                        msg_i = f"row {T.ids[t]} narration nearly contains this reference ({score:.0f}% similar) and amount/date agree"
                        (sr if text_right else sl).setdefault(t, msg_t)
                        (sl if text_right else sr).setdefault(j, msg_i)
                        break
        return sl, sr


def reconcile(left: Dataset, right: Dataset, cfg: PairConfig) -> PairResult:
    return Matcher(left, right, cfg).run()
