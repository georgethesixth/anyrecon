"""anyrecon web UI.   Run locally:  streamlit run app.py

Local mode (default): files stay on your machine.
Demo mode (ANYRECON_DEMO=1): uploads disabled, only bundled synthetic data. Use this for any
public deployment so the hosted app can never receive real card or customer data.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import tempfile
from itertools import combinations
from pathlib import Path

if sys.platform == "emscripten":   # Browser edition: pure-Python wheels bundled without their unused native deps
    for _w in sorted(Path("wheels").glob("*.whl")):
        if str(_w.resolve()) not in sys.path:
            sys.path.insert(0, str(_w.resolve()))

import pandas as pd
import streamlit as st

from anyrecon import __version__, llm
from anyrecon import templates as tpl
from anyrecon.chain import auto_config, run_all
from anyrecon.discover import discover
from anyrecon.ingest import UnreadableFile, list_sheets, load, load_each_sheet
from anyrecon.match import KeySpec
from anyrecon.pci import PCIBlocked
from anyrecon.profile import profile
from anyrecon.report import audit_json, write_excel

import ui_theme as ui

DEMO = os.environ.get("ANYRECON_DEMO") == "1"
BROWSER = sys.platform == "emscripten"
EDITION = "Browser" if BROWSER else os.environ.get("ANYRECON_EDITION", "Desktop").title()
WHERE = {"Browser": "Runs inside this browser tab. Files are never uploaded.",
         "Desktop": "Runs on this computer only.",
         "Server": "Hosted by your organisation."}.get(EDITION, "")
SAMPLES = Path(__file__).parent / "examples" / "data"
SAMPLE_FILES = [("processor", "processor.csv"), ("ledger", "ledger.xlsx"), ("bank", "bank_statement.pdf"),
                ("settlement", "settlement_report.json")] + ([] if BROWSER else [("scan", "scanned_statement.png")])

st.set_page_config(page_title="anyrecon", page_icon="◯", layout="wide", initial_sidebar_state="collapsed")
# Browser edition: fonts are declared by the page itself (same origin). Desktop/Server: served by Streamlit's static folder.
st.markdown(ui.css(None if BROWSER else "app/static/fonts/"), unsafe_allow_html=True)

ss = st.session_state
ss.setdefault("view", "home")
ss.setdefault("datasets", {})
ss.setdefault("uploads", {})       # name -> (filename, bytes): held in memory only, never written to disk
ss.setdefault("overrides", {})     # name -> {"mask": [...], "keep": [...]}
ss.setdefault("sheet_mode", {})    # name -> ("largest"|"sheet"|"stack"|"each", sheet)
ss.setdefault("pci_mode", "strict")
ss.setdefault("window", 3)
ss.setdefault("tol", 0.01)


def _from_bytes(name, filename, data, sheet_mode, ov):
    """Write to a private temp file only for the duration of parsing, then delete it."""
    suffix = Path(filename).suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as fh:
        fh.write(data)
        tmp = Path(fh.name)
    try:
        kw = dict(pci_mode=ss.pci_mode, mask_columns=ov.get("mask", []), keep_columns=ov.get("keep", []))
        mode, sheet = sheet_mode
        if mode == "each":
            return {d.name: d for d in load_each_sheet(tmp, name=name, **kw)}
        sh = {"largest": None, "stack": "*", "sheet": sheet}[mode]
        ds = load(tmp, name=name, sheet=sh, **kw)
        ds.source = filename
        return {name: ds}
    finally:
        tmp.unlink(missing_ok=True)


def _load_samples():
    if all((SAMPLES / f).exists() for _, f in SAMPLE_FILES):
        ss.uploads = {n: (f, (SAMPLES / f).read_bytes()) for n, f in SAMPLE_FILES}
    else:   # generate into a throwaway folder (works on read-only installs), keep in memory only
        import shutil
        from examples.generate_samples import main as gen
        tmp = Path(tempfile.mkdtemp(prefix="anyrecon_samples_"))
        try:
            gen(out=tmp)
            ss.uploads = {n: (f, (tmp / f).read_bytes()) for n, f in SAMPLE_FILES}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    ss.using_samples = True


def _clear():
    for k in list(ss.keys()):
        del ss[k]


# ---------------------------------------------------------------- landing
if ss.view == "home":
    st.markdown(ui.home_top(WHERE), unsafe_allow_html=True)
    with st.container(key="home_actions"):
        if DEMO:
            if st.button("Try it with sample data", type="primary", key="try"):
                _load_samples(); ss.view = "work"; st.rerun()
        else:
            c1, c2 = st.columns(2)
            if c1.button("Start reconciling", type="primary", key="start"):
                ss.view = "work"; st.rerun()
            if c2.button("Try with sample data", key="try"):
                _load_samples(); ss.view = "work"; st.rerun()
    st.markdown(ui.home_where(WHERE, EDITION), unsafe_allow_html=True)
    st.markdown(ui.home_sections(EDITION, BROWSER), unsafe_allow_html=True)
    st.markdown(ui.footer(__version__, EDITION), unsafe_allow_html=True)
    st.stop()

# ---------------------------------------------------------------- work area
stage = 4 if "results" in ss else 3 if ss.get("pairs_sel") else 2 if len(ss.datasets) >= 2 else 1
b1, b2, b3 = st.columns([1, 9, 2], vertical_alignment="center")
if b1.button("ar", key="go_home", help="Back to the start page"):
    ss.view = "home"; st.rerun()
b2.markdown(ui.steps_bar(stage), unsafe_allow_html=True)
if b3.button("Clear all", key="clear", help="Remove every file and result from this session"):
    _clear(); st.rerun()

st.markdown(ui.step_head(1, "Your documents", "Add two or more. CSV, Excel, JSON or PDF"
                         + ("." if BROWSER else ", including scans and photos.")), unsafe_allow_html=True)
if DEMO:
    st.info("Public demo: uploads are switched off. You're looking at synthetic sample data.")
    if not ss.uploads:
        _load_samples()
else:
    types = ["csv", "tsv", "txt", "xlsx", "xlsm", "xls", "json", "pdf"] + ([] if BROWSER else ["png", "jpg", "jpeg", "tif", "tiff"])
    ups = st.file_uploader("Add files", accept_multiple_files=True, type=types,
                           help="Scanned documents need the Desktop or Server edition." if BROWSER else None)
    if ups:
        ss.uploads = {Path(u.name).stem.replace(" ", "_")[:24]: (u.name, u.getvalue()) for u in ups}
        ss.using_samples = False
    elif not ss.get("using_samples"):
        ss.uploads = {}
    if not ups and not ss.get("using_samples") and st.button("Use sample data instead", key="try2"):
        _load_samples(); st.rerun()

with st.expander("Settings"):
    s1, s2, s3 = st.columns(3)
    s1.selectbox("Card data", ["strict", "paranoid", "block"], key="pci_mode",
                 help="strict: mask card numbers, remove security codes and PIN data. paranoid: also mask "
                      "card-number-shaped references. block: refuse files that contain card data.")
    s2.number_input("Date window (days)", 0, 30, key="window")
    s3.number_input("Amount tolerance", 0.0, 1000.0, step=0.01, key="tol")
    if not BROWSER:
        st.caption("AI commentary: " + ("on" if llm.available() else "off"))
pci_mode, window, tol = ss.pci_mode, ss.window, ss.tol

if not ss.uploads:
    st.markdown('<p class="ar-note">Nothing added yet.</p>', unsafe_allow_html=True)
    st.markdown(ui.footer(__version__, EDITION), unsafe_allow_html=True)
    st.stop()

datasets = {}
for name, (filename, data) in ss.uploads.items():
    if filename.lower().endswith((".xlsx", ".xlsm", ".xls")):
        with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix, delete=False) as fh:
            fh.write(data)
        try:
            sheets = [x for x in list_sheets(fh.name) if not x["hidden"] and x["rows"] >= 2]
        finally:
            Path(fh.name).unlink(missing_ok=True)
        if len(sheets) > 1:
            c1, c2 = st.columns([2, 1])
            choice = c1.radio(f"**{filename}** has {len(sheets)} sheets: " + ", ".join(f"{x['name']} ({x['rows']} rows)" for x in sheets),
                              ["Use the sheet with most data", "Use one sheet", "Stack sheets with the same columns (e.g. monthly tabs)",
                               "Treat each sheet as its own document"], key=f"sm_{name}", horizontal=False)
            sheet = c2.selectbox("Sheet", [x["name"] for x in sheets], key=f"sh_{name}") if choice == "Use one sheet" else None
            ss.sheet_mode[name] = ({"Use the sheet with most data": "largest", "Use one sheet": "sheet",
                                    "Stack sheets with the same columns (e.g. monthly tabs)": "stack",
                                    "Treat each sheet as its own document": "each"}[choice], sheet)
    mode = ss.sheet_mode.get(name, ("largest", None))
    ov = ss.overrides.get(name, {})
    ck = f"ds_{hashlib.sha256(data).hexdigest()[:12]}_{mode}_{sorted(ov.get('mask', []))}_{sorted(ov.get('keep', []))}_{pci_mode}"
    try:
        if ck not in ss:
            with st.spinner(f"Reading {filename}…"):
                ss[ck] = _from_bytes(name, filename, data, mode, ov)
        datasets.update(ss[ck])
    except PCIBlocked as e:
        st.error(f"Blocked: {e}")
    except UnreadableFile as e:
        st.error(str(e))
ss.datasets = datasets
if len(datasets) < 2:
    st.markdown('<p class="ar-note">Add at least one more document to continue.</p>', unsafe_allow_html=True)
    st.markdown(ui.footer(__version__, EDITION), unsafe_allow_html=True)
    st.stop()

handled = [(d.name, f) for d in datasets.values() for f in d.findings if f.kind != "MASKED_PAN"]
if handled:
    n_masked = sum(f.count for _, f in handled if f.kind.startswith("PAN") and f.kind != "PAN_EXEMPT")
    n_dropped = sum(1 for _, f in handled if f.kind.startswith("SAD") and f.action == "dropped")
    n_review = sum(1 for _, f in handled if f.review)
    st.warning(f"Card data protected automatically: {n_masked} card number(s) masked to first 6 / last 4, "
               f"{n_dropped} card-security column(s) removed." + (f" **{n_review} item(s) need your decision below.**" if n_review else ""))

for name, ds in datasets.items():
    base = name.split(":")[0]
    flag = " · ⚠ needs review" if any(f.review for f in ds.findings) or ds.warnings else (" · card data protected" if ds.findings else "")
    with st.expander(f"**{name}** · {ds.fmt} · {len(ds)} rows{flag}", expanded=bool(ds.warnings or any(f.review for f in ds.findings))):
        for w in ds.warnings:
            st.error(w)
        for n in ds.notes:
            st.caption("• " + n)
        for f in ds.findings:
            st.warning(f"**{f.column}**: {f.kind} → {f.action} ({f.count}). {f.detail}")
            ov = ss.overrides.setdefault(base, {"mask": [], "keep": []})
            if f.review == "can_mask":
                if st.checkbox(f"Mask '{f.column}' anyway", key=f"mask_{name}_{f.column}"):
                    if f.column not in ov["mask"]:
                        ov["mask"].append(f.column)
                        st.rerun()
            if f.review == "can_keep":
                if st.checkbox(f"I confirm '{f.column}' is NOT a card security code / PIN block: restore it",
                               key=f"keep_{name}_{f.column}"):
                    if f.column not in ov["keep"]:
                        ov["keep"].append(f.column)
                        st.rerun()
        st.dataframe(ds.df[[c for c in ds.df.columns if not c.startswith("__") or c == "__ocr_conf"]].head(15), width="stretch")
        prof = pd.DataFrame([p.as_dict() for p in profile(ds).values()])[["name", "kind", "semantic", "uniqueness", "top_shape", "date_format", "note"]]
        st.dataframe(prof, width="stretch", hide_index=True)

# ---------------------------------------------------------------- 2. pairs
st.markdown(ui.step_head(2, "What should agree with what?", "Pick one or more pairs. Three or more documents are "
                         "linked into one view of each transaction."), unsafe_allow_html=True)
names = list(ss.datasets)
options = [f"{a} ⟷ {b}" for a, b in combinations(names, 2)]
pairs = st.multiselect("Pairs", options, default=options[:1])
ss.pairs_sel = bool(pairs)
with st.expander("Use a saved setup"):
    tmpl_file = st.file_uploader("Saved setup (JSON)", type=["json"], key="tmpl")

configs = []
if tmpl_file:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as fh:
        fh.write(tmpl_file.getvalue())
    try:
        configs, expected = tpl.load(fh.name)
    finally:
        Path(fh.name).unlink(missing_ok=True)
    for w in tpl.check(ss.datasets, expected):
        st.warning(w)
    st.success(f"Template loaded: {len(configs)} pair(s).")
else:
    # ---------------------------------------------------------------- 3. identifiers
    st.markdown(ui.step_head(3, "How they match", "The best options are already chosen. Change them if you know better."),
                unsafe_allow_html=True)
    for pr in pairs:
        l, r = pr.split(" ⟷ ")
        L, R = ss.datasets[l], ss.datasets[r]
        ck = f"cands_{l}_{r}_{L.file_sha256[:8]}_{R.file_sha256[:8]}_{window}"
        if ck not in ss:
            ss[ck] = auto_config(L, R, date_window_days=window)
        base_cfg, cands = ss[ck]
        st.markdown(ui.pair_head(l, r), unsafe_allow_html=True)
        if not cands:
            st.error("No shared identifier or amount/date pattern found. Check the files or choose different pairs.")
            continue
        table = pd.DataFrame([dict(rank=i + 1, rule=c.describe(), score=c.score, **{f"% of {l} found": round(100 * c.cov_left, 1),
                                    f"% of {r} found": round(100 * c.cov_right, 1)},
                                    example=" ⟷ ".join(map(str, c.examples[0])) if c.examples else "")
                               for i, c in enumerate(cands)])
        st.dataframe(table, hide_index=True, width="stretch")
        labels = [f"{i + 1}. {c.describe()}" for i, c in enumerate(cands)]
        key_cands = [i for i, c in enumerate(cands) if c.mode != "composite"]
        default_keys = [labels[i] for i in key_cands if any(k.left_col == cands[i].left_col and k.right_col == cands[i].right_col
                                                             and k.mode == cands[i].mode for k in base_cfg.keys)]
        chosen = st.multiselect("Keys to use, in priority order (each runs as a tier on rows still unmatched)",
                                [labels[i] for i in key_cands], default=default_keys, key=f"k_{pr}")
        c1, c2, c3, c4 = st.columns(4)
        lcols, rcols = ["(none)"] + L.columns, ["(none)"] + R.columns

        def pick(col, cols, cur, label, key):
            return col.selectbox(label, cols, index=cols.index(cur) if cur in cols else 0, key=f"{key}_{pr}")
        la = pick(c1, lcols, base_cfg.left_amount, f"{l} amount", "la")
        ra = pick(c2, rcols, base_cfg.right_amount, f"{r} amount", "ra")
        ld = pick(c3, lcols, base_cfg.left_date, f"{l} date", "ld")
        rd = pick(c4, rcols, base_cfg.right_date, f"{r} date", "rd")
        c5, c6, c7 = st.columns(3)
        fee = c5.number_input(f"Fee % deducted in {r}", 0.0, 20.0, 0.0, step=0.05, key=f"fee_{pr}")
        tol_pct = c6.number_input("Amount tolerance %", 0.0, 10.0, 0.0, step=0.1, key=f"tp_{pr}")
        comp = c7.checkbox("Amount + date fallback", True, key=f"comp_{pr}", help="When no shared reference exists, match on amount and date.")
        cfg = auto_config(L, R, date_window_days=window, candidates=cands)[0]
        cfg.keys = [KeySpec(cands[labels.index(x)].left_col, cands[labels.index(x)].right_col, cands[labels.index(x)].left_tf,
                            cands[labels.index(x)].right_tf, cands[labels.index(x)].mode) for x in chosen]
        cfg.left_amount, cfg.right_amount = (None if la == "(none)" else la), (None if ra == "(none)" else ra)
        cfg.left_date, cfg.right_date = (None if ld == "(none)" else ld), (None if rd == "(none)" else rd)
        cfg.expected_fee_pct, cfg.amount_tol_pct, cfg.use_composite, cfg.amount_tol = fee, tol_pct, comp, tol
        configs.append(cfg)

# ---------------------------------------------------------------- 4. run
st.markdown(ui.step_head(4, "Results"), unsafe_allow_html=True)
if st.button("Reconcile", type="primary", disabled=not configs, key="run"):
    with st.spinner("Matching…"):
        results, chain = run_all(ss.datasets, configs)
    ss.results, ss.chain, ss.configs = results, chain, configs
    st.rerun()

if "results" in ss:
    results, chain = ss.results, ss.chain
    for k, r in results.items():
        s = r.summary
        st.markdown(ui.pair_head(r.config.left, r.config.right), unsafe_allow_html=True)
        m = st.columns(5)
        m[0].metric("Matched groups", s["matched_groups"])
        m[1].metric("With variance", s["exception_groups"])
        m[2].metric(f"{r.config.left} matched", f"{s['left_match_rate_pct']}%")
        m[3].metric(f"{r.config.right} matched", f"{s['right_match_rate_pct']}%")
        m[4].metric("Value matched", f"{s['left_value_matched_pct']}%" if s["left_value_matched_pct"] is not None else "–")
        for i in r.insights:
            st.info(i)
        t1, t2, t3, t4 = st.tabs(["Exceptions", "Matches", f"Only in {r.config.left}", f"Only in {r.config.right}"])
        t1.dataframe(r.exceptions, width="stretch", hide_index=True)
        t2.dataframe(r.matches, width="stretch", hide_index=True)
        t3.dataframe(r.left_unmatched, width="stretch", hide_index=True)
        t4.dataframe(r.right_unmatched, width="stretch", hide_index=True)
    if chain is not None:
        st.markdown(f'<div class="ar-pair">Across all documents <i>· one row per {ui.esc(chain.anchor.iloc[0])} item</i></div>',
                    unsafe_allow_html=True)
        st.bar_chart(chain.status.value_counts(), color="#3A372F")
        st.dataframe(chain, width="stretch", hide_index=True)
    if llm.available() and st.button("Explain these results (AI)"):
        st.write(llm.explain(results))
    buf = io.BytesIO()
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as fh:
        write_excel(fh.name, ss.datasets, results, chain)
        buf.write(Path(fh.name).read_bytes())
    Path(fh.name).unlink(missing_ok=True)
    d1, d2, d3 = st.columns(3)
    d1.download_button("Excel report", buf.getvalue(), "recon_report.xlsx")
    d2.download_button("Audit trail (JSON)", json.dumps(audit_json(ss.datasets, results), indent=2, default=str), "recon_audit.json")
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as fh:
        pass
    tpl.save(fh.name, ss.datasets, ss.configs)
    d3.download_button("Save setup as template", Path(fh.name).read_text(), "recon_template.json")
    Path(fh.name).unlink(missing_ok=True)

st.markdown(ui.footer(__version__, EDITION), unsafe_allow_html=True)
