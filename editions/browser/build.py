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


# One calm loading screen in the Monogram style. It covers stlite's own boot steps and fades out
# only once the app has drawn its first screen (the app marks it with the class "ar-ready").
BOOT_CSS = """
@font-face{font-family:"Cormorant Garamond";font-style:normal;font-weight:400;font-display:swap;src:url("fonts/cormorant-garamond-latin-400-normal.woff2") format("woff2")}
@font-face{font-family:"Cormorant Garamond";font-style:italic;font-weight:400;font-display:swap;src:url("fonts/cormorant-garamond-latin-400-italic.woff2") format("woff2")}
@font-face{font-family:"Cormorant Garamond";font-style:normal;font-weight:500;font-display:swap;src:url("fonts/cormorant-garamond-latin-500-normal.woff2") format("woff2")}
@font-face{font-family:"Cormorant Garamond";font-style:italic;font-weight:500;font-display:swap;src:url("fonts/cormorant-garamond-latin-500-italic.woff2") format("woff2")}
@font-face{font-family:"Geist";font-style:normal;font-weight:300;font-display:swap;src:url("fonts/geist-sans-latin-300-normal.woff2") format("woff2")}
@font-face{font-family:"Geist";font-style:normal;font-weight:400;font-display:swap;src:url("fonts/geist-sans-latin-400-normal.woff2") format("woff2")}
@font-face{font-family:"Geist";font-style:normal;font-weight:500;font-display:swap;src:url("fonts/geist-sans-latin-500-normal.woff2") format("woff2")}
html,body{margin:0;background:#F2F0EA}
#loader{position:fixed;inset:0;z-index:2147483647;background:#F2F0EA;color:#25231F;display:flex;flex-direction:column;align-items:center;justify-content:center;
  text-align:center;padding:24px;font-family:"Geist",system-ui,-apple-system,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased;transition:opacity .6s ease}
#loader.gone{opacity:0;pointer-events:none}
.ld-mark{width:112px;height:112px;border-radius:50%;border:1px solid #B9B3A7;display:grid;place-items:center;font-family:"Cormorant Garamond",Georgia,serif;
  font-size:42px;color:#3A372F;animation:breathe 3.2s ease-in-out infinite}
.ld-mark i{font-style:italic}
.ld-name{margin-top:34px;font-size:13px;letter-spacing:.32em;text-transform:uppercase;font-weight:500}
.ld-msg{margin-top:14px;font-family:"Cormorant Garamond",Georgia,serif;font-style:italic;font-size:22px;color:#7A7468;min-height:1.4em;transition:opacity .4s ease}
.ld-msg.out{opacity:0}
.ld-track{width:180px;height:1px;background:#DDD8CD;margin-top:30px;overflow:hidden}
.ld-track span{display:block;height:100%;width:0;background:#25231F;transition:width .3s linear}
.ld-sub{margin-top:28px;font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:#A39D90;max-width:30em;line-height:1.8}
@keyframes breathe{0%,100%{opacity:1}50%{opacity:.55}}
@media (prefers-reduced-motion:reduce){.ld-mark{animation:none}#loader,.ld-msg{transition:none}}
"""

BOOT_LOADER_JS = r"""
(() => {
  const ov = document.getElementById("loader"), bar = document.getElementById("ldbar"), msg = document.getElementById("ldmsg");
  if (!ov) return;
  const steps = ["Preparing the engine in your browser", "Loading the matching engine", "Setting up the document readers", "Almost ready"];
  const t0 = performance.now(); let i = 0, done = false;
  const tick = () => { if (done) return; const s = (performance.now() - t0) / 1000; bar.style.width = (92 * (1 - Math.exp(-s / 20))) + "%"; requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
  const rotate = setInterval(() => {
    if (i >= steps.length - 1) return; i++;
    msg.classList.add("out"); setTimeout(() => { msg.textContent = steps[i]; msg.classList.remove("out"); }, 400);
  }, 8000);
  const finish = () => {
    if (done) return; done = true; clearInterval(rotate); bar.style.width = "100%";
    setTimeout(() => { ov.classList.add("gone"); setTimeout(() => ov.remove(), 700); }, 400);
  };
  const ready = () => document.querySelector("#root .ar-ready");
  const obs = new MutationObserver(() => { if (ready()) { obs.disconnect(); setTimeout(finish, 250); } });
  obs.observe(document.getElementById("root"), { childList: true, subtree: true });
  setTimeout(finish, 180000);  // never trap the visitor behind the loader
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
    shutil.copytree(ROOT / "static" / "fonts", out / "fonts")

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
                            "theme.base": "light", "theme.primaryColor": "#3A372F", "theme.backgroundColor": "#F2F0EA",
                            "theme.secondaryBackgroundColor": "#ECE8DF", "theme.textColor": "#25231F", "theme.font": "sans serif"},
    }
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="referrer" content="no-referrer">
<meta name="description" content="Reconcile any set of documents, in your browser. Files are never uploaded.">
<meta name="theme-color" content="#F2F0EA">
<title>anyrecon</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Ccircle cx='32' cy='32' r='30' fill='%23F2F0EA' stroke='%2325231F' stroke-width='2'/%3E%3Ctext x='32' y='41' font-family='Georgia,serif' font-size='26' text-anchor='middle' fill='%2325231F'%3Ear%3C/text%3E%3C/svg%3E">
<link rel="preload" href="./fonts/cormorant-garamond-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="./fonts/geist-sans-latin-500-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="./boot.css">
<link rel="stylesheet" href="./stlite/stlite.css">
</head>
<body>
<div id="loader" role="status" aria-live="polite">
  <div class="ld-mark"><span>a<i>r</i></span></div>
  <div class="ld-name">anyrecon</div>
  <div class="ld-msg" id="ldmsg">Preparing the engine in your browser</div>
  <div class="ld-track"><span id="ldbar"></span></div>
  <div class="ld-sub">The first visit takes about a minute. Your files never leave this tab.</div>
</div>
<div id="root"></div>
<script type="module" src="./boot.js"></script>
</body>
</html>
"""
    (out / "boot.css").write_text(BOOT_CSS, encoding="utf-8")
    (out / "index.html").write_text(html, encoding="utf-8")
    # external file: the security policy forbids inline scripts
    # Paths are made absolute at load time: the Python worker runs from a blob: URL, where "./x" resolves to nothing.
    (out / "boot.js").write_text(
        'import { mount } from "./stlite/stlite.js";\n'
        'const base = new URL(".", import.meta.url).href;\n'
        'const abs = (v) => typeof v === "string" && v.startsWith("./") ? new URL(v, base).href\n'
        '  : Array.isArray(v) ? v.map(abs) : (v && typeof v === "object") ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, abs(x)])) : v;\n'
        f'const options = {json.dumps(opts, indent=1)};\n'
        + BOOT_LOADER_JS +
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
