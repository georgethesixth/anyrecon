"""End-to-end check of the built Browser edition, the way a visitor uses it.

Serves the built site locally with the same security headers as production (from vercel.json),
opens it in headless Chromium with every request to any other host blocked, uploads the synthetic
example files, confirms the proposed connections, and checks the results, the Excel download and
the Advanced view. Fails (exit code 1) on any page error, any attempt to reach another host, or
any part of the UI that failed to load.

    pip install playwright && python -m playwright install chromium
    python examples/generate_samples.py            # once: synthetic files in examples/data/
    python editions/browser/check.py               # checks web/
    python editions/browser/check.py --record-prefetch
        # also rewrites editions/browser/prefetch.txt: the UI pieces the page downloads in the
        # background (see build.py). Run this after upgrading stlite or using a new kind of widget,
        # then rebuild.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import json
import re
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = ["processor.csv", "ledger.xlsx", "bank_statement.pdf", "settlement_report.json"]


def serve(site: Path, port: int) -> http.server.ThreadingHTTPServer:
    cfg = json.loads((ROOT / "vercel.json").read_text())
    headers = [(h["key"], h["value"]) for h in cfg["headers"][0]["headers"]]

    class Handler(http.server.SimpleHTTPRequestHandler):
        def end_headers(self):
            for k, v in headers:
                self.send_header(k, v)
            super().end_headers()

        def log_message(self, *a):
            pass

    Handler.extensions_map.update({".mjs": "text/javascript", ".wasm": "application/wasm", ".whl": "application/zip"})
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(Handler, directory=str(site)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default=str(ROOT / "web"))
    ap.add_argument("--data", default=str(ROOT / "examples" / "data"))
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--record-prefetch", action="store_true")
    a = ap.parse_args()
    data = Path(a.data)
    missing = [f for f in FILES if not (data / f).exists()]
    if missing:
        print(f"missing example files: {missing}. Run: python examples/generate_samples.py")
        return 1
    from playwright.sync_api import sync_playwright

    srv = serve(Path(a.site), a.port)
    base = f"http://127.0.0.1:{a.port}"
    external, errors, chunks = [], [], set()
    problems = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1400, "height": 900}, accept_downloads=True)
        ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base) else (external.append(r.request.url), r.abort()))
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)[:300]))
        pg.on("request", lambda r: chunks.add(r.url.split("/stlite/")[1]) if "/stlite/" in r.url and r.url.endswith(".js") else None)
        t0 = time.time()
        pg.goto(base + "/")
        pg.wait_for_selector("#landing .ar-hero", timeout=15000)
        print(f"landing visible after {time.time() - t0:.1f}s")
        boot = set(chunks)
        pg.locator('#landing [data-go="start"]').click()
        pg.wait_for_selector('[data-testid="stFileUploaderDropzoneInput"]', state="attached", timeout=400000)
        print(f"app ready after {time.time() - t0:.0f}s")
        pg.set_input_files('[data-testid="stFileUploaderDropzoneInput"]', [str(data / f) for f in FILES])
        pg.wait_for_selector("text=Confirm and reconcile", timeout=400000)
        pg.wait_for_timeout(1500)
        print(f"connections proposed after {time.time() - t0:.0f}s")
        pg.get_by_role("button", name="Preview").first.click()
        pg.wait_for_timeout(1500)
        pg.keyboard.press("Escape")
        pg.get_by_role("button", name="Change").first.click()
        pg.wait_for_timeout(2500)
        pg.get_by_role("button", name="Done").first.click()
        pg.wait_for_timeout(1500)
        pg.get_by_role("button", name="Confirm and reconcile").click()
        pg.wait_for_selector("text=Matched groups", timeout=400000)
        pg.wait_for_timeout(2500)
        body = pg.inner_text("body")
        summary = re.search(r"([\d,]+) matched · ([\d,]+) exception", body)
        print(f"results after {time.time() - t0:.0f}s: " + (f"{summary.group(1)} matched, {summary.group(2)} exceptions" if summary else "?"))
        if not re.search(r"[1-9][\d,]* matched", body):
            problems.append("no matches in results")
        with pg.expect_download(timeout=60000) as dl:
            pg.get_by_role("button", name="Excel report").click()
        path = Path("/tmp") / dl.value.suggested_filename
        dl.value.save_as(path)
        import openpyxl
        sheets = openpyxl.load_workbook(path).sheetnames
        print(f"Excel report: {len(sheets)} sheets ({', '.join(sheets[:3])}, …)")
        tab = pg.get_by_role("tab", name="All documents")
        if tab.count():
            tab.click()
            pg.wait_for_timeout(2500)
        pg.get_by_text("Advanced").first.click()
        pg.wait_for_timeout(8000)
        body = pg.inner_text("body")
        if "Failed to fetch dynamically imported module" in body:
            problems.append("part of the UI failed to load")
        browser.close()
    srv.shutdown()

    if external:
        problems.append(f"page tried to reach other hosts: {sorted(set(external))[:5]}")
    if errors:
        problems.append(f"page errors: {errors[:3]}")
    if a.record_prefetch:
        used = sorted(chunks - boot - {"stlite.js"})
        (Path(__file__).parent / "prefetch.txt").write_text("\n".join(used) + "\n")
        print(f"wrote prefetch.txt: {len(used)} files. Rebuild to apply.")
    for pr in problems:
        print("FAIL:", pr)
    print("OK" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
