"""How much data can anyrecon handle, and how fast?

Generates realistic synthetic files at increasing sizes (a processor export, a ledger and a bank statement,
the bank with references buried in narrations and a 1.5% fee deducted, a few percent of breaks on each
side), then times the same steps the app runs: read, find connections, match, write the Excel report.

    python scripts/benchmark.py                       # this computer (the download version)
    python scripts/benchmark.py --rows 10000 50000    # chosen sizes
    python scripts/benchmark.py --browser             # the web app, in headless Chromium (needs web/ built
                                                      #  and: pip install playwright && playwright install chromium)

Numbers depend on the machine; the guide quotes results from a typical laptop-class machine.
"""
from __future__ import annotations

import argparse
import random
import resource
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def make_files(n: int, folder: Path, seed: int = 7) -> list[Path]:
    """processor (n rows), ledger (~98% of them, ID with prefix), bank (~98%, ID in narration, net of 1.5% fee)."""
    rnd = random.Random(seed)
    start = date(2026, 1, 1)
    proc, led, bank = [], [], []
    for i in range(n):
        rrn = f"{rnd.randrange(10**11, 10**12):012d}"
        amt = round(rnd.uniform(500, 250_000), 2)
        d = start + timedelta(days=rnd.randrange(0, 90))
        proc.append(f"TX{i:09d},{rrn},{amt:.2f},{d:%d/%m/%Y},MERCHANT {rnd.randrange(1, 400)}")
        if rnd.random() > 0.02:
            led.append(f"NX-{rrn.lstrip('0')},{amt + (100 if rnd.random() < 0.005 else 0):.2f},{d:%d/%m/%Y}")
        if rnd.random() > 0.02:
            net = round(amt * 0.985, 2)
            bank.append(f"{d + timedelta(days=1):%d/%m/%Y},POS SETTL/{rrn}/MERCHANT {rnd.randrange(1, 400)},{net:.2f}")
    for _ in range(max(1, n // 100)):   # bank items with no counterpart
        bank.append(f"{start + timedelta(days=rnd.randrange(0, 90)):%d/%m/%Y},TRANSFER FROM CUSTOMER,{rnd.uniform(100, 9000):.2f}")
    files = {
        "processor.csv": "Transaction ID,RRN,Amount,Transaction Date,Merchant\n" + "\n".join(proc),
        "ledger.csv": "Txn Reference,Gross Amount,Posting Date\n" + "\n".join(led),
        "bank.csv": "Value Date,Narration,Credit\n" + "\n".join(bank),
    }
    out = []
    for name, text in files.items():
        p = folder / name
        p.write_text(text + "\n", encoding="utf-8")
        out.append(p)
    return out


def run_native(files: list[Path]) -> dict:
    """The same steps the app runs, in-process."""
    from itertools import combinations
    from anyrecon.chain import auto_config, auto_pairs, run_all
    from anyrecon.discover import discover
    from anyrecon.ingest import load
    from anyrecon.report import write_excel
    t = {}
    t0 = time.perf_counter()
    ds = {p.stem: load(p, name=p.stem) for p in files}
    t["read"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    cmap = {(a, b): discover(ds[a], ds[b]) for a, b in combinations(ds, 2)}
    pairs = auto_pairs(ds, cmap)
    cfgs = [auto_config(ds[a], ds[b], candidates=cmap[(a, b)])[0] for a, b in pairs]
    t["connect"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    results, chain = run_all(ds, cfgs, auto_fee=True)
    t["match"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    with tempfile.NamedTemporaryFile(suffix=".xlsx") as fh:
        write_excel(fh.name, ds, results, chain)
    t["report"] = time.perf_counter() - t0
    t["matched"] = sum(r.summary["matched_groups"] for r in results.values())
    return t


def run_browser(files: list[Path], timeout_s: int = 1800) -> dict:
    sys.path.insert(0, str(ROOT / "browser"))
    from check import serve
    from playwright.sync_api import sync_playwright
    srv = serve(ROOT / "web", 8790)
    out = {}
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1300, "height": 900})
            crashed = []
            pg.on("crash", lambda *_: crashed.append(True))
            pg.goto("http://127.0.0.1:8790/")
            pg.wait_for_selector("#arStatus.ok", timeout=400_000)
            pg.locator('#landing [data-go="start"]').click()
            pg.wait_for_selector('[data-testid="stFileUploaderDropzoneInput"]', state="attached", timeout=120_000)
            t0 = time.perf_counter()
            pg.set_input_files('[data-testid="stFileUploaderDropzoneInput"]', [str(f) for f in files])
            pg.wait_for_selector("text=Confirm and reconcile", timeout=timeout_s * 1000)
            out["to_connections"] = time.perf_counter() - t0
            t1 = time.perf_counter()
            pg.get_by_role("button", name="Confirm and reconcile").click()
            pg.wait_for_selector("text=Matched groups", timeout=timeout_s * 1000)
            out["to_results"] = time.perf_counter() - t1
            out["total"] = time.perf_counter() - t0
            mem = pg.evaluate("performance.memory ? performance.memory.usedJSHeapSize : null")
            out["js_heap_mb"] = round(mem / 1e6) if mem else None
            b.close()
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {str(e)[:120]}"
    finally:
        srv.shutdown()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, nargs="*", default=[10_000, 50_000, 100_000, 250_000, 500_000, 1_000_000])
    ap.add_argument("--browser", action="store_true")
    a = ap.parse_args()
    for n in a.rows:
        with tempfile.TemporaryDirectory() as tmp:
            files = make_files(n, Path(tmp))
            mb = sum(f.stat().st_size for f in files) / 1e6
            if a.browser:
                r = run_browser(files)
                print(f"{n:>9,} rows/file  {mb:7.1f} MB  browser: " + ", ".join(
                    f"{k} {v:.0f}s" if isinstance(v, float) else f"{k} {v}" for k, v in r.items()), flush=True)
            else:
                r = run_native(files)
                peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
                print(f"{n:>9,} rows/file  {mb:7.1f} MB  read {r['read']:.1f}s  connect {r['connect']:.1f}s  "
                      f"match {r['match']:.1f}s  report {r['report']:.1f}s  total "
                      f"{r['read'] + r['connect'] + r['match'] + r['report']:.0f}s  peak RAM {peak:,.0f} MB  "
                      f"matched {r['matched']:,}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
