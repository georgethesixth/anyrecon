"""N-way reconciliation: the user defines which documents pair; the engine runs each
pair and then stitches the results into chains (e.g. processor ⟷ ledger ⟷ bank)."""
from __future__ import annotations

import pandas as pd

from .discover import discover
from .match import KeySpec, PairConfig, PairResult, reconcile
from .models import ROWID, Dataset
from .profile import pick_amount, pick_date, profile


def auto_config(left: Dataset, right: Dataset, date_window_days: int = 3, candidates=None) -> tuple[PairConfig, list]:
    cands = candidates if candidates is not None else discover(left, right, date_window_days=date_window_days)
    keys: list[KeySpec] = []
    usable = [c for c in cands if c.mode != "composite" and c.score >= 0.15]
    top = usable[0].score if usable else 0
    for c in usable:
        if c.score < 0.5 * top or len(keys) == 2:
            break
        keys.append(KeySpec(c.left_col, c.right_col, c.left_tf, c.right_tf, c.mode))
    lp, rp = profile(left), profile(right)
    cfg = PairConfig(left=left.name, right=right.name, keys=keys,
                     left_amount=pick_amount(lp), right_amount=pick_amount(rp),
                     left_date=pick_date(lp), right_date=pick_date(rp),
                     date_window_days=date_window_days)
    return cfg, cands


def pair_score(cands) -> float:
    """How well two documents link: best identifier score, or a discounted amount+date pattern."""
    keys = [c.score for c in cands if c.mode != "composite"]
    comp = [c.score for c in cands if c.mode == "composite"]
    return max(keys or [0.0]) if keys else 0.5 * max(comp or [0.0])


def auto_pairs(datasets: dict[str, Dataset], candidates: dict | None = None, date_window_days: int = 3,
               min_score: float = 0.3) -> list[tuple[str, str]]:
    """Choose which documents to reconcile against each other: the strongest links that connect every
    document once (a maximum spanning tree). Two documents give one pair; n give at most n-1."""
    from itertools import combinations
    names = list(datasets)
    cands = candidates if candidates is not None else {}
    edges = []
    for a, b in combinations(names, 2):
        if (a, b) not in cands:
            cands[(a, b)] = discover(datasets[a], datasets[b], date_window_days=date_window_days)
        s = pair_score(cands[(a, b)])
        if s >= min_score:
            edges.append((s, a, b))
    parent = {n: n for n in names}

    def root(n):
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n
    chosen = []
    for s, a, b in sorted(edges, reverse=True):
        ra, rb = root(a), root(b)
        if ra != rb:
            parent[ra] = rb
            chosen.append((a, b))
    return chosen


def reconcile_auto(left: Dataset, right: Dataset, cfg: PairConfig):
    """Reconcile; if the breaks show a consistent percentage difference (a fee taken, e.g. MDR, or a charge added),
    apply it and keep the re-run when it matches more."""
    res = reconcile(left, right, cfg)
    fee = res.summary.get("detected_fee_pct")
    if fee and -20 <= fee <= 20 and not cfg.expected_fee_pct:   # deducted (MDR) or added on top (a surcharge)
        from dataclasses import replace
        cfg2 = replace(cfg, expected_fee_pct=fee)
        res2 = reconcile(left, right, cfg2)
        if res2.summary["matched_groups"] > res.summary["matched_groups"]:
            return res2
    return res


def run_all(datasets: dict[str, Dataset], configs: list[PairConfig], auto_fee: bool = False) -> tuple[dict[str, PairResult], pd.DataFrame | None]:
    results: dict[str, PairResult] = {}
    for cfg in configs:
        if cfg.left not in datasets or cfg.right not in datasets:
            raise KeyError(f"pair {cfg.left} ⟷ {cfg.right}: dataset not loaded (have: {', '.join(datasets)})")
        run = reconcile_auto if auto_fee else reconcile
        results[f"{cfg.left}⟷{cfg.right}"] = run(datasets[cfg.left], datasets[cfg.right], cfg)
    chain = build_chains(datasets, results) if len(configs) > 1 else None
    return results, chain


def build_chains(datasets: dict[str, Dataset], results: dict[str, PairResult], anchor: str | None = None) -> pd.DataFrame:
    """One row per record of the anchor document (default: the document in most pairs),
    traced through every other document; plus orphan rows that never reach the anchor.
    Traversal never passes back through another anchor row, so a settlement batch that
    covers 30 transactions does not merge those 30 transactions into one chain."""
    involved, degree = [], {}
    for r in results.values():
        for n in (r.config.left, r.config.right):
            degree[n] = degree.get(n, 0) + 1
            if n not in involved:
                involved.append(n)
    anchor = anchor or max(involved, key=lambda n: (degree[n], -involved.index(n)))
    adj: dict[str, list[tuple[str, str]]] = {}
    for r in results.values():
        for li, ri, status in r.links:
            ln = [f"{r.config.left}|{x}" for x in li]
            rn = [f"{r.config.right}|{x}" for x in ri]
            for a in ln:
                for b in rn:
                    adj.setdefault(a, []).append((b, status))
                    adj.setdefault(b, []).append((a, status))

    def trace(start: str, blocked_ds: str | None):
        seen, stack, variance = {start}, [start], False
        while stack:
            node = stack.pop()
            for nb, status in adj.get(node, []):
                if nb in seen or (blocked_ds and nb.split("|", 1)[0] == blocked_ds):
                    continue
                seen.add(nb)
                variance |= status != "matched"
                stack.append(nb)
        return seen, variance

    rows, reached = [], set()
    others = [d for d in involved if d != anchor]
    for rid in datasets[anchor].df[ROWID].astype(str):
        node = f"{anchor}|{rid}"
        seen, var = trace(node, anchor)
        reached |= seen
        members: dict[str, list[str]] = {}
        for n in seen:
            ds, x = n.split("|", 1)
            members.setdefault(ds, []).append(x)
        missing = [d for d in others if d not in members]
        status = ("complete_with_variance" if var else "complete") if not missing else (
            "partial" if len(members) > 1 else f"only_in_{anchor}")
        rows.append(dict(status=status, missing=", ".join(missing),
                         **{d: ";".join(sorted(members.get(d, []))) for d in involved}))
    for d in others:
        for rid in datasets[d].df[ROWID].astype(str):
            node = f"{d}|{rid}"
            if node in reached:
                continue
            seen, var = trace(node, anchor)
            reached |= seen
            members = {}
            for n in seen:
                ds, x = n.split("|", 1)
                members.setdefault(ds, []).append(x)
            present = [x for x in involved if x in members]
            rows.append(dict(status="partial" if len(present) > 1 else f"only_in_{d}",
                             missing=", ".join(x for x in involved if x not in members),
                             **{x: ";".join(sorted(members.get(x, []))) for x in involved}))
    df = pd.DataFrame(rows)
    df.insert(0, "chain_id", [f"C{i:06d}" for i in range(1, len(df) + 1)])
    df.insert(1, "anchor", anchor)
    order = {"complete": 0, "complete_with_variance": 1, "partial": 2}
    return df.sort_values("status", key=lambda s: s.map(lambda v: order.get(v, 3)), kind="stable").reset_index(drop=True)
