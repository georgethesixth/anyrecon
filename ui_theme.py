"""Look and feel for the anyrecon UI (shared by the Browser, Desktop and Server editions).

Plain and practical: system fonts (nothing to download), white surfaces, grey hairlines, one blue accent.
The landing page is plain HTML so the Browser edition can show it instantly while the engine loads.
"""
from __future__ import annotations

import html

ACCENT, INK, MUTED, LINE, WELL = "#2457D6", "#14171F", "#5F6673", "#E3E6EB", "#F5F6F8"
REPO = "https://github.com/georgethesixth/anyrecon"
AUTHOR_URL = "https://kemdi.co"

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


def css(_font_base=None) -> str:
    return f"<style>{BASE_CSS}{ST_CSS}</style>"


def esc(s) -> str:
    return html.escape(str(s))


def logo(href: str = "#") -> str:
    return f'<a class="ar-logo" href="{href}"><b>ar</b>anyrecon</a>'


def nav(extra: str = "") -> str:
    return (f'<nav class="ar-nav">{logo()}<div class="ar-navlinks">{extra}<a class="opt" href="#how">How it works</a>'
            f'<a class="opt" href="#data">Your data</a><a href="{REPO}" target="_blank" rel="noopener">GitHub</a></div></nav>')


HERO_TITLE = "Reconcile any set of documents."
HERO_TEXT = ("Add your files, choose which ones should agree, and anyrecon finds the references they share and matches them "
             "line by line. Anything that doesn't match comes with a reason.")


def home_top(where: str = "") -> str:
    return f'{nav()}<div class="ar-hero"><h1>{HERO_TITLE}</h1><p>{HERO_TEXT}</p></div>'


def facts(edition: str) -> str:
    first = {"Browser": "Runs in this browser tab", "Desktop": "Runs on this computer",
             "Server": "Runs on your organisation's server"}.get(edition, "Runs locally")
    items = [first, "Files are never uploaded" if edition == "Browser" else "Nothing is sent anywhere",
             "Card numbers masked", "Nothing stored"]
    return '<div class="ar-facts">' + "".join(f"<span>{esc(i)}</span>" for i in items) + "</div>"


def home_where(where: str, edition: str) -> str:
    return facts(edition)


def home_sections(edition: str, browser: bool) -> str:
    steps = [
        ("Add your documents", "Processor exports, ledgers, bank statements, settlement reports. CSV, Excel, JSON or PDF"
         + ("" if browser else ", including scans") + ". Multi-tab workbooks are fine."),
        ("Choose the pairs", "Say what should agree with what, e.g. processor and bank. Three or more documents are linked "
         "into one view per transaction."),
        ("Confirm the references", "anyrecon proposes the shared reference for each pair, even with prefixes, missing zeros "
         "or references buried in narrations. Ranked, with examples."),
        ("Review the breaks", "Missing items, amount differences, timing, duplicates and likely typos, each with a reason. "
         "Download the Excel report and an audit trail."),
    ]
    cards = "".join(f'<div class="ar-card"><span class="n">{i}</span><h3>{esc(t)}</h3><p>{esc(b)}</p></div>'
                    for i, (t, b) in enumerate(steps, 1))
    where = ("In this browser tab. Files are read here and never uploaded." if browser
             else "On this computer." if edition == "Desktop" else "On your organisation's server.")
    rows = [("Where it runs", where),
            ("Card numbers", "Masked to the first six and last four digits on load. Security codes and PIN data are removed."),
            ("What is kept", "Nothing. Close the tab or clear the session and it's gone."),
            ("How matching works", "Fixed rules you can see, not guesses. Every match records the rule that made it.")]
    dl = "".join(f"<dt>{esc(a)}</dt><dd>{esc(b)}</dd>" for a, b in rows)
    return (f'<section class="ar-sec" id="how"><h2>How it works</h2><p>No setup and no account.</p>'
            f'<div class="ar-cards">{cards}</div></section>'
            f'<section class="ar-sec" id="data"><h2>Your data</h2><p>Built for card and bank data.</p><dl class="ar-dl">{dl}</dl></section>')


def footer(version: str, edition: str) -> str:
    return (f'<footer class="ar-foot"><span>anyrecon {esc(version)} · {esc(edition)} edition</span>'
            f'<span>A project by <a href="{AUTHOR_URL}" target="_blank" rel="noopener">Kemdi Okoli</a> · '
            f'<a href="{REPO}" target="_blank" rel="noopener">Source on GitHub</a></span></footer>')


def landing_page(edition: str, version: str, browser: bool) -> str:
    """The whole landing page as static HTML (Browser edition shows it before Python has started)."""
    status = '<span class="ar-status" id="arStatus"><i></i><em>Preparing engine</em></span>'
    actions = ('<div class="ar-actions"><button class="ar-btn primary" data-go="start">Start reconciling</button>'
               '<button class="ar-btn" data-go="sample">Try with sample data</button></div>')
    return (f'<div class="ar-wrap">{nav(status)}<div class="ar-hero"><h1>{HERO_TITLE}</h1><p>{HERO_TEXT}</p>{actions}'
            f'{facts(edition)}</div>{home_sections(edition, browser)}{footer(version, edition)}</div>')


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
