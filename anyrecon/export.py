"""The downloadable report: plain tables built from the match results.

Default sheets: Matched and Exceptions. Exceptions lists everything that didn't reconcile, one row each, with
the likely reason (or "No clear reason") and an action; rows with no clear reason come first. Optional sheets,
chosen by the user at export: Groups (keys linking more than one record), Overview, Only in <file>, and
Across all files. Values come from the original rows, so keys, dates and amounts look as they do in the files.
"""
from __future__ import annotations

import pandas as pd

from .match import PairResult
from .models import ROWID, Dataset
from .profile import parse_date

NO_REASON = "No clear reason"
INVESTIGATE = "Investigate"

# Sheets a user can choose at export: key -> label. Matched and Exceptions are ticked by default.
SHEETS = {
    "matched": "Matched",
    "exceptions": "Exceptions",
    "groups": "Groups",
    "overview": "Overview",
    "only": "Only in each file",
    "across": "Across all files",
}
DEFAULT = ("matched", "exceptions")


def available(results: dict[str, PairResult], chain: pd.DataFrame | None) -> list[str]:
    """Which sheets make sense for this run (Groups only when some links aren't one-to-one; Across all
    files only with three or more files)."""
    out = ["matched", "exceptions"]
    if any((r.matches.cardinality != "1:1").any() for r in results.values() if len(r.matches)):
        out.append("groups")
    out += ["overview", "only"]
    if chain is not None and len(chain):
        out.append("across")
    return out


class _Rows:
    """Looks up a file's original values by row id (the `__row` origin, e.g. L12 or P3:R7)."""

    def __init__(self, ds: Dataset, key_col, date_col, amount_col):
        df = ds.df
        self.pos = pd.Series(range(len(df)), index=df[ROWID].astype(str)).to_dict()
        self.cols = {}
        for name, c in (("key", key_col), ("date", date_col), ("amount", amount_col)):
            self.cols[name] = df[c].astype(object).where(df[c].notna(), None).tolist() if c and c in df.columns else None
        # Dates read with the format detected for the whole column (so 2026-10-05 stays 5 Oct, 05/10/2026 is
        # day-first), shown as plain dates; anything unreadable is shown as written in the file.
        self.dates = None
        if date_col and date_col in df.columns:
            parsed, _, _ = parse_date(df[date_col])
            raw = self.cols["date"]
            self.dates = [p if pd.notna(p) else None for p in parsed.tolist()]
            self.cols["date"] = [(p.date() if p.time() == pd.Timestamp(0).time() else p.to_pydatetime()) if p is not None else r
                                 for p, r in zip(self.dates, raw)]

    def get(self, rowids: str, what: str):
        """Value for one row id; for several ('L1;L2'), the first (key, date) or the list as text."""
        vals = self.cols.get(what)
        if vals is None or not rowids:
            return None
        ids = [x for x in str(rowids).split(";") if x]
        got = [vals[self.pos[i]] for i in ids if i in self.pos]
        got = [g for g in got if g not in (None, "")]
        if not got:
            return None
        return got[0]


def _key_cols(r: PairResult):
    if not r.config.keys:
        return None, None
    k = r.config.keys[0]
    return k.left_col, k.right_col


def _linked_by(r: PairResult, tier: str) -> str:
    cfg = r.config
    if tier and tier.startswith("key"):
        try:
            k = cfg.keys[int(tier[3:]) - 1]
        except (ValueError, IndexError):
            k = cfg.keys[0] if cfg.keys else None
        if k is None:
            return "Reference"
        if k.mode == "extract_right":
            how = f"{k.left_col} found in {k.right_col}"
        elif k.mode == "extract_left":
            how = f"{k.right_col} found in {k.left_col}"
        else:
            how = k.left_col if k.left_col == k.right_col else f"{k.left_col} = {k.right_col}"
    elif tier == "aggregate":
        how = "Batch total"
    elif tier == "composite":
        how = "Amount and date"
    else:
        how = tier or ""
    fee = cfg.expected_fee_pct
    if fee:
        how += f"; {abs(fee):g}% {'lower' if fee > 0 else 'higher'} in {cfg.right}"
    return how


def _pct_explained(r: PairResult, la, ra):
    """Reason when an amount difference fits the file-wide percentage pattern the matcher detected."""
    fee = r.summary.get("detected_fee_pct")
    try:
        la, ra = float(la), float(ra)
    except (TypeError, ValueError):
        return None
    if not fee or not la:
        return None
    pct = (ra - la) / abs(la) * 100
    if abs(pct + fee) > 0.05:
        return None
    p, right = abs(fee), r.config.right
    if fee > 0:
        return (f"{right} is {p:g}% lower, like most differences in this file: likely a {p:g}% fee",
                f"Confirm the {p:g}% fee is the agreed rate")
    return (f"{right} is {p:g}% higher, like most differences in this file: likely a {p:g}% charge added",
            f"Confirm the {p:g}% charge is agreed")


def _date_range(rows: _Rows):
    d = [x for x in (rows.dates or []) if x is not None]
    return (min(d), max(d)) if d else None


def tables(datasets: dict[str, Dataset], results: dict[str, PairResult], chain: pd.DataFrame | None = None) -> dict[str, pd.DataFrame | dict]:
    multi = len(results) > 1
    matched, exceptions, groups, overview, only = [], [], [], [], {}
    for r in results.values():
        cfg = r.config
        A, B = cfg.left, cfg.right
        kl, kr = _key_cols(r)
        LA = _Rows(datasets[A], kl, cfg.left_date, cfg.left_amount)
        RB = _Rows(datasets[B], kr, cfg.right_date, cfg.right_amount)
        rng = {A: _date_range(LA), B: _date_range(RB)}
        pair = f"{A} ↔ {B}"
        # One pair: columns carry the file names. Several pairs share one sheet, so columns say A and B and the
        # Compared column names the files ("processor (A) ↔ bank (B)").
        a_, b_ = ("A", "B") if multi else (A, B)
        head = {"Compared": f"{A} (A) ↔ {B} (B)"} if multi else {}
        has_date = bool(cfg.left_date or cfg.right_date)
        has_amt = bool(cfg.left_amount or cfg.right_amount)

        def rec(key, where, la, ra, da, db, reason, action):
            d = dict(head, Key=key, Where=where)
            if has_date:
                d[f"Date ({a_})"], d[f"Date ({b_})"] = da, db
            if has_amt:
                d[f"Amount ({a_})"], d[f"Amount ({b_})"] = la, ra
            d["Reason"], d["Action"] = reason, action
            return d

        # Matched (and groups)
        m = r.matches
        for row in m.itertuples(index=False):
            key = row.key if isinstance(row.key, str) and row.key else (LA.get(row.left_rows, "key") or RB.get(row.right_rows, "key"))
            if row.status == "matched":
                d = dict(head, Key=key)
                if has_date:
                    d[f"Date ({a_})"], d[f"Date ({b_})"] = LA.get(row.left_rows, "date"), RB.get(row.right_rows, "date")
                if has_amt:
                    d[f"Amount ({a_})"], d[f"Amount ({b_})"] = row.left_amount, row.right_amount
                d["Linked by"] = _linked_by(r, row.tier)
                if row.cardinality != "1:1":
                    d["Group"] = row.match_id
                matched.append(d)
            if row.cardinality != "1:1":
                g = dict(head, Key=key)
                g[f"Records in {a_}"] = len(str(row.left_rows).split(";"))
                g[f"Records in {b_}"] = len(str(row.right_rows).split(";"))
                if has_amt:
                    g[f"Total ({a_})"], g[f"Total ({b_})"] = row.left_amount, row.right_amount
                g["Agree"] = "Yes" if row.status == "matched" else "No"
                g["Group"] = row.match_id
                groups.append(g)

        # Exceptions, each with its reason and action
        for e in r.exceptions.itertuples(index=False):
            cat, side = e.category, e.side
            if side == "both":
                lrows, rrows = str(e.rows).split("] R[")
                lrows, rrows = lrows.removeprefix("L["), rrows.rstrip("]")
                da, db = LA.get(lrows, "date"), RB.get(rrows, "date")
                key = e.key if isinstance(e.key, str) and e.key else LA.get(lrows, "key")
                if cat == "amount_variance":
                    why = _pct_explained(r, e.left_amount, e.right_amount)
                    reason, action = why or (NO_REASON, INVESTIGATE)
                    where = "In both, amounts differ"
                elif cat == "date_variance":
                    gap = str(e.detail).split(" days")[0].replace("dates ", "")
                    reason, action = f"Timing: dates {gap} days apart", "Confirm the dates; it should clear"
                    where = "In both, dates differ"
                else:
                    reason, action = "Read from a scan with low confidence", "Check against the original"
                    where = "In both, needs a check"
                exceptions.append(rec(key, where, e.left_amount, e.right_amount, da, db, reason, action))
                continue
            own, other, rows_ = (A, B, LA) if side == "left" else (B, A, RB)
            rid = str(e.rows)
            key, date = rows_.get(rid, "key"), rows_.get(rid, "date")
            when = rows_.dates[rows_.pos[rid]] if rows_.dates is not None and rid in rows_.pos else None
            amt = e.left_amount if side == "left" else e.right_amount
            where = f"Only in {own}"
            reason, action = NO_REASON, INVESTIGATE
            if cat.startswith("missing_in_"):
                sugg = str(e.suggestion or "")
                d = when
                orng = rng.get(other)
                if sugg:
                    reason, action = "Possible typo: " + sugg.split(": ", 1)[-1], "Check the reference"
                elif orng is not None and d is not None and (d.normalize() > orng[1].normalize() or d.normalize() < orng[0].normalize()):
                    later = d.normalize() > orng[1].normalize()
                    reason = f"Outside {other}'s dates ({orng[0].date()} to {orng[1].date()})"
                    action = f"Check the {'next' if later else 'previous'} {other} file"
            elif cat == "duplicate_key":
                reason, action = "Same reference appears more than once", "Check for a duplicate entry"
            elif cat == "ambiguous_amount":
                reason, action = "Several possible matches with the same amount and date", "Choose the right match"
            la, ra = (amt, None) if side == "left" else (None, amt)
            da, db = (date, None) if side == "left" else (None, date)
            exceptions.append(rec(key, where, la, ra, da, db, reason, action))

        n_exc = [x for x in exceptions if x.get("Compared") == head.get("Compared")]
        s = r.summary
        overview.append({"Compared": pair, f"Records": f"{s['left_rows']:,} in {A} · {s['right_rows']:,} in {B}",
                         "Matched": s["matched_groups"],
                         "In both, different": sum(1 for x in n_exc if str(x["Where"]).startswith("In both")),
                         f"Only in {a_}": sum(1 for x in n_exc if x["Where"] == f"Only in {A}"),
                         f"Only in {b_}": sum(1 for x in n_exc if x["Where"] == f"Only in {B}"),
                         "With a likely reason": sum(1 for x in n_exc if x["Reason"] != NO_REASON),
                         "No clear reason": sum(1 for x in n_exc if x["Reason"] == NO_REASON)})
        for name, df in ((A, r.left_unmatched), (B, r.right_unmatched)):
            label = f"Only in {name}" + (f" (vs {B if name == A else A})" if multi else "")
            if len(df):
                only[label] = df.rename(columns={ROWID: "Row in file"})

    exc = pd.DataFrame(exceptions)
    if len(exc):
        exc = exc.assign(_o=(exc["Reason"] != NO_REASON).astype(int)).sort_values(["_o", "Where"], kind="stable").drop(columns="_o")
    ov = pd.DataFrame(overview)
    if len(ov) and not multi:
        ov = ov.drop(columns="Compared")
    return {"matched": pd.DataFrame(matched), "exceptions": exc, "groups": pd.DataFrame(groups),
            "overview": ov.T.reset_index().set_axis(["Item", "Value"], axis=1) if len(ov) == 1 else ov,
            "only": only, "across": chain if chain is not None else pd.DataFrame()}
