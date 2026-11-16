"""Command line interface.

  anyrecon inspect FILE [FILE ...]        (Excel: FILE.xlsx#Sheet | #* stack | #each)
  anyrecon suggest LEFT RIGHT
  anyrecon run -f processor=p.csv -f ledger=l.xlsx -f bank=b.pdf -p processor:ledger -p processor:bank \\
               --fee processor:bank=1.5 --out report.xlsx [--interactive] [--save-template t.json]
  anyrecon run -f ... --template t.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, llm
from . import templates as tpl
from .chain import auto_config, run_all
from .discover import discover
from .ingest import UnreadableFile, list_sheets, load, load_each_sheet
from .match import KeySpec
from .pci import PCIBlocked
from .profile import profile
from .report import audit_json, write_excel


def _print_dataset(ds):
    print(f"\n■ {ds.name}  ({ds.fmt}, {len(ds)} rows)  sha256 {ds.file_sha256[:12]}…")
    for n in ds.notes:
        print(f"   note: {n}")
    for w in ds.warnings:
        print(f"   WARNING: {w}")
    for f in ds.findings:
        print(f"   PCI : {f.column}: {f.kind} → {f.action} ({f.count})" + (f"  [{_review_hint(ds, f)}]" if f.review else ""))
    print(f"   {'column':28} {'type':9} {'meaning':11} {'uniq':>5}  shape")
    for c, p in profile(ds).items():
        print(f"   {c[:28]:28} {p.kind:9} {str(p.semantic or ''):11} {p.uniqueness:>5.2f}  {p.top_shape[:24]}  {p.note}")


def _review_hint(ds, f):
    if f.review == "can_keep":
        return f"if this is NOT card security data, rerun with --keep-col {ds.name}:{f.column!r}"
    if f.review == "can_mask":
        return f"to mask anyway, rerun with --mask-col {ds.name}:{f.column!r}"
    return ""


def _overrides(a, name):
    pick = lambda items: [x.split(":", 1)[1].strip("'\"") for x in (items or []) if x.split(":", 1)[0] == name]
    return dict(mask_columns=pick(getattr(a, "mask_col", None)), keep_columns=pick(getattr(a, "keep_col", None)))


def _load_spec(name, path, a) -> dict:
    """path may end with #Sheet, #* (stack same-layout sheets) or #each (one dataset per sheet)."""
    sheet = None
    if "#" in path:
        path, sheet = path.rsplit("#", 1)
    if sheet == "each":
        return {d.name: d for d in load_each_sheet(path, name=name, pci_mode=a.pci, **_overrides(a, name))}
    return {name: load(path, name=name, sheet=sheet, pci_mode=a.pci, **_overrides(a, name))}


def cmd_inspect(a):
    for f in a.files:
        path = f.split("#")[0]
        if path.lower().endswith((".xlsx", ".xlsm", ".xls")):
            sheets = list_sheets(path)
            if len(sheets) > 1:
                print(f"\n{path}: sheets → " + ", ".join(f"{s['name']} ({s['rows']} rows{', hidden' if s['hidden'] else ''})" for s in sheets))
                print("   use file.xlsx#Sheet, file.xlsx#* (stack same layout) or file.xlsx#each (separate)")
        for ds in _load_spec(Path(path).stem, f, a).values():
            _print_dataset(ds)


def cmd_suggest(a):
    L = list(_load_spec(Path(a.left.split("#")[0]).stem, a.left, a).values())[0]
    R = list(_load_spec(Path(a.right.split("#")[0]).stem, a.right, a).values())[0]
    print(f"\nIdentifier candidates: {L.name} ⟷ {R.name}\n")
    for i, c in enumerate(discover(L, R, date_window_days=a.window), 1):
        print(f" {i}. score {c.score:.3f}  covers {c.cov_left:.0%} of {L.name} / {c.cov_right:.0%} of {R.name}\n    {c.describe()}")
        for ex in c.examples[:2]:
            print(f"      e.g. {ex[0]!r}  ⟷  {ex[1]!r}")


def _parse_files(items):
    out = {}
    for it in items:
        if "=" in it:
            name, path = it.split("=", 1)
        else:
            path = it
            name = Path(it).stem
        out[name] = path
    return out


def _interactive(cfg, cands, L, R):
    print(f"\n── {cfg.left} ⟷ {cfg.right}")
    for i, c in enumerate(cands, 1):
        print(f"  {i}. [{c.score:.2f}] {c.describe()}   ({c.cov_left:.0%} / {c.cov_right:.0%})")
    default = ",".join(str(cands.index(next(c for c in cands if c.left_col == k.left_col and c.right_col == k.right_col and c.mode == k.mode)) + 1)
                       for k in cfg.keys) if cfg.keys else ""
    ans = input(f"  keys to use, in priority order [{default}]: ").strip() or default
    keys = []
    for tok in [t for t in ans.split(",") if t.strip()]:
        c = cands[int(tok) - 1]
        if c.mode == "composite":
            cfg.use_composite = True
            continue
        keys.append(KeySpec(c.left_col, c.right_col, c.left_tf, c.right_tf, c.mode))
    cfg.keys = keys
    for side, ds in (("left", L), ("right", R)):
        for what in ("amount", "date"):
            cur = getattr(cfg, f"{side}_{what}")
            v = input(f"  {ds.name} {what} column [{cur}] (options: {', '.join(ds.columns)}): ").strip()
            if v:
                setattr(cfg, f"{side}_{what}", None if v == "-" else v)
    fee = input(f"  expected fee % deducted on the right side [{cfg.expected_fee_pct}]: ").strip()
    if fee:
        cfg.expected_fee_pct = float(fee)


def cmd_run(a):
    files = _parse_files(a.file)
    datasets = {}
    for n, p in files.items():
        datasets.update(_load_spec(n, p, a))
    for ds in datasets.values():
        _print_dataset(ds) if a.verbose else None
        for f in ds.findings:
            print(f"PCI  {ds.name}.{f.column}: {f.kind} → {f.action} ({f.count})" + (f"  [{_review_hint(ds, f)}]" if f.review else ""))
        for w in ds.warnings:
            print(f"WARN {ds.name}: {w}")
    if a.template:
        configs, expected = tpl.load(a.template)
        for w in tpl.check(datasets, expected):
            print("WARN", w)
        skipped = [c for c in configs if c.left not in datasets or c.right not in datasets]
        for c in skipped:
            print(f"SKIP pair {c.left} ⟷ {c.right}: file not provided")
        configs = [c for c in configs if c not in skipped]
    else:
        pairs = a.pair or ([f"{list(datasets)[0]}:{n}" for n in list(datasets)[1:]])
        fees = {}
        for f in a.fee or []:
            k, v = f.split("=")
            fees[k] = float(v)
        configs = []
        for pr in pairs:
            l, r = pr.split(":")
            cfg, cands = auto_config(datasets[l], datasets[r], date_window_days=a.window)
            cfg.expected_fee_pct = fees.get(pr, 0.0)
            cfg.amount_tol = a.tol
            if a.interactive:
                _interactive(cfg, cands, datasets[l], datasets[r])
            configs.append(cfg)
            print(f"\nPAIR {l} ⟷ {r}")
            for i, k in enumerate(cfg.keys, 1):
                print(f"  key{i}: {k.label()}")
            print(f"  amount: {cfg.left_amount} ⟷ {cfg.right_amount}   date: {cfg.left_date} ⟷ {cfg.right_date}  ±{cfg.date_window_days}d"
                  + (f"   fee {cfg.expected_fee_pct}%" if cfg.expected_fee_pct else ""))
    results, chain = run_all(datasets, configs)
    print()
    for k, r in results.items():
        s = r.summary
        print(f"RESULT {k}: {s['matched_groups']} matched, {s['exception_groups']} with variance; "
              f"{s['left_match_rate_pct']}% / {s['right_match_rate_pct']}% of rows reconciled; "
              f"exceptions {s['exceptions_by_category']}")
        for i in r.insights:
            print(f"   ▸ {i}")
    if chain is not None:
        print(f"CHAINS (anchor: {chain.anchor.iloc[0]}): {chain.status.value_counts().to_dict()}")
    out = a.out or "recon_report.xlsx"
    write_excel(out, datasets, results, chain)
    audit = audit_json(datasets, results)
    if a.explain:
        text = llm.explain(results, share_masked_samples=a.share_samples)
        audit["ai_commentary"] = text
        print("\nAI commentary:\n" + (text or "(set ANTHROPIC_API_KEY and pip install anthropic to enable)"))
    Path(a.audit or Path(out).with_suffix(".audit.json")).write_text(json.dumps(audit, indent=2, default=str))
    print(f"\nReport: {out}")
    if a.save_template:
        tpl.save(a.save_template, datasets, configs)
        print(f"Template saved: {a.save_template}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="anyrecon", description="Reconcile any set of documents.")
    p.add_argument("--version", action="version", version=__version__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--pci", choices=["strict", "paranoid", "block"], default="strict", help="card-data handling (default strict)")
    common.add_argument("--mask-col", action="append", help="name:column  mask a column the guard left as-is")
    common.add_argument("--keep-col", action="append", help="name:column  restore a suspected-CVV/PIN column you confirm is not card data")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("inspect", parents=[common], help="parse files, show PCI actions and column profiles")
    s.add_argument("files", nargs="+")
    s.set_defaults(fn=cmd_inspect)

    s = sub.add_parser("suggest", parents=[common], help="rank identifier candidates for a pair of files")
    s.add_argument("left")
    s.add_argument("right")
    s.add_argument("--window", type=int, default=3)
    s.set_defaults(fn=cmd_suggest)

    s = sub.add_parser("run", parents=[common], help="reconcile")
    s.add_argument("-f", "--file", action="append", required=True, help="name=path (repeat)")
    s.add_argument("-p", "--pair", action="append", help="left:right (repeat). Default: first file vs each other")
    s.add_argument("--fee", action="append", help="left:right=PCT expected fee deducted on the right side")
    s.add_argument("--window", type=int, default=3, help="date window in days (default 3)")
    s.add_argument("--tol", type=float, default=0.01, help="absolute amount tolerance (default 0.01)")
    s.add_argument("--template", help="reuse a saved setup")
    s.add_argument("--save-template", help="save this setup for next time")
    s.add_argument("-i", "--interactive", action="store_true", help="confirm keys/columns for each pair")
    s.add_argument("--out", help="Excel report path")
    s.add_argument("--audit", help="audit JSON path")
    s.add_argument("--explain", action="store_true", help="add AI commentary (needs ANTHROPIC_API_KEY)")
    s.add_argument("--share-samples", action="store_true", help="let --explain see up to 15 masked exception rows")
    s.add_argument("-v", "--verbose", action="store_true")
    s.set_defaults(fn=cmd_run)

    a = p.parse_args(argv)
    try:
        a.fn(a)
    except PCIBlocked as e:
        print(f"BLOCKED: {e}", file=sys.stderr)
        sys.exit(2)
    except UnreadableFile as e:
        print(f"CANNOT READ: {e}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
