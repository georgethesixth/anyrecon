"""Build anyrecon: a static website that runs entirely in the visitor's browser, installable as an app.

Every file the page needs (the app, the Python runtime, all packages) is copied into one folder and
served from your own domain. Nothing is loaded from third-party CDNs and nothing is fetched from PyPI
at run time, so it works behind corporate proxies and the page never needs to talk to anyone else.

    python browser/build.py && rm web/_headers      # -> web/ (served by Vercel; vercel.json sets the headers)
    python browser/build.py --pyodide-dir /path/to/pyodide-314.0.3/pyodide   # offline build

Any static host works: upload the contents of the output folder (GitHub Pages, Netlify, an intranet server).
Build machine needs: Python 3.10+, npm, internet (or --pyodide-dir), and the `markdown` package (renders the guide).
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
PURE_WHEELS = ["python-multipart", "itsdangerous", "openpyxl", "et-xmlfile", "pdfminer.six", "xlsxwriter"]
NO_DEPS_WHEELS = ["pdfplumber"]      # its pypdfium2 dependency is only used for page images, which the browser edition doesn't need

ROOT = Path(__file__).resolve().parents[1]
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
.ar-oops{position:fixed;left:50%;bottom:20px;transform:translateX(-50%);z-index:2147483647;background:#14171F;color:#fff;font:14px/1.4 var(--font);
  padding:12px 14px 12px 18px;border-radius:10px;display:flex;gap:12px;align-items:center;flex-wrap:wrap;max-width:min(680px,92vw);box-shadow:0 8px 30px rgba(0,0,0,.2)}
.ar-oops button{background:var(--accent);color:#fff;border:0;border-radius:7px;padding:7px 12px;font:600 14px var(--font);cursor:pointer}
.ar-oops span{color:#B8BDC7;font-size:13px}
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
  };
  land.addEventListener("click", (e) => {
    const b = e.target.closest("[data-go]"); if (!b) return;
    if (ready) return enter(b.dataset.go);
    pending = b.dataset.go;
    land.querySelectorAll("[data-go]").forEach((x) => { x.disabled = true; });
    b.innerHTML = '<span class="spin"></span>Getting ready…';
  });
  // Pre-select the visitor's system in "Run it on your computer".
  try {
    const plat = ((navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || navigator.userAgent || "").toLowerCase();
    const os = /mac|iphone|ipad/.test(plat) ? "mac" : (/linux|x11/.test(plat) && !/android/.test(plat)) ? "linux" : "win";
    const r = document.getElementById("os-" + os); if (r) r.checked = true;
  } catch (e) {}
  const slow = setTimeout(() => { if (!ready) status("", "Preparing engine (first visit is slower)"); }, 25000);
  const obs = new MutationObserver(() => {
    if (!root.querySelector(".ar-ready")) return;
    obs.disconnect(); clearTimeout(slow); ready = true; status("ok", "Ready");
    if (pending) enter(pending);
  });
  obs.observe(root, { childList: true, subtree: true });
})();

// Fetch the UI pieces the app will need (figures, download buttons, tables...) while the visitor reads,
// with retries, so nothing has to be downloaded at the moment results appear on a slow or flaky line.
(() => {
  const list = PREFETCH, base = new URL("./stlite/", import.meta.url).href;
  const get = async (f) => { for (let i = 0; i < 4; i++) { try { const r = await fetch(base + f); if (r.ok) { await r.arrayBuffer(); return; } } catch (e) {} await new Promise((s) => setTimeout(s, 1500 * (i + 1))); } };
  setTimeout(async () => { const q = list.slice(); const run = async () => { while (q.length) await get(q.shift()); }; await Promise.all([run(), run(), run()]); }, 1500);
})();

// If a piece still fails to load, say so plainly instead of leaving red boxes.
(() => {
  const root = document.getElementById("root"); let shown = false;
  new MutationObserver(() => {
    if (shown || !root.innerText || !root.innerText.includes("Failed to fetch dynamically imported module")) return;
    shown = true;
    const bar = document.createElement("div"); bar.className = "ar-oops";
    bar.innerHTML = 'Part of the page didn\'t load because the connection dropped for a moment. <button>Reload</button><span>You\'ll need to add your files again.</span>';
    bar.querySelector("button").onclick = () => location.reload();
    document.body.appendChild(bar);
  }).observe(root, { childList: true, subtree: true });
})();
"""


GUIDE_CSS = """
.g-body{max-width:820px;margin:0 auto;padding:8px 24px 40px;color:var(--ink);font:16px/1.65 var(--font);-webkit-font-smoothing:antialiased}
.g-body h1{font-size:34px;letter-spacing:-.02em;line-height:1.15;margin:40px 0 12px}
.g-body h2{font-size:24px;letter-spacing:-.01em;margin:48px 0 10px;padding-top:20px;border-top:1px solid var(--line)}
.g-body h3{font-size:18px;margin:30px 0 8px}
.g-body p,.g-body li{color:var(--ink2)}
.g-body a{color:var(--accent)}
.g-body code{font:13.5px var(--mono);background:var(--well);border-radius:5px;padding:1px 5px}
.g-body pre{background:#0F1218;color:#E6E8EC;border-radius:10px;padding:14px 16px;overflow-x:auto;font:13px/1.55 var(--mono)}
.g-body pre code{background:none;padding:0;color:inherit}
.g-body table{width:100%;border-collapse:collapse;margin:14px 0 20px;font-size:14.5px;display:block;overflow-x:auto}
.g-body th,.g-body td{border-bottom:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}
.g-body th{background:var(--well);font-weight:600}
.g-body hr{border:0;border-top:1px solid var(--line);margin:28px 0}
.g-body blockquote{margin:16px 0;padding:4px 16px;border-left:3px solid var(--accent);background:var(--accent-soft);border-radius:0 8px 8px 0}
.g-edit{font-size:14px;color:var(--muted);margin-top:40px}
html{scroll-behavior:smooth}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
"""


def _doc(out: Path, ui, src: Path, name: str, title: str, description: str) -> None:
    """Render a markdown file to <name>.html, styled like the app, with no scripts."""
    import markdown
    body = markdown.markdown(src.read_text(encoding="utf-8"), extensions=["tables", "fenced_code", "toc"], output_format="html")
    rel = src.relative_to(ROOT).as_posix()
    nav = (f'<nav class="ar-nav"><a class="ar-logo" href="./"><b>ar</b>anyrecon</a><div class="ar-navlinks">'
           f'<a href="./">Open anyrecon</a><a href="./guide.html">Guide</a><a href="./changelog.html">What\'s new</a>'
           f'<a href="{ui.REPO}" target="_blank" rel="noopener">GitHub</a></div></nav>')
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="referrer" content="no-referrer">
<meta name="description" content="{description}">
<title>anyrecon · {title}</title>
<link rel="icon" href="./favicon-32.png" type="image/png">
<link rel="manifest" href="./manifest.webmanifest">
<link rel="stylesheet" href="./guide.css">
</head>
<body>
<div class="ar-wrap">{nav}</div>
<main class="g-body">{body}
<p class="g-edit">This page is generated from <a href="{ui.REPO}/blob/main/{rel}" target="_blank" rel="noopener">{rel}</a>.
Found something wrong or out of date? <a href="{ui.REPO}/edit/main/{rel}" target="_blank" rel="noopener">Edit it on GitHub</a>.</p>
</main>
<div class="ar-wrap">{ui.footer(*ui_version())}</div>
</body>
</html>
"""
    (out / f"{name}.html").write_text(html, encoding="utf-8")


def _guide(out: Path, ui) -> None:
    (out / "guide.css").write_text("body{margin:0;background:#fff;font-family:var(--font);-webkit-font-smoothing:antialiased}"
                                   + ui.BASE_CSS + GUIDE_CSS, encoding="utf-8")
    _doc(out, ui, ROOT / "docs" / "GUIDE.md", "guide", "Guide", "How anyrecon works and how it handles your data: the full technical guide.")
    _doc(out, ui, ROOT / "CHANGELOG.md", "changelog", "What's new", "anyrecon versions and what changed in each.")
    log("guide.html and changelog.html written")


def ui_version() -> tuple[str, str]:
    init = (ROOT / "anyrecon" / "__init__.py").read_text()
    return (re.search(r'__version__\s*=\s*"([^"]+)"', init).group(1), re.search(r'__released__\s*=\s*"([^"]+)"', init).group(1))


# ---------------------------------------------------------------- installable app (PWA)
# Chrome/Edge show an install icon in the address bar when the site has a manifest and a service worker.
# The service worker keeps a copy of everything the app loads, so once installed and opened it also
# starts with no internet connection. It only ever stores the app's own files, never user data.
PWA_JS = r"""
(() => {
  const btn = document.getElementById("arInstall");
  const standalone = matchMedia("(display-mode: standalone)").matches || navigator.standalone;
  if (standalone) { const s = document.getElementById("install"); if (s) s.hidden = true; }
  if ("serviceWorker" in navigator) {
    addEventListener("load", () => navigator.serviceWorker.register("./sw.js").catch(() => {}));
  }
  let deferred = null;
  addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); deferred = e; if (btn) btn.hidden = false; });
  addEventListener("appinstalled", () => { deferred = null; if (btn) btn.hidden = true; });
  if (btn) btn.addEventListener("click", async () => {
    if (!deferred) return;
    deferred.prompt();
    try { await deferred.userChoice; } catch (e) {}
    deferred = null; btn.hidden = true;
  });
})();
"""

SW_JS = r"""// anyrecon service worker. Caches the app's own files so the installed app starts offline.
// It never sees user files: those are opened inside the page and never requested over the network.
const VERSION = "__VERSION__";
const CACHE = "anyrecon-" + VERSION;
const SHELL = __SHELL__;
const IMMUTABLE = /\/(pyodide|stlite|wheels|app)\//;   // content-hashed or versioned: cache first

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k.startsWith("anyrecon-") && k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

const put = (req, res) => { if (res && res.ok && res.type === "basic") caches.open(CACHE).then((c) => c.put(req, res.clone())); return res; };

self.addEventListener("fetch", (e) => {
  const req = e.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin) return;
  if (IMMUTABLE.test(url.pathname)) {
    e.respondWith(caches.match(req).then((hit) => hit || fetch(req).then((res) => put(req, res))));
    return;
  }
  // Everything else: the network first (so updates arrive), the cached copy when offline or slow.
  e.respondWith((async () => {
    try {
      const res = await Promise.race([fetch(req), new Promise((_, no) => setTimeout(() => no(new Error("slow")), 6000))]);
      return put(req, res);
    } catch (err) {
      const hit = await caches.match(req, { ignoreSearch: req.mode === "navigate" });
      return hit || (req.mode === "navigate" ? caches.match("./index.html") : Response.error());
    }
  })());
});
"""


def _pwa(out: Path, app_files: list[str]) -> None:
    import hashlib
    for f in (HERE / "assets").glob("*.png"):
        shutil.copy2(f, out / f.name)
    manifest = {
        "id": "./", "name": "anyrecon", "short_name": "anyrecon",
        "description": "Reconcile any set of documents. Runs on your device; files are never uploaded.",
        "start_url": "./", "scope": "./", "display": "standalone",
        "background_color": "#FFFFFF", "theme_color": "#FFFFFF",
        "icons": [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
                  {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
                  {"src": "icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}],
    }
    (out / "manifest.webmanifest").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    shell = ["./", "./index.html", "./boot.js", "./boot.css", "./guide.html", "./changelog.html", "./guide.css", "./manifest.webmanifest",
             "./icon-192.png", "./icon-512.png", "./stlite/stlite.js", "./stlite/stlite.css"] + [f"./{f}" for f in app_files]
    h = hashlib.sha256()
    for rel in shell[1:]:
        h.update((out / rel[2:]).read_bytes())
    sw = SW_JS.replace("__VERSION__", h.hexdigest()[:12]).replace("__SHELL__", json.dumps(shell))
    (out / "sw.js").write_text(sw, encoding="utf-8")
    log(f"installable app: manifest + service worker (version {h.hexdigest()[:12]})")


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
    ap.add_argument("--out", type=Path, default=ROOT / "web")
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

    # 4. The app itself
    files = {}
    for p in sorted((ROOT / "anyrecon").glob("*.py")):
        files[f"anyrecon/{p.name}"] = p
    files["app.py"] = ROOT / "app.py"
    files["ui_theme.py"] = ROOT / "ui_theme.py"
    for w in nodeps:   # pure-Python, imported straight from the wheel (zip) at start-up: see app.py
        files[f"wheels/{w}"] = out / "wheels" / w
    # The app's code goes in a folder named after a fingerprint of its contents (app/<hash>/), so each release
    # gets new addresses and the files can be cached as immutable, like the runtime. That matters offline: the
    # Python worker fetches them itself, outside the service worker, so only the browser's cache can serve them.
    import hashlib
    fp = hashlib.sha256()
    for rel in sorted(files):
        fp.update(rel.encode()); fp.update(Path(files[rel]).read_bytes())
    app_dir = f"app/{fp.hexdigest()[:12]}"
    for rel, src in files.items():
        dst = out / app_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    log(f"{len(files)} app files in {app_dir}/")

    # 5. Page
    stl_files = {rel: {"url": f"./{app_dir}/{rel}"} for rel in files}
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
    wanted = (Path(__file__).parent / "prefetch.txt").read_text().split()
    prefetch = [f for f in wanted if (out / "stlite" / f).exists()]
    if len(prefetch) < len(wanted):
        log(f"warning: {len(wanted) - len(prefetch)} prefetch chunk(s) not found (stlite version changed?): refresh prefetch.txt")
    version = re.search(r'__version__\s*=\s*"([^"]+)"', (ROOT / "anyrecon" / "__init__.py").read_text()).group(1)
    released = re.search(r'__released__\s*=\s*"([^"]+)"', (ROOT / "anyrecon" / "__init__.py").read_text()).group(1)
    landing = ui.landing_page(version, released)
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
<link rel="icon" href="./favicon-32.png" type="image/png">
<link rel="apple-touch-icon" href="./apple-touch-icon.png">
<link rel="manifest" href="./manifest.webmanifest">
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
    _guide(out, ui)
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
        + LANDING_JS.replace("PREFETCH", json.dumps(prefetch)) + PWA_JS +
        'mount(abs(options), document.getElementById("root"));\n', encoding="utf-8")
    _pwa(out, [f"{app_dir}/{f}" for f in sorted(stl_files)])
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
