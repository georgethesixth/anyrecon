"""Look and feel for the anyrecon UI.

Plain and practical: system fonts (nothing to download), white surfaces, grey hairlines, one blue accent.
The landing page is plain HTML so it shows instantly while the engine loads in the background.
"""
from __future__ import annotations

import html

ACCENT, INK, MUTED, LINE, WELL = "#2457D6", "#14171F", "#5F6673", "#E3E6EB", "#F5F6F8"
REPO = "https://github.com/georgethesixth/anyrecon"
AUTHOR_URL = "https://kemdi.co"
SITE = "https://anyrecon.vercel.app"
GUIDE_URL = SITE + "/guide.html"           # rendered from docs/GUIDE.md by browser/build.py
CHANGELOG_URL = SITE + "/changelog.html"   # rendered from CHANGELOG.md
DOWNLOAD_URL = REPO + "/archive/refs/heads/main.zip"   # web/ is export-ignored (.gitattributes): about 1 MB

# Measured with scripts/benchmark.py (three files of N rows each: processor, ledger, bank with references in
# narrations and a fee) on a modest 2-core machine. Faster computers finish sooner. See the guide for the table.
SIZE_GUIDE = {
    "web": ("Up to about 250,000 rows per file (37 MB for three files). 500,000 at most",
            "About 2 minutes for 100,000 rows per file, 4 minutes for 250,000"),
    "download": ("Up to about 1,000,000 rows per file (150 MB for three files), with 8 GB of memory",
                 "About 1 minute for 100,000 rows per file, 8 minutes for 1,000,000"),
}

BASE_CSS = """
:root{--accent:#2457D6;--accent-d:#1C46B0;--accent-soft:#EEF3FD;--ink:#14171F;--ink2:#2B303B;--muted:#5F6673;--faint:#8A909C;
  --line:#E3E6EB;--well:#F5F6F8;--bg:#FFFFFF;--ok:#1F8A4C;--warn:#B26B00;--bad:#C2362B;
  --font:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.ar-wrap{max-width:1080px;margin:0 auto;padding:0 24px}
.ar-nav{display:flex;align-items:center;justify-content:space-between;gap:16px;height:60px;border-bottom:1px solid var(--line)}
.ar-logo{display:flex;align-items:center;gap:9px;font-weight:650;font-size:17px;color:var(--ink);text-decoration:none;letter-spacing:-.01em}
.ar-logo b{display:grid;place-items:center;width:26px;height:26px;border-radius:7px;background:var(--accent);color:#fff;font-size:13px;font-weight:700}
.ar-navlinks{display:flex;align-items:center;gap:22px;font-size:14px}
.ar-navlinks a{color:var(--muted);text-decoration:none}
.ar-navlinks a:hover{color:var(--ink)}
.ar-install{font:500 13.5px var(--font);color:#fff;background:var(--accent);border:0;border-radius:999px;padding:6px 12px;cursor:pointer}
.ar-install:hover{background:var(--accent-d)}
.ar-install[hidden]{display:none}
.ar-hero{padding:72px 0 8px;max-width:720px}
.ar-hero h1{font-size:clamp(32px,4.6vw,46px);line-height:1.1;letter-spacing:-.025em;font-weight:700;color:var(--ink);margin:0}
.ar-hero p{font-size:18px;line-height:1.6;color:var(--muted);margin:18px 0 0;max-width:36em}
.ar-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:30px}
.ar-btn{display:inline-flex;align-items:center;gap:8px;font:500 15px/1 var(--font);padding:12px 18px;border-radius:8px;border:1px solid var(--line);
  background:#fff;color:var(--ink);cursor:pointer;text-decoration:none}
.ar-btn:hover{border-color:#C9CED6;background:var(--well)}
.ar-btn.primary{background:var(--accent);border-color:var(--accent);color:#fff}
.ar-btn.primary:hover{background:var(--accent-d);border-color:var(--accent-d)}
.ar-btn[disabled]{opacity:.75;cursor:progress}
.ar-facts{display:flex;flex-wrap:wrap;gap:8px 20px;margin-top:26px;font-size:14px;color:var(--muted)}
.ar-facts span{display:inline-flex;align-items:center;gap:7px}
.ar-facts span::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--ok)}
.ar-sec{padding:64px 0 0}
.ar-sec h2{font-size:24px;letter-spacing:-.015em;font-weight:650;color:var(--ink);margin:0 0 6px}
.ar-sec>p{color:var(--muted);font-size:15px;margin:0 0 22px}
.ar-sec>p a{color:var(--accent)}
.stLinkButton a{border-radius:8px!important;border:1px solid var(--line)!important;padding:12px 18px!important;font-size:15px!important;color:var(--ink)!important;background:#fff!important}
.ar-cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}
.ar-card{border:1px solid var(--line);border-radius:10px;padding:18px;background:#fff}
.ar-card .n{display:inline-grid;place-items:center;width:24px;height:24px;border-radius:6px;background:var(--accent-soft);color:var(--accent);
  font-size:13px;font-weight:650}
.ar-card h3{font-size:15px;font-weight:650;color:var(--ink);margin:12px 0 6px;letter-spacing:0}
.ar-card p{font-size:14px;line-height:1.55;color:var(--muted);margin:0}
.ar-dl{display:grid;grid-template-columns:180px minmax(0,1fr);margin:0;border-top:1px solid var(--line)}
.ar-dl dt,.ar-dl dd{padding:14px 0;border-bottom:1px solid var(--line);margin:0;font-size:15px}
.ar-dl dt{font-weight:600;color:var(--ink)}
.ar-dl dd{color:var(--muted)}
.ar-foot{display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-top:72px;padding:20px 0 28px;border-top:1px solid var(--line);
  font-size:13px;color:var(--faint)}
.ar-foot a{color:var(--muted);text-decoration:none}
.ar-foot a:hover{color:var(--ink);text-decoration:underline}
.ar-steps{display:flex;flex-wrap:wrap;gap:6px}
.ar-steps span{display:inline-flex;align-items:center;gap:7px;font-size:13px;color:var(--faint);padding:6px 10px;border-radius:999px}
.ar-steps span i{font-style:normal;display:inline-grid;place-items:center;width:20px;height:20px;border-radius:50%;border:1px solid var(--line);font-size:11px;font-weight:600}
.ar-steps span.done{color:var(--muted)}
.ar-steps span.done i{background:var(--accent-soft);border-color:var(--accent-soft);color:var(--accent)}
.ar-steps span.on{color:var(--ink);background:var(--well);font-weight:600}
.ar-steps span.on i{background:var(--accent);border-color:var(--accent);color:#fff}
.ar-step{margin:44px 0 4px;padding-top:28px;border-top:1px solid var(--line)}
.ar-step.first{margin-top:12px;padding-top:0;border-top:0}
.ar-step .k{font-size:12px;font-weight:600;color:var(--accent);text-transform:uppercase;letter-spacing:.06em}
.ar-step h2{font-size:22px!important;font-weight:650!important;letter-spacing:-.01em;color:var(--ink);margin:4px 0 2px!important;padding:0!important}
.ar-step p{color:var(--muted);font-size:15px;margin:0}
.ar-note{color:var(--muted);font-size:14px;margin:6px 0 0}
.ar-os{border:1px solid var(--line);border-radius:12px;background:#fff;overflow:hidden}
.ar-os>input{position:absolute;opacity:0;pointer-events:none}
.ar-os-tabs{display:flex;border-bottom:1px solid var(--line);background:var(--well)}
.ar-os-tabs label{padding:12px 20px;font-size:15px;font-weight:500;color:var(--muted);cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-1px}
.ar-os-tabs label:hover{color:var(--ink)}
#os-win:checked~.ar-os-tabs label[for=os-win],#os-mac:checked~.ar-os-tabs label[for=os-mac],#os-linux:checked~.ar-os-tabs label[for=os-linux]
  {color:var(--ink);border-bottom-color:var(--accent);background:#fff}
#os-win:focus-visible~.ar-os-tabs label[for=os-win],#os-mac:focus-visible~.ar-os-tabs label[for=os-mac],#os-linux:focus-visible~.ar-os-tabs label[for=os-linux]
  {outline:2px solid var(--accent);outline-offset:-2px}
.ar-os-panel{display:none;padding:20px 22px 6px}
#os-win:checked~.ar-os-panels .p-win,#os-mac:checked~.ar-os-panels .p-mac,#os-linux:checked~.ar-os-panels .p-linux{display:block}
.ar-os-size{margin-left:12px;font-size:13px;color:var(--faint)}
.ar-os-panel ol{margin:18px 0 8px;padding-left:20px;color:var(--ink2);font-size:15px;line-height:1.6}
.ar-os-panel li{margin-bottom:8px}
.ar-os-panel code{font:13px var(--mono);background:var(--well);padding:1px 5px;border-radius:4px}
.ar-os-note{padding:12px 22px 16px;font-size:13.5px;color:var(--muted);border-top:1px solid var(--line)}
.ar-os-note a{color:var(--accent)}
.ar-vt{overflow-x:auto;border:1px solid var(--line);border-radius:12px}
.ar-vt table{width:100%;border-collapse:collapse;font-size:15px}
.ar-vt th,.ar-vt td{text-align:left;padding:11px 16px;border-bottom:1px solid var(--line);vertical-align:top}
.ar-vt tbody tr:last-child th,.ar-vt tbody tr:last-child td{border-bottom:0}
.ar-vt thead th{background:var(--well);font-weight:650}
.ar-vt thead a{color:var(--ink);text-decoration:none}
.ar-vt thead a:hover{color:var(--accent)}
.ar-vt tbody th{font-weight:600;color:var(--ink);width:22%}
.ar-vt td{color:var(--ink2)}
.ar-sec>p.ar-vt-note{font-size:13.5px;color:var(--muted);margin:12px 0 0}
.ar-vt-note a{color:var(--accent)}
.ar-results h2{font-size:22px!important;font-weight:650!important;margin:28px 0 2px!important;padding:0!important;color:var(--ink)}
.ar-results p{color:var(--muted);font-size:15px;margin:0}
.ar-pair{font-size:17px;font-weight:650;color:var(--ink);margin:30px 0 8px}
.ar-pair span{color:var(--faint);font-weight:400;margin:0 6px}
.ar-pair small{color:var(--muted);font-weight:400;font-size:14px;margin-left:6px}
@media (max-width:860px){.ar-cards{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:560px){.ar-cards{grid-template-columns:minmax(0,1fr)}.ar-dl{grid-template-columns:minmax(0,1fr)}.ar-dl dt{border-bottom:0;padding-bottom:0}
  .ar-hero{padding-top:44px}.ar-navlinks a.opt{display:none}}
"""

# Streamlit-specific: hide its chrome and bring its widgets in line with the above.
ST_CSS = """
header[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stStatusWidget"],
#MainMenu,footer,[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],[data-testid="collapsedControl"],
[data-testid="stHeaderActionElements"]{display:none!important}
[data-stale="true"],.stale-element{opacity:1!important;filter:none!important;transition:none!important}
.stApp{background:var(--bg)!important;color:var(--ink)}
.stApp,.stApp p,.stApp li,.stApp label,.stApp input,.stApp textarea,.stApp button,.stMarkdown,.stApp h1,.stApp h2,.stApp h3,
.stApp a,.stApp dt,.stApp dd,.stApp div[class^="ar-"],.stApp div[class^="ar-"] span{font-family:var(--font)!important}
.stApp a.ar-logo{color:var(--ink)!important;text-decoration:none!important}
.stApp .ar-navlinks a,.stApp .ar-foot a{color:var(--muted)!important;text-decoration:none!important}
.stApp .ar-navlinks a:hover,.stApp .ar-foot a:hover{color:var(--ink)!important}
.stApp .ar-hero{padding-top:56px}
.stApp .ar-hero h1{font-size:clamp(32px,4.6vw,46px)!important;font-weight:700!important;padding:0!important;line-height:1.1!important}
.block-container,[data-testid="stMainBlockContainer"]{max-width:1080px!important;padding:12px 24px 40px!important}
:focus-visible{outline:2px solid var(--accent)!important;outline-offset:2px}
.stButton>button,.stDownloadButton>button{border-radius:8px!important;border:1px solid var(--line)!important;background:#fff!important;color:var(--ink)!important;
  font-weight:500!important;padding:8px 14px!important;min-height:0!important;box-shadow:none!important}
.stButton>button:hover,.stDownloadButton>button:hover{border-color:#C9CED6!important;background:var(--well)!important}
.stButton>button[kind="primary"],[data-testid="stBaseButton-primary"]{background:var(--accent)!important;border-color:var(--accent)!important;color:#fff!important}
.stDownloadButton>button[kind="primary"]{background:var(--accent)!important;border-color:var(--accent)!important;color:#fff!important}
.stDownloadButton>button[kind="primary"]:hover{background:var(--accent-d)!important}
.stButton>button[kind="primary"] p,.stDownloadButton>button[kind="primary"] p{color:#fff!important}
.stButton>button[kind="primary"]:hover{background:var(--accent-d)!important}
.stApp input,.stApp textarea,[data-baseweb="select"]>div,[data-baseweb="input"]>div{border-radius:8px!important}
[data-baseweb="tag"]{border-radius:6px!important;background:var(--accent)!important}
[data-testid="stWidgetLabel"] p{font-size:14px!important;font-weight:500;color:var(--ink2)!important}
[data-testid="stFileUploaderDropzone"]{border-radius:10px!important;background:var(--well)!important;border:1px dashed #C9CED6!important}
[data-testid="stExpander"] details{border:1px solid var(--line)!important;border-radius:10px!important}
.stTabs [data-baseweb="tab-list"]{gap:22px;border-bottom:1px solid var(--line)}
.stTabs [data-baseweb="tab-highlight"]{background:var(--accent)!important}
[data-testid="stAlert"]>div{border-radius:10px!important}
[data-testid="stMetric"]{border:1px solid var(--line);border-radius:10px;padding:12px 14px}
[data-testid="stMetricValue"],[data-testid="stMetricValue"] *{font-size:26px!important;font-weight:650!important;font-variant-numeric:tabular-nums}
[data-testid="stMetricLabel"] p{font-size:13px!important;color:var(--muted)!important}
[data-testid="stDataFrame"]{border:1px solid var(--line);border-radius:10px;overflow:hidden}
.st-key-home_actions{margin-top:22px}
.st-key-home_actions [data-testid="stHorizontalBlock"]{gap:10px}
.st-key-home_actions [data-testid="stColumn"]{flex:0 0 auto!important;width:auto!important;min-width:0!important}
.st-key-home_actions button{padding:12px 18px!important;font-size:15px!important}
.st-key-go_home button{border:0!important;background:transparent!important;padding:4px 0!important;font-weight:650!important;font-size:17px!important}
.st-key-go_home button p{font-weight:650!important;font-size:17px!important}
.st-key-go_home button:hover{background:transparent!important;color:var(--accent)!important}
.st-key-topbar{border-bottom:1px solid var(--line);padding-bottom:8px;margin-bottom:0}
.st-key-tools [data-testid="stCheckbox"],.st-key-tools .stToggle{margin:0}
.st-key-downloads{gap:8px}
.st-key-clear{align-items:flex-end}
"""


# What the file picker says. Streamlit's default ("Upload", "200MB per file") suggests files leave the
# machine. They never do: the page opens them inside the browser tab.
PICKER_NOTE = "or drag them here. They open in this browser tab and are never uploaded."
PICKER_NOTE_DOWNLOAD = "or drag them here. They open on this computer and are never sent anywhere."


def css(download: bool = False) -> str:
    picker = (
        '[data-testid="stFileUploaderDropzone"] button span:has(>[data-testid="stIconMaterial"]){display:none!important}'
        '[data-testid="stFileUploaderDropzone"] button [data-testid="stMarkdownContainer"] p{font-size:0!important;line-height:0}'
        '[data-testid="stFileUploaderDropzone"] button [data-testid="stMarkdownContainer"] p::after{content:"Choose files";font-size:14.5px;line-height:1.4}'
        '[data-testid="stFileUploaderDropzoneInstructions"] span{font-size:0!important}'
        f'[data-testid="stFileUploaderDropzoneInstructions"] span::after{{content:"{PICKER_NOTE_DOWNLOAD if download else PICKER_NOTE}";font-size:14px;color:var(--muted)}}'
    )
    return f"<style>{BASE_CSS}{ST_CSS}{CONN_CSS}{picker}</style>"


def esc(s) -> str:
    return html.escape(str(s))


def logo(href: str = "#") -> str:
    return f'<a class="ar-logo" href="{href}"><b>ar</b>anyrecon</a>'


def nav(extra: str = "") -> str:
    return (f'<nav class="ar-nav">{logo()}<div class="ar-navlinks">{extra}<a class="opt" href="#how">How it works</a>'
            f'<a class="opt" href="#versions">Versions</a>'
            f'<a class="opt" href="{GUIDE_URL}" target="_blank" rel="noopener">Guide</a><a href="{REPO}" target="_blank" rel="noopener">GitHub</a></div></nav>')


HERO_TITLE = "Reconcile any set of documents."
HERO_TEXT = ("Add your files, choose which ones should agree, and anyrecon finds the references they share and matches them "
             "line by line. Anything that doesn't match comes with a reason.")


def home_top() -> str:
    return f'{nav()}<div class="ar-hero"><h1>{HERO_TITLE}</h1><p>{HERO_TEXT}</p></div>'


def facts(download: bool = False) -> str:
    items = (["Runs on this computer", "Nothing is sent anywhere"] if download else
             ["Runs in your browser", "Files are never uploaded"]) + ["Card numbers masked", "Nothing stored"]
    return '<div class="ar-facts">' + "".join(f"<span>{esc(i)}</span>" for i in items) + "</div>"


def home_sections(download: bool = False) -> str:
    steps = [
        ("Add your documents", "Processor exports, ledgers, bank statements, settlement reports. CSV, Excel, JSON or PDF. "
         "Multi-tab workbooks are fine."),
        ("Check the connections", "anyrecon proposes how the files link, even through prefixes, missing zeros or references "
         "buried in bank narrations, and shows how many rows each link matches, with examples."),
        ("Confirm or change", "Accept the proposal or pick a different match. Matching then runs on fixed rules; a consistent "
         "fee such as MDR is spotted and applied."),
        ("Review the breaks", "Missing items, amount differences, timing, duplicates and likely typos, each with a reason. "
         "Download the Excel report and an audit trail."),
    ]
    cards = "".join(f'<div class="ar-card"><span class="n">{i}</span><h3>{esc(t)}</h3><p>{esc(b)}</p></div>'
                    for i, (t, b) in enumerate(steps, 1))
    where = ("On this computer. Files are opened here and never sent anywhere." if download else
             "In your browser tab. Files are opened here and never uploaded; the page is not allowed to send data anywhere.")
    rows = [("Where it runs", where),
            ("Card numbers", "Masked to the first six and last four digits on load. Security codes and PIN data are removed."),
            ("What is kept", "Nothing. Close the tab or clear the session and it's gone."),
            ("How matching works", "Fixed rules you can see, not guesses. Every match records the rule that made it.")]
    dl = "".join(f"<dt>{esc(a)}</dt><dd>{esc(b)}</dd>" for a, b in rows)
    sections = (f'<section class="ar-sec" id="how"><h2>How it works</h2><p>No setup and no account.</p>'
                f'<div class="ar-cards">{cards}</div></section>'
                f'<section class="ar-sec" id="data"><h2>Your data</h2><p>Built for card and bank data. '
                f'<a href="{GUIDE_URL}#data-handling" target="_blank" rel="noopener">Full detail in the guide.</a></p>'
                f'<dl class="ar-dl">{dl}</dl></section>')
    return sections if download else sections + versions_section() + install_section() + download_section()


def versions_section() -> str:
    """Which version to use, by data size. Figures from scripts/benchmark.py (see SIZE_GUIDE)."""
    (wr, wt), (dr, dt) = SIZE_GUIDE["web"], SIZE_GUIDE["download"]
    rows = [("Best for", "Everyday reconciliations", "Large files and month-end volumes"),
            ("Comfortable size", wr, dr),
            ("Speed", wt, dt),
            ("Install", "Nothing. Optionally add it as an app in two clicks", "Download a 1 MB ZIP; needs Python"),
            ("Scanned documents", "No: use a digital export", "Yes, with Tesseract installed"),
            ("Works offline", "Yes, once added as an app and opened once", "Yes, after the first run"),
            ("Your files", "Stay in the browser", "Stay on your computer"),
            ("Updates", "Automatic", "Download the new version")]
    body = "".join(f"<tr><th>{esc(a)}</th><td>{esc(b)}</td><td>{esc(c)}</td></tr>" for a, b, c in rows)
    return (f'<section class="ar-sec" id="versions"><h2>Which version?</h2><p>Same tool and same results. '
            f'The difference is how much data each handles comfortably.</p><div class="ar-vt"><table>'
            f'<thead><tr><th></th><th><a href="#install">In your browser or as an app</a></th>'
            f'<th><a href="#download">Download for your computer</a></th></tr></thead><tbody>{body}</tbody></table></div>'
            f'<p class="ar-vt-note">Measured with three files at once on a modest 2-core machine; faster computers finish sooner. '
            f'<a href="{GUIDE_URL}#data-size-and-speed" target="_blank" rel="noopener">Full measurements</a>.</p></section>')


def install_section() -> str:
    install = [("Add it", "In Chrome or Edge, click the install icon at the right end of the address bar "
                          "(a screen with a down arrow), or the <b>Install app</b> button at the top of this page."),
               ("Then", "anyrecon opens in its own window from your Start menu, Dock or desktop, like any other app."),
               ("Offline", "Once added and opened once, it starts and works with no internet connection."),
               ("Size", "Same as the web page: it is the web page in its own window, so it handles the same amount of data."),
               ("Remove", "Open the app, click the ⋮ menu at the top of its window, choose <b>Uninstall</b>.")]
    inst = "".join(f"<dt>{esc(a)}</dt><dd>{b}</dd>" for a, b in install)
    return (f'<section class="ar-sec" id="install"><h2>Use it as an app</h2><p>Your browser adds it like an app in two clicks. '
            f'Nothing to download, no administrator rights needed.</p><dl class="ar-dl">{inst}</dl></section>')


def download_section() -> str:
    """'Download for your computer': the download version, one tab per OS. CSS-only tabs (radio inputs);
    boot.js pre-selects the visitor's OS."""
    trouble = f'<a href="{GUIDE_URL}#run-it-on-your-computer" target="_blank" rel="noopener">Help and troubleshooting</a>'
    oses = [
        ("win", "Windows", "Start anyrecon (Windows).bat", [
            "Download and unzip it (right-click → <b>Extract All</b>).",
            "In the <b>anyrecon-main</b> folder, double-click <b>Start anyrecon (Windows).bat</b>. "
            "If Windows says it protected your PC, click <b>More info</b> → <b>Run anyway</b>.",
            "No Python yet? The download page opens: install it, ticking <b>Add python.exe to PATH</b> "
            "(no administrator rights needed), then double-click the file again.",
            "The first run sets itself up in 2–5 minutes, then anyrecon opens in your browser."]),
        ("mac", "Mac", "Start anyrecon (Mac).command", [
            "Download it; it unzips into an <b>anyrecon-main</b> folder.",
            "Right-click <b>Start anyrecon (Mac).command</b> → <b>Open</b> → <b>Open</b>. "
            "The right-click is needed the first time only.",
            "No Python yet? The download page opens: install it (it may ask for your Mac password), then repeat step 2.",
            "The first run sets itself up in 2–5 minutes, then anyrecon opens in your browser."]),
        ("linux", "Linux", "start-anyrecon-linux.sh", [
            "Download and unzip it.",
            "In a terminal, in the <b>anyrecon-main</b> folder: <code>bash start-anyrecon-linux.sh</code>",
            "Needs Python 3.10+ with venv (<code>sudo apt install python3-venv</code> on Ubuntu).",
            "The first run sets itself up in 2–5 minutes, then anyrecon opens in your browser."]),
    ]
    radios = "".join(f'<input type="radio" name="ar-os" id="os-{k}"{" checked" if k == "win" else ""}>' for k, _, _, _ in oses)
    tabs = "".join(f'<label for="os-{k}">{n}</label>' for k, n, _, _ in oses)
    panels = "".join(
        f'<div class="ar-os-panel p-{k}"><a class="ar-btn primary" href="{DOWNLOAD_URL}">Download for {n}</a>'
        f'<span class="ar-os-size">ZIP, about 1 MB</span><ol>' + "".join(f"<li>{s}</li>" for s in steps) + "</ol></div>"
        for k, n, _, steps in oses)
    return (f'<section class="ar-sec" id="download"><h2>Download for your computer</h2>'
            f'<p>For large files: it uses your computer\'s full memory instead of the browser\'s. Also reads scanned documents. '
            f'Same tool, same results, and your files stay on your computer.</p>'
            f'<div class="ar-os">{radios}<div class="ar-os-tabs">{tabs}</div><div class="ar-os-panels">{panels}</div>'
            f'<div class="ar-os-note">Installs only inside its own folder: delete the folder to remove it. The first run downloads its '
            f'components from pypi.org; after that it works offline. Can\'t install anything? The browser version needs nothing installed. {trouble}.</div>'
            f'</div></section>')


def footer(version: str, released: str = "") -> str:
    from datetime import date
    when = f" · updated {date.fromisoformat(released):%-d %b %Y}" if released else ""
    return (f'<footer class="ar-foot"><span>anyrecon {esc(version)}{when} · '
            f'<a href="{CHANGELOG_URL}" target="_blank" rel="noopener">What\'s new</a></span>'
            f'<span>A project by <a href="{AUTHOR_URL}" target="_blank" rel="noopener">Kemdi Okoli</a> · '
            f'<a href="{GUIDE_URL}" target="_blank" rel="noopener">Guide</a> · '
            f'<a href="{REPO}" target="_blank" rel="noopener">Source on GitHub</a></span></footer>')


def landing_page(version: str, released: str = "") -> str:
    """The whole landing page as static HTML, shown before Python has started."""
    status = ('<span class="ar-status" id="arStatus"><i></i><em>Preparing engine</em></span>'
              '<button class="ar-install" id="arInstall" hidden>Install app</button>')
    actions = ('<div class="ar-actions"><button class="ar-btn primary" data-go="start">Start reconciling</button>'
               f'<a class="ar-btn" href="{GUIDE_URL}" target="_blank" rel="noopener">How it works and handles data</a></div>')
    return (f'<div class="ar-wrap">{nav(status)}<div class="ar-hero"><h1>{HERO_TITLE}</h1><p>{HERO_TEXT}</p>{actions}'
            f'{facts()}</div>{home_sections()}{footer(version, released)}</div>')


def steps_bar(active: int) -> str:
    names = ["Documents", "Pairs", "Rules", "Results"]
    out = []
    for i, n in enumerate(names, 1):
        cls = "on" if i == active else "done" if i < active else ""
        out.append(f'<span class="{cls}"><i>{"✓" if i < active else i}</i>{n}</span>')
    return '<div class="ar-steps ar-ready">' + "".join(out) + "</div>"


def step_head(n: int, title: str, intro: str = "") -> str:
    return (f'<div class="ar-step{" first" if n == 1 else ""}"><div class="k">Step {n}</div><h2>{esc(title)}</h2>'
            + (f'<p>{esc(intro)}</p>' if intro else "") + "</div>")


def pair_head(left: str, right: str, note: str = "") -> str:
    return (f'<div class="ar-pair">{esc(left)}<span>↔</span>{esc(right)}'
            + (f"<small>{esc(note)}</small>" if note else "") + "</div>")


# ---------------------------------------------------------------- connections (Power BI–style model view)
def _tone(pct: float) -> str:
    return "#1F8A4C" if pct >= 90 else "#B26B00" if pct >= 60 else "#C2362B"


def graph_svg(nodes: list[tuple[str, int]], edges: list[tuple[str, str, str, float, str, str]]) -> str:
    """nodes: (name, rows). edges: (a, b, label, match %, cardinality at a, cardinality at b)."""
    import math
    n = len(nodes)
    W, H, bw, bh = 1000, 300 if n > 2 else 170, 176, 56
    cx, cy = W / 2, H / 2
    if n == 2:
        pos = {nodes[0][0]: (230, cy), nodes[1][0]: (W - 230, cy)}
    else:
        rx, ry = 360, (H - bh) / 2 - 8
        pos = {nm: (cx + rx * math.cos(-math.pi / 2 + 2 * math.pi * i / n), cy + ry * math.sin(-math.pi / 2 + 2 * math.pi * i / n))
               for i, (nm, _) in enumerate(nodes)}
    linked = {x for e in edges for x in e[:2]}
    out = [f'<svg class="ar-graph" viewBox="0 0 {W} {H}" role="img" aria-label="How the files connect" '
           f'xmlns="http://www.w3.org/2000/svg" font-family="system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif">']
    for a, b, label, pct, ca, cb in edges:
        (x1, y1), (x2, y2) = pos[a], pos[b]
        col = _tone(pct)
        out.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="{col}" stroke-width="2"/>')
        for (px, py), (qx, qy), card in (((x1, y1), (x2, y2), ca), ((x2, y2), (x1, y1), cb)):   # 1 / * near each box
            d = math.hypot(qx - px, qy - py) or 1
            t = min(0.45, (bw / 2 + 22) / d) if abs(qx - px) > abs(qy - py) * 3 else min(0.45, (bh / 2 + 18) / d)
            ox = 11 if abs(qx - px) < abs(qy - py) else 0   # sit beside a steep line, not on it
            out.append(f'<text x="{px + (qx - px) * t + ox:.0f}" y="{py + (qy - py) * t - (0 if ox else 6):.0f}" font-size="14" font-weight="700" '
                       f'fill="{col}" text-anchor="middle">{esc(card)}</text>')
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        txt = f"{label} · {pct:.0f}%"
        w = max(90, 7.2 * len(txt) + 18)
        out.append(f'<rect x="{mx - w / 2:.0f}" y="{my - 13:.0f}" width="{w:.0f}" height="26" rx="13" fill="#fff" stroke="{col}"/>'
                   f'<text x="{mx:.0f}" y="{my + 5:.0f}" font-size="13" fill="#14171F" text-anchor="middle">{esc(txt)}</text>')
    for name, rows in nodes:
        x, y = pos[name]
        on = name in linked
        out.append(f'<rect x="{x - bw / 2:.0f}" y="{y - bh / 2:.0f}" width="{bw}" height="{bh}" rx="10" fill="#fff" '
                   f'stroke="{"#C9CED6" if on else "#C2362B"}" stroke-width="1.5"{"" if on else " stroke-dasharray=\"5 4\""}/>'
                   f'<rect x="{x - bw / 2:.0f}" y="{y - bh / 2:.0f}" width="6" height="{bh}" rx="3" fill="{ACCENT if on else "#C2362B"}"/>'
                   f'<text x="{x - bw / 2 + 18:.0f}" y="{y - 4:.0f}" font-size="15" font-weight="650" fill="#14171F">{esc(name[:20])}</text>'
                   f'<text x="{x - bw / 2 + 18:.0f}" y="{y + 16:.0f}" font-size="12.5" fill="#5F6673">'
                   f'{rows:,} rows{"" if on else " · not connected"}</text>')
    out.append("</svg>")
    return "".join(out)


def conn_card(a: str, b: str, rule: str, la: int, lb: int, na: int, nb: int, examples: list, note: str = "") -> str:
    """Power BI merge-style summary for one connection."""
    pa, pb = (100 * la / na if na else 0), (100 * lb / nb if nb else 0)
    pct = pa if na <= nb else pb    # judged on the smaller file: a partial extract can still match fully
    col = _tone(pct)
    ex = "".join(f'<tr><td>{esc(str(x)[:40])}</td><td class="eq">⟷</td><td>{esc(str(y)[:60])}</td></tr>' for x, y in examples[:3])
    return (f'<div class="ar-conn"><div class="ar-conn-h"><b>{esc(a)}</b><span>↔</span><b>{esc(b)}</b>'
            f'<em style="color:{col};border-color:{col}">{pct:.0f}% match</em></div>'
            f'<div class="ar-conn-r">{esc(rule)}</div>'
            f'<div class="ar-conn-bars"><div><span>Matches <b>{la:,}</b> of {na:,} {esc(a)} rows</span>'
            f'<i><s style="width:{pa:.1f}%;background:{_tone(pa)}"></s></i></div>'
            f'<div><span>Matches <b>{lb:,}</b> of {nb:,} {esc(b)} rows</span><i><s style="width:{pb:.1f}%;background:{_tone(pb)}"></s></i></div></div>'
            + (f'<table class="ar-ex"><thead><tr><th>{esc(a)}</th><th></th><th>{esc(b)}</th></tr></thead><tbody>{ex}</tbody></table>' if ex else "")
            + (f'<div class="ar-conn-n">{esc(note)}</div>' if note else "") + "</div>")


def file_card(name: str, fmt: str, rows: int, cols: int, amount: str | None, date: str | None, card_note: str, warn: bool) -> str:
    roles = " · ".join(f"{k}: <b>{esc(v)}</b>" for k, v in (("Amount", amount), ("Date", date)) if v) or "No amount or date column found"
    return (f'<div class="ar-file{" warn" if warn else ""}"><div class="ar-file-h"><b>{esc(name)}</b><small>{esc(fmt)}</small></div>'
            f'<div class="ar-file-m">{rows:,} rows · {cols} columns</div><div class="ar-file-r" title="{esc(amount or "")} / {esc(date or "")}">{roles}</div>'
            f'<div class="ar-file-n">{"🔒 " + esc(card_note) if card_note else "&nbsp;"}</div></div>')


CONN_CSS = """
.ar-graph{width:100%;height:auto;display:block;background:var(--well);border:1px solid var(--line);border-radius:12px}
.ar-conn{border:1px solid var(--line);border-radius:12px;padding:16px 18px;background:#fff}
.ar-conn-h{display:flex;align-items:center;gap:8px;font-size:16px;color:var(--ink)}
.ar-conn-h span{color:var(--faint)}
.ar-conn-h em{margin-left:auto;font-style:normal;font-size:12.5px;font-weight:600;border:1px solid;border-radius:999px;padding:2px 9px}
.ar-conn-r{margin-top:4px;color:var(--muted);font-size:14px}
.ar-conn-bars{display:grid;grid-template-columns:1fr 1fr;gap:10px 22px;margin-top:12px}
.ar-conn-bars span{display:block;font-size:13.5px;color:var(--ink2);margin-bottom:5px}
.ar-conn-bars i{display:block;height:6px;border-radius:3px;background:var(--line);overflow:hidden}
.ar-conn-bars s{display:block;height:100%;text-decoration:none}
.ar-ex{width:100%;border-collapse:collapse;margin-top:12px;font-size:13px;font-family:var(--mono)}
.ar-ex th{font-family:var(--font);text-align:left;font-weight:600;color:var(--muted);font-size:12px;padding:4px 6px;border-bottom:1px solid var(--line)}
.ar-ex td{padding:5px 6px;border-bottom:1px solid var(--line);color:var(--ink2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:0}
.ar-ex td.eq,.ar-ex th:nth-child(2){width:28px;color:var(--faint);text-align:center}
.ar-conn-n{margin-top:10px;font-size:13px;color:var(--muted)}
.ar-file{border:1px solid var(--line);border-radius:12px 12px 0 0;border-bottom:0;padding:11px 13px 8px;background:#fff}
.ar-file-r{font-size:12.5px;color:var(--muted);margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ar-file-r b{color:var(--ink2);font-weight:500}
.ar-file.warn{border-color:#E8B44C;background:#FFFBF0}
.ar-file-h{display:flex;align-items:baseline;gap:8px}
.ar-file-h b{font-size:15px;color:var(--ink);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ar-file-h small{color:var(--faint);font-size:12px;text-transform:uppercase}
.ar-file-m{font-size:13px;color:var(--muted);margin-top:2px}
.ar-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.ar-chips span{font-size:12px;background:var(--well);border-radius:6px;padding:3px 7px;color:var(--ink2);max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ar-chips small{color:var(--faint);margin-right:5px}
.ar-file-n{font-size:12.5px;color:var(--muted);margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
[class*="st-key-fcard_"] [data-testid="stPopover"] button{border-radius:0 0 12px 12px!important;border-color:var(--line)!important;padding:5px!important;font-size:13px!important;color:var(--muted)!important}
[class*="st-key-fcard_"] [data-testid="stMarkdownContainer"]{margin-bottom:-16px}
[class*="st-key-conn_btns_"] button{padding:5px 12px!important;font-size:13.5px!important}
.ar-h3{font-size:18px;font-weight:650;color:var(--ink);margin:26px 0 2px}
.ar-sub{color:var(--muted);font-size:14px;margin:0 0 12px}
@media (max-width:640px){.ar-conn-bars{grid-template-columns:1fr}}
"""
