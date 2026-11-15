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
from anyrecon.chain import auto_config, auto_pairs, run_all
from anyrecon.discover import discover
from anyrecon.ingest import UnreadableFile, list_sheets, load, load_each_sheet
from anyrecon.match import KeySpec
from anyrecon.pci import PCIBlocked
from anyrecon.profile import pick_amount, pick_date, profile
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
st.markdown(ui.css(), unsafe_allow_html=True)

ss = st.session_state
# Browser edition: the page already showed the landing (static HTML) while Python loaded, so open on the work view.
ss.setdefault("view", "work" if BROWSER else "home")
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

def _rule_line(cfg):
    keys = []
    for k in cfg.keys:
        keys.append(f"{k.left_col} = {k.right_col}" if k.mode == "key" else f"{k.left_col} found in {k.right_col}"
                    if k.mode == "extract_right" else f"{k.right_col} found in {k.left_col}" if k.mode == "extract_left"
                    else f"{k.left_col} ~ {k.right_col}")
    parts = ["Matched on " + (", then ".join(keys) if keys else "amount and date")]
    if cfg.expected_fee_pct:
        parts.append(f"{cfg.expected_fee_pct:g}% fee deducted in {cfg.right} (detected)")
    return " · ".join(parts)


# ---------------------------------------------------------------- work area
# Simple (default): add files → results. Pairs, rules and fees are worked out automatically and the
# reconciliation runs by itself. Advanced shows every choice.
ss.setdefault("advanced", False)
with st.container(key="topbar"):
    b1, b2 = st.columns([1, 1], vertical_alignment="center")
    if b1.button("anyrecon", key="go_home", help="Back to the start page"):
        ss.view = "home"; st.rerun()
    with b2.container(key="tools", horizontal=True, horizontal_alignment="right", vertical_alignment="center"):
        st.toggle("Advanced", key="advanced", help="Choose the pairs, matching rules, sheets and card-data mode yourself")
        if st.button("Clear all", key="clear", help="Remove every file and result from this session"):
            _clear(); ss.view = "work"; st.rerun()
st.markdown('<span class="ar-ready"></span>', unsafe_allow_html=True)
ADV = ss.advanced

if ADV:
    st.markdown(ui.step_head(1, "Documents"), unsafe_allow_html=True)
types = ["csv", "tsv", "txt", "xlsx", "xlsm", "xls", "json", "pdf"] + ([] if BROWSER else ["png", "jpg", "jpeg", "tif", "tiff"])
if DEMO:
    st.info("Public demo: uploads are switched off. You're looking at synthetic sample data.")
    if not ss.uploads:
        _load_samples()
else:
    ups = st.file_uploader("Add your files: two or more. CSV, Excel, JSON or PDF" + ("" if BROWSER else ", or scans") + ".",
                           accept_multiple_files=True, type=types,
                           help="Scanned documents need the Desktop or Server edition." if BROWSER else None)
    if ups:
        ss.uploads = {Path(u.name).stem.replace(" ", "_")[:24]: (u.name, u.getvalue()) for u in ups}
        ss.using_samples = False
    elif not ss.get("using_samples"):
        ss.uploads = {}
    if not ups and not ss.get("using_samples") and st.button("Use sample data", key="try2"):
        _load_samples(); st.rerun()

if ADV:
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
    st.markdown(ui.footer(__version__, EDITION), unsafe_allow_html=True)
    st.stop()

datasets = {}
for name, (filename, data) in ss.uploads.items():
    if ADV and filename.lower().endswith((".xlsx", ".xlsm", ".xls")):
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

# file cards: what was read, which columns hold the amount and date, card data handled, preview
prof_cache = ss.setdefault("prof", {})


def _roles(n, d):
    k = (n, d.file_sha256, len(d))
    if k not in prof_cache:
        p = profile(d)
        prof_cache[k] = (pick_amount(p), pick_date(p))
    return prof_cache[k]


if datasets:
    st.markdown('<div class="ar-h3">Your files</div>', unsafe_allow_html=True)
    items, per = list(datasets.items()), 5
    for i in range(0, len(items), per):
        cols = st.columns(per)
        for col, (name, ds) in zip(cols, items[i:i + per]):
            am, dt = _roles(name, ds)
            masked = sum(f.count for f in ds.findings if f.kind.startswith("PAN") and f.kind != "PAN_EXEMPT")
            dropped = sum(1 for f in ds.findings if f.kind.startswith("SAD") and f.action == "dropped")
            note = ", ".join(x for x in [f"{masked:,} card numbers masked" if masked else "",
                                         f"{dropped} security column{'s' if dropped != 1 else ''} removed" if dropped else ""] if x)
            needs = bool(ds.warnings or any(f.review for f in ds.findings))
            with col, st.container(key=f"fcard_{i}_{name}"):
                st.markdown(ui.file_card(name, ds.fmt, len(ds), len(ds.columns), am, dt, note, needs), unsafe_allow_html=True)
                with st.popover("Preview", use_container_width=True):
                    st.caption(f"{ds.source or name} · first 20 of {len(ds):,} rows" + (" · card numbers already masked" if masked else ""))
                    st.dataframe(ds.df[[c for c in ds.df.columns if not c.startswith("__")]].head(20), width="stretch", hide_index=True)

for name, ds in datasets.items():
    needs = bool(ds.warnings or any(f.review for f in ds.findings))
    if not (ADV or needs):
        continue
    base = name.split(":")[0]
    flag = " · ⚠ needs your decision" if needs else (" · card data protected" if ds.findings else "")
    with st.expander(f"**{name}** · {ds.fmt} · {len(ds)} rows{flag}", expanded=needs):
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
        if ADV:
            st.dataframe(ds.df[[c for c in ds.df.columns if not c.startswith("__") or c == "__ocr_conf"]].head(15), width="stretch")
            prof = pd.DataFrame([p.as_dict() for p in profile(ds).values()])[["name", "kind", "semantic", "uniqueness", "top_shape", "date_format", "note"]]
            st.dataframe(prof, width="stretch", hide_index=True)

if len(datasets) < 2:
    st.markdown('<p class="ar-note">Add at least one more file to reconcile.</p>', unsafe_allow_html=True)
    st.markdown(ui.footer(__version__, EDITION), unsafe_allow_html=True)
    st.stop()

# ---------------------------------------------------------------- pairs and rules
names = list(ss.datasets)
cache = ss.setdefault("cands", {})


def cands_for(a, b):
    k = (a, b, ss.datasets[a].file_sha256, ss.datasets[b].file_sha256, len(ss.datasets[a]), len(ss.datasets[b]), window)
    if k not in cache:
        cache[k] = discover(ss.datasets[a], ss.datasets[b], date_window_days=window)
    return cache[k]


with st.spinner("Working out how your files link…"):
    cmap = {(a, b): cands_for(a, b) for a, b in combinations(names, 2)}
    auto = auto_pairs(ss.datasets, cmap, date_window_days=window)

configs = []
if not ADV:
    def _okey(a, b):
        return (a, b) if (a, b) in cmap else (b, a)

    def _build(conn):
        a, b = _okey(conn["a"], conn["b"])
        L, R, c = ss.datasets[a], ss.datasets[b], cmap[_okey(conn["a"], conn["b"])]
        cfg = auto_config(L, R, date_window_days=window, candidates=c)[0]
        cfg.amount_tol = tol
        cand = None
        if conn["ci"] is not None and conn["ci"] < len(c):
            cand = c[conn["ci"]]
            if cand.mode == "composite":
                cfg.keys, cfg.use_composite = [], True
            else:
                cfg.keys = [KeySpec(cand.left_col, cand.right_col, cand.left_tf, cand.right_tf, cand.mode)]
        else:
            k0 = cfg.keys[0] if cfg.keys else None
            cand = next((x for x in c if k0 and x.mode == k0.mode and x.left_col == k0.left_col and x.right_col == k0.right_col), None) \
                or next((x for x in c if x.mode == "composite"), None)
        return a, b, cfg, cand

    dsig = "|".join(f"{n}:{d.file_sha256}:{len(d)}" for n, d in ss.datasets.items()) + f"|{window}"
    if ss.get("conns_for") != dsig:
        ss.conns, ss.conns_for, ss.editing = [{"a": a, "b": b, "ci": None} for a, b in auto], dsig, None
    built = [_build(c) for c in ss.conns]
    csig = hashlib.sha256((dsig + json.dumps([(c["a"], c["b"], c["ci"]) for c in ss.conns])).encode()).hexdigest()
    confirmed = ss.get("confirmed") == csig

    head = (f"How your files connect · {len(ss.conns)} connection{'s' if len(ss.conns) != 1 else ''} confirmed"
            if confirmed else None)
    box = st.expander(head, expanded=False) if confirmed else st.container()
    with box:
        if not confirmed:
            st.markdown('<div class="ar-h3">How your files connect</div><p class="ar-sub">Proposed from the data. '
                        'Check each match, change any that look wrong, then confirm.</p>', unsafe_allow_html=True)
        edges = []
        for a, b, cfg, cand in built:
            if cand is None:
                continue
            pct = 100 * (cand.cov_left if len(ss.datasets[a]) <= len(ss.datasets[b]) else cand.cov_right)
            lab = "amount + date" if cand.mode == "composite" else (cand.left_col if cand.mode != "extract_left" else cand.right_col)
            card = (lambda u: "1" if u >= 0.98 else "*")
            edges.append((a, b, str(lab)[:18], pct, card(cand.uniq_left) if cand.mode != "composite" else "*",
                          card(cand.uniq_right) if cand.mode != "composite" else "*"))
        st.markdown(ui.graph_svg([(n, len(d)) for n, d in ss.datasets.items()], edges), unsafe_allow_html=True)
        if not ss.conns:
            st.error("These files don't share a reference, or an amount and date pattern. Add a connection below or use Advanced.")

        grid = st.columns(2)
        for i, (conn, (a, b, cfg, cand)) in enumerate(zip(ss.conns, built)):
            with grid[i % 2]:
                L, R = ss.datasets[a], ss.datasets[b]
                if cand is None:
                    st.markdown(ui.conn_card(a, b, "No shared reference found for this pair.", 0, 0, len(L), len(R), []), unsafe_allow_html=True)
                else:
                    note = ("Then by amount and date for anything left over." if cfg.use_composite and cand.mode != "composite" else "")
                    st.markdown(ui.conn_card(a, b, _rule_line(cfg), round(cand.cov_left * len(L)), round(cand.cov_right * len(R)),
                                             len(L), len(R), cand.examples if cand.mode != "composite" else [], note),
                                unsafe_allow_html=True)
                with st.container(key=f"conn_btns_{i}", horizontal=True):
                    if st.button("Done" if ss.editing == i else "Change", key=f"edit_{i}"):
                        ss.editing = None if ss.editing == i else i; st.rerun()
                    if st.button("Remove", key=f"rm_{i}"):
                        ss.conns.pop(i); ss.editing = None; st.rerun()
                if ss.editing == i:
                    e1, e2 = st.columns(2)
                    na = e1.selectbox("Connect", names, index=names.index(conn["a"]), key=f"ca_{i}")
                    nb = e2.selectbox("with", [x for x in names if x != na],
                                      index=max(0, [x for x in names if x != na].index(conn["b"])) if conn["b"] != na else 0, key=f"cb_{i}")
                    if (na, nb) != (conn["a"], conn["b"]):
                        ss.conns[i] = {"a": na, "b": nb, "ci": None}; st.rerun()
                    c = cmap[_okey(na, nb)]
                    if c:
                        L2, R2 = ss.datasets[_okey(na, nb)[0]], ss.datasets[_okey(na, nb)[1]]
                        opts = [f"{x.describe()}  ·  {round(100 * min(x.cov_left, x.cov_right))}% match" for x in c]
                        cur = c.index(cand) if cand in c else 0
                        pick = st.selectbox("Match on", opts, index=cur, key=f"ci_{i}_{na}_{nb}")
                        if opts.index(pick) != cur:
                            ss.conns[i]["ci"] = opts.index(pick); st.rerun()
                    else:
                        st.warning("No usable match between these two files.")
        free = [(a, b) for a, b in combinations(names, 2)
                if cmap[(a, b)] and not any({a, b} == {c["a"], c["b"]} for c in ss.conns)]
        f1, f2 = st.columns([1, 1])
        if free and f1.button("Add a connection", key="add_conn"):
            ss.conns.append({"a": free[0][0], "b": free[0][1], "ci": None}); ss.editing = len(ss.conns) - 1; st.rerun()
        if not confirmed and ss.conns:
            if st.button("Confirm and reconcile", type="primary", key="confirm", use_container_width=True):
                ss.confirmed = csig; ss.editing = None; st.rerun()

    if not confirmed:
        st.markdown(ui.footer(__version__, EDITION), unsafe_allow_html=True)
        st.stop()
    seen = set()
    for a, b, cfg, cand in built:
        if cand is not None and (a, b) not in seen:
            seen.add((a, b)); configs.append(cfg)
else:
    st.markdown(ui.step_head(2, "Pairs", "Chosen automatically. Add or remove pairs."), unsafe_allow_html=True)
    options = [f"{a} ⟷ {b}" for a, b in combinations(names, 2)]
    pairs = st.multiselect("Pairs", options, default=[f"{a} ⟷ {b}" for a, b in auto] or options[:1])
    with st.expander("Use a saved setup"):
        tmpl_file = st.file_uploader("Saved setup (JSON)", type=["json"], key="tmpl")
    if tmpl_file:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as fh:
            fh.write(tmpl_file.getvalue())
        try:
            configs, expected = tpl.load(fh.name)
        finally:
            Path(fh.name).unlink(missing_ok=True)
        for w in tpl.check(ss.datasets, expected):
            st.warning(w)
        st.success(f"Saved setup loaded: {len(configs)} pair(s).")
    else:
        st.markdown(ui.step_head(3, "Rules", "Best options are pre-selected."), unsafe_allow_html=True)
        for pr in pairs:
            l, r = pr.split(" ⟷ ")
            L, R = ss.datasets[l], ss.datasets[r]
            cands = cmap.get((l, r)) or cands_for(l, r)
            base_cfg = auto_config(L, R, date_window_days=window, candidates=cands)[0]
            st.markdown(ui.pair_head(l, r), unsafe_allow_html=True)
            if not cands:
                st.error("No shared identifier or amount/date pattern found.")
                continue
            labels = [f"{i + 1}. {c.describe()}" for i, c in enumerate(cands)]
            key_cands = [i for i, c in enumerate(cands) if c.mode != "composite"]
            default_keys = [labels[i] for i in key_cands if any(k.left_col == cands[i].left_col and k.right_col == cands[i].right_col
                                                                 and k.mode == cands[i].mode for k in base_cfg.keys)]
            chosen = st.multiselect("Match on (in priority order)", [labels[i] for i in key_cands], default=default_keys, key=f"k_{pr}")
            with st.expander("All candidate identifiers"):
                st.dataframe(pd.DataFrame([dict(rank=i + 1, rule=c.describe(), score=c.score,
                                                **{f"% of {l} found": round(100 * c.cov_left, 1), f"% of {r} found": round(100 * c.cov_right, 1)},
                                                example=" ⟷ ".join(map(str, c.examples[0])) if c.examples else "")
                                           for i, c in enumerate(cands)]), hide_index=True, width="stretch")
            c1, c2, c3, c4 = st.columns(4)
            lcols, rcols = ["(none)"] + L.columns, ["(none)"] + R.columns

            def pick(col, cols, cur, label, key):
                return col.selectbox(label, cols, index=cols.index(cur) if cur in cols else 0, key=f"{key}_{pr}")
            la = pick(c1, lcols, base_cfg.left_amount, f"{l} amount", "la")
            ra = pick(c2, rcols, base_cfg.right_amount, f"{r} amount", "ra")
            ld = pick(c3, lcols, base_cfg.left_date, f"{l} date", "ld")
            rd = pick(c4, rcols, base_cfg.right_date, f"{r} date", "rd")
            c5, c6, c7 = st.columns(3)
            fee = c5.number_input(f"Fee % deducted in {r}", 0.0, 20.0, 0.0, step=0.05, key=f"fee_{pr}", help="Leave at 0 to detect it automatically.")
            tol_pct = c6.number_input("Amount tolerance %", 0.0, 10.0, 0.0, step=0.1, key=f"tp_{pr}")
            comp = c7.checkbox("Amount + date fallback", True, key=f"comp_{pr}", help="When no shared reference exists, match on amount and date.")
            cfg = base_cfg
            cfg.keys = [KeySpec(cands[labels.index(x)].left_col, cands[labels.index(x)].right_col, cands[labels.index(x)].left_tf,
                                cands[labels.index(x)].right_tf, cands[labels.index(x)].mode) for x in chosen]
            cfg.left_amount, cfg.right_amount = (None if la == "(none)" else la), (None if ra == "(none)" else ra)
            cfg.left_date, cfg.right_date = (None if ld == "(none)" else ld), (None if rd == "(none)" else rd)
            cfg.expected_fee_pct, cfg.amount_tol_pct, cfg.use_composite, cfg.amount_tol = fee, tol_pct, comp, tol
            configs.append(cfg)

if not configs:
    st.markdown(ui.footer(__version__, EDITION), unsafe_allow_html=True)
    st.stop()

# ---------------------------------------------------------------- run (automatic; re-runs only when something changed)
sig = hashlib.sha256((json.dumps([c.to_dict() for c in configs], default=str, sort_keys=True)
                      + "|".join(f"{n}:{d.file_sha256}:{len(d)}" for n, d in ss.datasets.items())
                      + json.dumps(ss.overrides, sort_keys=True) + pci_mode).encode()).hexdigest()
if ss.get("run_sig") != sig:
    with st.spinner("Matching…"):
        ss.results, ss.chain = run_all(ss.datasets, configs, auto_fee=True)
    ss.configs = [r.config for r in ss.results.values()]
    ss.run_sig = sig
results, chain = ss.results, ss.chain
results = dict(sorted(results.items(), key=lambda kv: -kv[1].summary["matched_groups"]))   # busiest pair first


# ---------------------------------------------------------------- results
tot_m = sum(r.summary["matched_groups"] for r in results.values())
tot_x = sum(len(r.exceptions) for r in results.values())
h1, h2 = st.columns([3, 2], vertical_alignment="bottom")
h1.markdown(f'<div class="ar-results"><h2>Results</h2><p>{len(results)} pair{"s" if len(results) != 1 else ""} · '
            f'{tot_m:,} matched · {tot_x:,} exception{"s" if tot_x != 1 else ""}</p></div>', unsafe_allow_html=True)
buf = io.BytesIO()
with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as fh:
    write_excel(fh.name, ss.datasets, results, chain)
    buf.write(Path(fh.name).read_bytes())
Path(fh.name).unlink(missing_ok=True)
with h2.container(key="downloads", horizontal=True, horizontal_alignment="right"):
    st.download_button("Excel report", buf.getvalue(), "recon_report.xlsx", type="primary")
    st.download_button("Audit trail", json.dumps(audit_json(ss.datasets, results), indent=2, default=str), "recon_audit.json")
    if ADV:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as fh:
            pass
        tpl.save(fh.name, ss.datasets, ss.configs)
        st.download_button("Save setup", Path(fh.name).read_text(), "recon_template.json")
        Path(fh.name).unlink(missing_ok=True)


def show_pair(k, r):
    s = r.summary
    st.markdown(f'<p class="ar-note">{ui.esc(_rule_line(r.config))}</p>', unsafe_allow_html=True)
    m = st.columns(5)
    m[0].metric("Matched groups", f"{s['matched_groups']:,}")
    m[1].metric("Exceptions", f"{len(r.exceptions):,}")
    m[2].metric(f"{r.config.left} matched", f"{s['left_match_rate_pct']}%")
    m[3].metric(f"{r.config.right} matched", f"{s['right_match_rate_pct']}%")
    m[4].metric("Value matched", f"{s['left_value_matched_pct']}%" if s["left_value_matched_pct"] is not None else "–")
    for i in r.insights:
        if "expected_fee_pct" not in i:
            st.info(i)
    views = {f"Exceptions ({len(r.exceptions):,})": r.exceptions, f"Matches ({len(r.matches):,})": r.matches,
             f"Only in {r.config.left} ({len(r.left_unmatched):,})": r.left_unmatched,
             f"Only in {r.config.right} ({len(r.right_unmatched):,})": r.right_unmatched}
    pick = st.segmented_control("Show", list(views), default=list(views)[0], key=f"view_{k}", label_visibility="collapsed")
    df = views.get(pick, r.exceptions)
    st.dataframe(df, width="stretch", hide_index=True, height=min(400, 38 + 35 * max(len(df), 1)))


labels = [k.replace("⟷", " ↔ ") for k in results] + (["All documents"] if chain is not None else [])
tabs = st.tabs(labels) if len(labels) > 1 else [st.container()]
for tab, (k, r) in zip(tabs, results.items()):
    with tab:
        show_pair(k, r)
if chain is not None:
    with tabs[-1]:
        st.markdown(f'<p class="ar-note">One row per {ui.esc(chain.anchor.iloc[0])} item, traced across every document.</p>',
                    unsafe_allow_html=True)
        st.bar_chart(chain.status.value_counts(), color=ui.ACCENT, height=220)
        st.dataframe(chain, width="stretch", hide_index=True, height=360)
if llm.available() and st.button("Explain these results (AI)"):
    st.write(llm.explain(results))

st.markdown(ui.footer(__version__, EDITION), unsafe_allow_html=True)
