"""Monogram theme for the anyrecon UI (shared by the Browser, Desktop and Server editions).

Palette and type follow the Monogram design of kemdi.co: warm paper, ink, hairline rules,
Cormorant Garamond for display (italic accents), Geist for text and spaced small caps.
"""
from __future__ import annotations

import html

PAPER, INK, INK2, MUTED, SOFT, RULE, EDGE = "#F2F0EA", "#25231F", "#3A372F", "#A39D90", "#7A7468", "#DDD8CD", "#B9B3A7"
REPO = "https://github.com/georgethesixth/anyrecon"
AUTHOR_URL = "https://kemdi.co"

FONT_FACES = """
@font-face{font-family:"Cormorant Garamond";font-style:normal;font-weight:400;font-display:swap;src:url("{b}cormorant-garamond-latin-400-normal.woff2") format("woff2")}
@font-face{font-family:"Cormorant Garamond";font-style:italic;font-weight:400;font-display:swap;src:url("{b}cormorant-garamond-latin-400-italic.woff2") format("woff2")}
@font-face{font-family:"Cormorant Garamond";font-style:normal;font-weight:500;font-display:swap;src:url("{b}cormorant-garamond-latin-500-normal.woff2") format("woff2")}
@font-face{font-family:"Cormorant Garamond";font-style:italic;font-weight:500;font-display:swap;src:url("{b}cormorant-garamond-latin-500-italic.woff2") format("woff2")}
@font-face{font-family:"Geist";font-style:normal;font-weight:300;font-display:swap;src:url("{b}geist-sans-latin-300-normal.woff2") format("woff2")}
@font-face{font-family:"Geist";font-style:normal;font-weight:400;font-display:swap;src:url("{b}geist-sans-latin-400-normal.woff2") format("woff2")}
@font-face{font-family:"Geist";font-style:normal;font-weight:500;font-display:swap;src:url("{b}geist-sans-latin-500-normal.woff2") format("woff2")}
"""

CSS = """
:root{--paper:#F2F0EA;--ink:#25231F;--ink2:#3A372F;--muted:#A39D90;--soft:#7A7468;--rule:#DDD8CD;--edge:#B9B3A7;--well:#ECE8DF;--field:#FAF8F3;
  --serif:"Cormorant Garamond",Georgia,"Times New Roman",serif;--sans:"Geist",system-ui,-apple-system,"Segoe UI",sans-serif}

/* chrome: no Streamlit header, toolbar, running man, or greyed-out reruns */
header[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stStatusWidget"],
#MainMenu,footer,[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],[data-testid="collapsedControl"]{display:none!important}
[data-stale="true"],.stale-element,[data-testid="stElementContainer"][data-stale="true"]{opacity:1!important;filter:none!important;transition:none!important}
.stApp{background:var(--paper)!important;color:var(--ink)}
.stApp,.stApp p,.stApp li,.stApp label,.stApp input,.stApp textarea,.stApp button,.stApp select,.stMarkdown{font-family:var(--sans)}
.block-container,[data-testid="stMainBlockContainer"]{max-width:1040px!important;padding-top:28px!important;padding-bottom:80px!important}
.stApp p{line-height:1.7}
::selection{background:#E2DDD1}
:focus-visible{outline:2px solid #6a8f7e!important;outline-offset:3px}

/* headings */
.stApp h1,.stApp h2,.stApp h3{font-family:var(--serif)!important;font-weight:400!important;color:var(--ink);letter-spacing:0}
.stApp h3{font-size:26px!important}
[data-testid="stHeaderActionElements"]{display:none!important}

/* buttons: outlined small caps; primary in ink */
.stButton>button,.stDownloadButton>button,[data-testid="stBaseButton-secondary"],[data-testid="stBaseButton-primary"]{
  border-radius:0!important;border:1px solid var(--edge)!important;background:transparent!important;color:var(--ink)!important;
  font-size:11px!important;letter-spacing:.2em;text-transform:uppercase;font-weight:500!important;padding:11px 20px!important;min-height:0!important;box-shadow:none!important}
.stButton>button p,.stDownloadButton>button p{font-size:11px!important;letter-spacing:.2em}
.stButton>button:hover,.stDownloadButton>button:hover{border-color:var(--ink)!important;color:var(--ink)!important}
.stButton>button[kind="primary"],[data-testid="stBaseButton-primary"]{background:var(--ink)!important;color:var(--paper)!important;border-color:var(--ink)!important}
.stButton>button[kind="primary"] p{color:var(--paper)!important}
.stButton>button[kind="primary"]:hover{background:var(--ink2)!important}
.stButton>button:disabled{opacity:.35}

/* fields */
.stApp input,.stApp textarea,[data-baseweb="select"]>div,[data-baseweb="input"]>div,[data-baseweb="base-input"]{border-radius:0!important;background:var(--field)!important;border-color:var(--rule)!important}
[data-baseweb="tag"]{border-radius:0!important;background:var(--ink2)!important}
[data-testid="stWidgetLabel"] p,.stApp label p{font-size:11px!important;letter-spacing:.16em;text-transform:uppercase;color:var(--soft)!important;font-weight:500}
[data-testid="stFileUploaderDropzone"]{border-radius:0!important;background:var(--well)!important;border:1px dashed var(--edge)!important}
[data-testid="stFileUploaderDropzone"] button{border-radius:0!important}
[data-testid="stCheckbox"] label p,[data-testid="stRadio"] label p{text-transform:none!important;letter-spacing:0!important;font-size:14px!important;color:var(--ink)!important}

/* expanders, tabs, alerts, metrics */
[data-testid="stExpander"] details{border:0!important;border-top:1px solid var(--rule)!important;border-bottom:1px solid var(--rule)!important;border-radius:0!important;background:transparent!important}
[data-testid="stExpander"] summary p{font-size:15px}
[data-testid="stExpander"]+[data-testid="stExpander"] details{border-top:0!important}
.stTabs [data-baseweb="tab-list"]{gap:26px;border-bottom:1px solid var(--rule)}
.stTabs [data-baseweb="tab"] p,.stTabs button p,.stTabs [role="tab"] p,.stTabs [role="tab"] div{font-size:11px!important;letter-spacing:.18em;text-transform:uppercase}
.stTabs [data-baseweb="tab-highlight"]{background:var(--ink)!important;height:1px!important}
[data-testid="stAlert"]>div{border-radius:0!important;background:var(--well)!important;color:var(--ink)!important;border-left:2px solid var(--muted)!important}
[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"])>div{border-left-color:#A2741E!important}
[data-testid="stAlert"]:has([data-testid="stAlertContentError"])>div{border-left-color:#8A3B2E!important}
[data-testid="stAlert"]:has([data-testid="stAlertContentInfo"])>div{border-left-color:#6a8f7e!important}
[data-testid="stAlert"] p{color:var(--ink)!important;font-size:14px}
[data-testid="stAlert"] svg{display:none}
[data-testid="stMetric"]{border-top:1px solid var(--rule);padding-top:12px}
[data-testid="stMetricValue"],[data-testid="stMetricValue"] *{font-family:var(--serif)!important;font-size:40px!important;font-weight:400!important;font-variant-numeric:lining-nums tabular-nums}
[data-testid="stMetricLabel"] p{font-size:10px!important;letter-spacing:.18em;text-transform:uppercase;color:var(--muted)!important}
[data-testid="stSpinner"] p,[data-testid="stSpinner"] div{font-family:var(--serif);font-style:italic;font-size:19px;color:var(--soft)}
[data-testid="stCaptionContainer"] p{color:var(--soft)!important;font-size:13px}
[data-testid="stDataFrame"]{border:1px solid var(--rule)}

/* Monogram pieces (markdown HTML) */
.ar-mark{width:112px;height:112px;border-radius:50%;border:1px solid var(--edge);display:grid;place-items:center;margin:0 auto;
  font-family:var(--serif);font-size:42px;letter-spacing:.02em;color:var(--ink2);line-height:1}
.ar-mark i{font-style:italic}
.ar-home{text-align:center;padding:9vh 0 0}
.ar-name{margin:34px 0 0;font-family:var(--sans);font-size:13px;letter-spacing:.32em;text-transform:uppercase;font-weight:500;color:var(--ink)}
.ar-line{margin-top:12px;font-family:var(--serif);font-style:italic;font-size:24px;color:var(--soft)}
.ar-lede{max-width:33em;margin:24px auto 34px;font-size:16px;line-height:1.75;font-weight:300;color:#4A463E}
.ar-where{margin-top:30px;font-size:11px;letter-spacing:.24em;text-transform:uppercase;color:var(--muted)}
.stApp a.ar-caps{font-size:11px;letter-spacing:.22em;text-transform:uppercase;color:var(--ink)!important;text-decoration:none!important;border-bottom:1px solid transparent;padding-bottom:4px}
.stApp a.stApp .ar-intro,.stApp .ar-line,.stApp .ar-note,.stApp .ar-num,.stApp .ar-it,.stApp .ar-pair,.stApp .ar-h,.stApp .ar-mark,.stApp .ar-mini{font-family:var(--serif)!important}
.stApp .ar-name,.stApp .ar-lede,.stApp .ar-ib,.stApp .ar-eyebrow,.stApp .ar-where,.stApp .ar-dl,.stApp .ar-foot,.stApp .ar-steps{font-family:var(--sans)!important}
.ar-links{display:flex;flex-wrap:wrap;justify-content:center;gap:10px 30px;margin-top:6px}
.ar-sec{max-width:660px;margin:12vh auto 0}
.ar-eyebrow{font-size:11px;letter-spacing:.26em;text-transform:uppercase;color:var(--muted)}
.ar-h{font-family:var(--serif);font-weight:400;font-size:clamp(34px,5vw,48px);line-height:1.08;margin:12px 0 10px;color:var(--ink)}
.ar-intro{font-family:var(--serif);font-style:italic;font-size:21px;line-height:1.5;color:#6E685C;margin:0 0 30px}
.ar-item{display:grid;grid-template-columns:54px minmax(0,1fr);gap:0 14px;padding:22px 0;border-top:1px solid var(--rule)}
.ar-item:last-child{border-bottom:1px solid var(--rule)}
.ar-num{font-family:var(--serif);font-style:italic;font-size:22px;color:var(--muted)}
.ar-it{font-family:var(--serif);font-weight:500;font-size:23px;line-height:1.25;margin:0 0 6px;color:var(--ink)}
.ar-ib{font-size:15px;line-height:1.7;font-weight:300;color:#5A564D}
.ar-dl{display:grid;grid-template-columns:150px minmax(0,1fr);gap:14px 24px;margin:8px 0 0;padding-top:22px;border-top:1px solid var(--rule)}
.ar-dl dt{font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:var(--muted);padding-top:3px}
.ar-dl dd{margin:0;font-size:15px;line-height:1.6;font-weight:300;color:var(--ink)}
.ar-foot{max-width:1040px;margin:12vh auto 0;display:flex;justify-content:space-between;flex-wrap:wrap;gap:12px;padding-top:24px;border-top:1px solid var(--rule);
  font-size:10px;letter-spacing:.24em;text-transform:uppercase;color:var(--muted)}
.stApp .ar-foot a{color:var(--muted)!important;text-decoration:none!important;border-bottom:1px solid var(--rule)}
.ar-foot a:hover{color:var(--ink)}
.ar-bar{display:flex;align-items:center;justify-content:space-between;gap:18px;flex-wrap:wrap;padding-bottom:18px;border-bottom:1px solid var(--rule);margin-bottom:8px}
.ar-mini{width:44px;height:44px;border-radius:50%;border:1px solid var(--edge);display:grid;place-items:center;font-family:var(--serif);font-size:18px;color:var(--ink2)}
.ar-mini i{font-style:italic}
.ar-steps{display:flex;flex-wrap:wrap;gap:8px 26px}
.ar-steps span{font-size:11px;letter-spacing:.22em;text-transform:uppercase;color:var(--muted)}
.ar-steps span.on{color:var(--ink);border-bottom:1px solid var(--ink);padding-bottom:5px}
.ar-step{margin:7vh 0 6px}
.ar-step .ar-h{font-size:clamp(30px,4vw,40px)}
.ar-step .ar-intro{font-size:19px;margin-bottom:10px}
.ar-pair{font-family:var(--serif);font-size:26px;margin:34px 0 4px;color:var(--ink)}
.ar-pair i{color:var(--muted)}
.ar-note{font-family:var(--serif);font-style:italic;font-size:17px;color:var(--soft);margin:6px 0 0}

/* home action buttons sit centred under the text */
.st-key-home_actions [data-testid="stHorizontalBlock"]{justify-content:center;gap:12px}
.st-key-home_actions [data-testid="stColumn"]{flex:0 0 auto!important;width:auto!important;min-width:0!important}
.st-key-go_home button{width:44px!important;height:44px!important;border-radius:50%!important;padding:0!important;font-family:var(--serif)!important;
  font-size:18px!important;letter-spacing:0!important;text-transform:none!important}
.st-key-go_home button p{font-family:var(--serif)!important;font-size:18px!important;letter-spacing:0!important;font-style:italic}

@media (max-width:760px){
  .ar-dl{grid-template-columns:minmax(0,1fr);gap:2px}.ar-dl dd{margin-bottom:12px}
  .ar-home{padding-top:6vh}.ar-mark{width:92px;height:92px;font-size:34px}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
"""


def css(font_base: str | None) -> str:
    faces = FONT_FACES.replace("{b}", font_base) if font_base else ""
    return f"<style>{faces}{CSS}</style>"


def esc(s) -> str:
    return html.escape(str(s))


def mark(text: str = "ar", cls: str = "ar-mark") -> str:
    return f'<div class="{cls}" aria-hidden="true"><span>{esc(text[0])}<i>{esc(text[1:])}</i></span></div>'


def home_top(where: str) -> str:
    return (f'<div class="ar-home ar-ready">{mark()}<div class="ar-name">anyrecon</div>'
            '<div class="ar-line">Reconcile any set of documents.</div>'
            '<div class="ar-lede">Add your files, choose which ones should agree, and anyrecon finds the references they share '
            'and matches them line by line. What doesn\'t match is explained, not just listed.</div></div>')


def home_where(where: str, edition: str) -> str:
    return (f'<div style="text-align:center"><div class="ar-links"><a class="ar-caps" href="#how">How it works</a>'
            f'<a class="ar-caps" href="#data">Your data</a><a class="ar-caps" href="{REPO}" target="_blank" rel="noopener">Source</a></div>'
            f'<div class="ar-where">{esc(edition)} edition · {esc(where)}</div></div>')


def home_sections(edition: str, browser: bool) -> str:
    steps = [
        ("Add your documents", "Processor exports, ledgers, bank statements, settlement reports. CSV, Excel, JSON and PDF"
         + ("" if browser else ", including scans") + ". Workbooks with several tabs are fine."),
        ("Choose what should agree", "Pick the pairs, such as processor and bank, or ledger and processor. Three or more documents "
         "are linked into one view of each transaction."),
        ("It finds the shared references", "Even when they look different on each side: a reference with a prefix, missing zeros, "
         "or buried in a bank narration. You see the options, ranked, with examples, and choose."),
        ("Review what doesn't match", "Missing items, amount differences, timing, duplicates and likely typos, each with a reason. "
         "Patterns such as a fee taken at settlement are called out. Download the report and an audit trail."),
    ]
    items = "".join(f'<div class="ar-item"><div class="ar-num">{i:02d}</div><div><div class="ar-it">{esc(t)}</div><div class="ar-ib">{esc(b)}</div></div></div>'
                    for i, (t, b) in enumerate(steps, 1))
    where = ("In this browser tab. Files are read here and are never uploaded." if browser
             else "On this computer." if edition == "Desktop" else "On your organisation's server.")
    facts = [("Where it runs", where),
             ("Card numbers", "Masked automatically to the first six and last four digits. Security codes and PIN data are removed."),
             ("What is kept", "Nothing. Close the tab, or clear the session, and it is gone."),
             ("Matching", "Done by fixed rules you can see, not guessed. Every match records the rule that made it.")]
    dl = "".join(f"<dt>{esc(a)}</dt><dd>{esc(b)}</dd>" for a, b in facts)
    return (f'<section class="ar-sec" id="how"><div class="ar-eyebrow">How it works</div><h2 class="ar-h">Four steps.</h2>'
            f'<div class="ar-intro">No setup, no accounts, nothing to install.</div>{items}</section>'
            f'<section class="ar-sec" id="data"><div class="ar-eyebrow">Your data</div><h2 class="ar-h">It stays with you.</h2>'
            f'<dl class="ar-dl">{dl}</dl></section>')


def footer(version: str, edition: str) -> str:
    return (f'<footer class="ar-foot"><span>anyrecon · {esc(edition)} edition · v{esc(version)}</span>'
            f'<span>A project by <a href="{AUTHOR_URL}" target="_blank" rel="noopener">Kemdi Okoli</a> · '
            f'<a href="{REPO}" target="_blank" rel="noopener">Source</a></span></footer>')


def steps_bar(active: int) -> str:
    names = ["Documents", "Pairs", "Rules", "Results"]
    return '<div class="ar-steps ar-ready">' + "".join(
        f'<span class="{"on" if i == active else ""}">{n}</span>' for i, n in enumerate(names, 1)) + "</div>"


def step_head(n: int, title: str, intro: str = "") -> str:
    return (f'<div class="ar-step"><div class="ar-eyebrow">{n:02d}</div><h2 class="ar-h">{esc(title)}</h2>'
            + (f'<div class="ar-intro">{esc(intro)}</div>' if intro else "") + "</div>")


def pair_head(left: str, right: str) -> str:
    return f'<div class="ar-pair">{esc(left)} <i>and</i> {esc(right)}</div>'
