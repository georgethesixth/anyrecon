"""Build the Browser edition: a static website that runs anyrecon entirely in the visitor's browser.

Every file the page needs (the app, the Python runtime, all packages) is copied into one folder and
served from your own domain. Nothing is loaded from third-party CDNs and nothing is fetched from PyPI
at run time, so it works behind corporate proxies and the page never needs to talk to anyone else.

    python editions/browser/build.py                   # -> editions/browser/site/
    python editions/browser/build.py --pyodide-dir /path/to/pyodide-314.0.3/pyodide   # offline build

Then upload the contents of site/ to any static host (kemdi.co, GitHub Pages, Netlify, an intranet server).
Build machine needs: Python 3.10+, npm, internet (or --pyodide-dir), and reportlab for the sample files.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

STLITE_VERSION = "1.12.0"
PYODIDE_VERSION = "314.0.3"          # must match the stlite release above
PYODIDE_CDN = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/"
PYODIDE_CORE = ["pyodide.mjs", "pyodide.js", "pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"]

# Packages taken from the Pyodide distribution (dependencies are added automatically).
PYODIDE_PACKAGES = ["micropip", "packaging", "numpy", "pandas", "pyarrow", "pillow", "protobuf", "altair", "typing-extensions",
                    "starlette", "anyio", "pyodide-http", "python-dateutil", "pytz", "six", "charset-normalizer", "cryptography",
                    "ssl", "pyodide-unix-timezones"]
# Pure-Python wheels not in Pyodide, bundled from PyPI at build time.
PURE_WHEELS = ["python-multipart", "itsdangerous", "openpyxl", "et-xmlfile", "pdfminer.six"]
NO_DEPS_WHEELS = ["pdfplumber"]      # its pypdfium2 dependency is only used for page images, which the browser edition doesn't need

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"

# connect-src 'self': the page and its Python worker can only talk to the site they came from. Downloads are
# produced inside the page, so they still work; stlite's pre-check pings to its internal stlite.invalid address
# are refused (harmless console notices) instead of leaving the browser.
CSP = ("default-src 'self'; script-src 'self' blob: data: 'wasm-unsafe-eval' 'unsafe-eval'; worker-src 'self' blob: data:; "
       "connect-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; font-src 'self' data:; "
       "object-src 'none'; base-uri 'none'; form-action 'none'")


# The landing page is plain HTML shown immediately; the Python engine starts underneath it.
# Visitors read the page while it loads. If they click before it's ready, the button says so and
# carries on by itself once the app has drawn its first screen (marked with the class "ar-ready").
LANDING_CSS = """
html,body{margin:0;background:#fff}
html.landing body{overflow:hidden}
#landing{position:fixed;inset:0;z-index:2147483646;overflow-y:auto;background:#fff;color:var(--ink);font-family:var(--font);
  -webkit-font-smoothing:antialiased;transition:opacity .2s ease}
#landing.gone{opacity:0;pointer-events:none}
.ar-status{display:inline-flex;align-items:center;gap:7px;font-size:13px;color:var(--muted);padding:5px 10px;border:1px solid var(--line);border-radius:999px;white-space:nowrap}
.ar-status em{font-style:normal}
.ar-status i{width:7px;height:7px;border-radius:50%;background:#D9A23A;animation:arpulse 1.4s ease-in-out infinite}
.ar-status.ok i{background:var(--ok);animation:none}
.ar-btn .spin{width:14px;height:14px;box-sizing:border-box;margin:-2px 0;border-radius:50%;border:2px solid currentColor;border-right-color:transparent;animation:arspin .8s linear infinite}
@keyframes arpulse{50%{opacity:.35}}
@keyframes arspin{to{transform:rotate(360deg)}}
@media (prefers-reduced-motion:reduce){.ar-status i,.ar-btn .spin{animation:none}#landing{transition:none}}
"""

LANDING_JS = r"""
(() => {
  const land = document.getElementById("landing"), root = document.getElementById("root"), st = document.getElementById("arStatus");
  if (!land) return;
  let ready = false, pending = null;
  const status = (cls, text) => { if (st) { st.className = "ar-status " + cls; st.querySelector("em").textContent = text; } };
  const enter = (go) => {
    document.documentElement.classList.remove("landing");
    land.classList.add("gone"); setTimeout(() => { land.hidden = true; }, 250); window.scrollTo(0, 0);
    if (go === "sample") {   // press the app's own sample button
      const t0 = Date.now(), iv = setInterval(() => {
        const b = root.querySelector(".st-key-try2 button");
        if (b) { clearInterval(iv); b.click(); } else if (Date.now() - t0 > 20000) clearInterval(iv);
      }, 150);
    }
  };
  land.addEventListener("click", (e) => {
    const b = e.target.closest("[data-go]"); if (!b) return;
    if (ready) return enter(b.dataset.go);
    pending = b.dataset.go;
    land.querySelectorAll("[data-go]").forEach((x) => { x.disabled = true; });
    b.innerHTML = '<span class="spin"></span>Getting ready…';
  });
  const slow = setTimeout(() => { if (!ready) status("", "Preparing engine (first visit is slower)"); }, 25000);
  const obs = new MutationObserver(() => {
    if (!root.querySelector(".ar-ready")) return;
    obs.disconnect(); clearTimeout(slow); ready = true; status("ok", "Ready");
    if (pending) enter(pending);
  });
  obs.observe(root, { childList: true, subtree: true });
})();
"""


def log(msg):
    print(f"[browser] {msg}", flush=True)


def get_stlite() -> Path:
    dest = CACHE / f"stlite-{STLITE_VERSION}"
    if not (dest / "package" / "build" / "stlite.js").exists():
        dest.mkdir(parents=True, exist_ok=True)
        log(f"downloading @stlite/browser {STLITE_VERSION} (npm)")
        out = subprocess.run(["npm", "pack", f"@stlite/browser@{STLITE_VERSION}"], cwd=dest, check=True,
                             capture_output=True, text=True).stdout.strip().splitlines()[-1]
        with tarfile.open(dest / out) as t:
            t.extractall(dest, filter="data")
    return dest / "package" / "build"


def pyodide_file(name: str, src_dir: Path | None, out: Path):
    target = out / name
    if target.exists():
        return
    if src_dir:
        shutil.copy2(src_dir / name, target)
    else:
        cached = CACHE / f"pyodide-{PYODIDE_VERSION}" / name
        if not cached.exists():
            cached.parent.mkdir(parents=True, exist_ok=True)
            log(f"downloading {name}")
            urllib.request.urlretrieve(PYODIDE_CDN + name, cached)
        shutil.copy2(cached, target)


def closure(lock: dict, names: list[str]) -> list[str]:
    norm = lambda n: n.lower().replace("_", "-").replace(".", "-")
    pk = {norm(k): k for k in lock["packages"]}
    seen, stack = set(), [norm(n) for n in names]
    while stack:
        n = stack.pop()
        if n in seen or n not in pk:
            continue
        seen.add(n)
        stack.extend(norm(d) for d in lock["packages"][pk[n]]["depends"])
    return sorted(pk[n] for n in seen)


def pip_download(names: list[str], out: Path) -> list[str]:
    before = {p.name for p in out.glob("*.whl")}
    subprocess.run([sys.executable, "-m", "pip", "download", "--no-deps", "--only-binary=:all:", "--python-version", "3.14",
                    "--platform", "any", "-d", str(out), *names], check=True, capture_output=True)
    files = sorted(p.name for p in out.glob("*.whl"))
    return [f for f in files if f not in before] or files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pyodide-dir", type=Path, help="local Pyodide full distribution (offline build)")
    ap.add_argument("--out", type=Path, default=HERE / "site")
    a = ap.parse_args()
    out: Path = a.out
    if out.exists():
        shutil.rmtree(out)
    (out / "pyodide").mkdir(parents=True)
    (out / "wheels").mkdir()

    # 1. stlite (the in-browser Streamlit), without source maps
    stl = get_stlite()
    shutil.copytree(stl, out / "stlite", ignore=shutil.ignore_patterns("*.map", "*.d.ts"))
    log("stlite copied")

    # 2. Pyodide runtime + only the packages we use
    for f in PYODIDE_CORE:
        pyodide_file(f, a.pyodide_dir, out / "pyodide")
    lock = json.loads((out / "pyodide" / "pyodide-lock.json").read_text())
    pkgs = closure(lock, PYODIDE_PACKAGES)
    for n in pkgs:
        pyodide_file(lock["packages"][n]["file_name"], a.pyodide_dir, out / "pyodide")
    log(f"pyodide runtime + {len(pkgs)} packages")

    # 3. Pure-Python wheels from PyPI
    pure = pip_download(PURE_WHEELS, out / "wheels")
    nodeps = [f for f in pip_download(NO_DEPS_WHEELS, out / "wheels") if f.startswith("pdfplumber")]
    log(f"wheels: {', '.join(pure + nodeps)}")

    # 4. The app itself + synthetic sample data
    files = {}
    for p in sorted((ROOT / "anyrecon").glob("*.py")):
        files[f"anyrecon/{p.name}"] = p
    files["app.py"] = ROOT / "app.py"
    files["ui_theme.py"] = ROOT / "ui_theme.py"
    files["examples/__init__.py"] = ROOT / "examples" / "__init__.py"
    files["examples/generate_samples.py"] = ROOT / "examples" / "generate_samples.py"
    samples = ROOT / "examples" / "data"
    if not (samples / "processor.csv").exists():
        subprocess.run([sys.executable, str(ROOT / "examples" / "generate_samples.py")], check=True)
    for f in ["processor.csv", "ledger.xlsx", "bank_statement.pdf", "settlement_report.json"]:
        files[f"examples/data/{f}"] = samples / f
    for w in nodeps:   # pure-Python, imported straight from the wheel (zip) at start-up: see app.py
        files[f"wheels/{w}"] = out / "wheels" / w
    for rel, src in files.items():
        dst = out / "app" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    log(f"{len(files)} app files")

    # 5. Page
    stl_files = {rel: {"url": f"./app/{rel}"} for rel in files}
    streamlit_whl = next((stl / "wheels").glob("streamlit-*.whl")).name
    stlite_whl = next((stl / "wheels").glob("stlite_lib-*.whl")).name
    opts = {
        "entrypoint": "app.py",
        "files": stl_files,
        "pyodideUrl": "./pyodide/pyodide.mjs",
        "requirements": [f"./wheels/{w}" for w in pure],
        "wheelUrls": {"streamlit": f"./stlite/wheels/{streamlit_whl}", "stliteLib": f"./stlite/wheels/{stlite_whl}"},
        "streamlitConfig": {"client.toolbarMode": "minimal", "browser.gatherUsageStats": False,
                            "theme.base": "light", "theme.primaryColor": "#2457D6", "theme.backgroundColor": "#FFFFFF",
                            "theme.secondaryBackgroundColor": "#F5F6F8", "theme.textColor": "#14171F", "theme.font": "sans serif"},
    }
    sys.path.insert(0, str(ROOT))
    import ui_theme as ui
    version = re.search(r'__version__\s*=\s*"([^"]+)"', (ROOT / "anyrecon" / "__init__.py").read_text()).group(1)
    landing = ui.landing_page("Browser", version, browser=True)
    html = f"""<!doctype html>
<html lang="en" class="landing">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="referrer" content="no-referrer">
<meta name="description" content="Reconcile any set of documents, in your browser. Files are never uploaded.">
<meta name="theme-color" content="#FFFFFF">
<title>anyrecon</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='16' fill='%232457D6'/%3E%3Ctext x='32' y='42' font-family='Arial,sans-serif' font-weight='700' font-size='28' text-anchor='middle' fill='%23fff'%3Ear%3C/text%3E%3C/svg%3E">
<link rel="stylesheet" href="./boot.css">
<link rel="stylesheet" href="./stlite/stlite.css">
</head>
<body>
<div id="landing">{landing}</div>
<div id="root"></div>
<script type="module" src="./boot.js"></script>
</body>
</html>
"""
    (out / "boot.css").write_text(ui.BASE_CSS + LANDING_CSS, encoding="utf-8")
    (out / "index.html").write_text(html, encoding="utf-8")
    # external file: the security policy forbids inline scripts
    # Paths are made absolute at load time: the Python worker runs from a blob: URL, where "./x" resolves to nothing.
    (out / "boot.js").write_text(
        'import { mount } from "./stlite/stlite.js";\n'
        'const base = new URL(".", import.meta.url).href;\n'
        'const abs = (v) => typeof v === "string" && v.startsWith("./") ? new URL(v, base).href\n'
        '  : Array.isArray(v) ? v.map(abs) : (v && typeof v === "object") ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, abs(x)])) : v;\n'
        f'const options = {json.dumps(opts, indent=1)};\n'
        + LANDING_JS +
        'mount(abs(options), document.getElementById("root"));\n', encoding="utf-8")
    # Response headers for hosts that support them (Netlify / Cloudflare Pages). These also cover the
    # Python worker, which a <meta> CSP does not reach.
    (out / "_headers").write_text("/*\n"
                                  f"  Content-Security-Policy: {CSP}\n"
                                  "  Referrer-Policy: no-referrer\n"
                                  "  X-Content-Type-Options: nosniff\n"
                                  "  Cross-Origin-Opener-Policy: same-origin\n")
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file()) / 1e6
    log(f"done: {out}  ({size:.0f} MB)")


if __name__ == "__main__":
    main()
