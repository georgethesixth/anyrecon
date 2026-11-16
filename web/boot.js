import { mount } from "./stlite/stlite.js";
const base = new URL(".", import.meta.url).href;
const abs = (v) => typeof v === "string" && v.startsWith("./") ? new URL(v, base).href
  : Array.isArray(v) ? v.map(abs) : (v && typeof v === "object") ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, abs(x)])) : v;
const options = {
 "entrypoint": "app.py",
 "files": {
  "anyrecon/__init__.py": {
   "url": "./app/382dc0006c6a/anyrecon/__init__.py"
  },
  "anyrecon/__main__.py": {
   "url": "./app/382dc0006c6a/anyrecon/__main__.py"
  },
  "anyrecon/chain.py": {
   "url": "./app/382dc0006c6a/anyrecon/chain.py"
  },
  "anyrecon/cli.py": {
   "url": "./app/382dc0006c6a/anyrecon/cli.py"
  },
  "anyrecon/discover.py": {
   "url": "./app/382dc0006c6a/anyrecon/discover.py"
  },
  "anyrecon/fuzzy.py": {
   "url": "./app/382dc0006c6a/anyrecon/fuzzy.py"
  },
  "anyrecon/ingest.py": {
   "url": "./app/382dc0006c6a/anyrecon/ingest.py"
  },
  "anyrecon/llm.py": {
   "url": "./app/382dc0006c6a/anyrecon/llm.py"
  },
  "anyrecon/match.py": {
   "url": "./app/382dc0006c6a/anyrecon/match.py"
  },
  "anyrecon/models.py": {
   "url": "./app/382dc0006c6a/anyrecon/models.py"
  },
  "anyrecon/pci.py": {
   "url": "./app/382dc0006c6a/anyrecon/pci.py"
  },
  "anyrecon/profile.py": {
   "url": "./app/382dc0006c6a/anyrecon/profile.py"
  },
  "anyrecon/report.py": {
   "url": "./app/382dc0006c6a/anyrecon/report.py"
  },
  "anyrecon/templates.py": {
   "url": "./app/382dc0006c6a/anyrecon/templates.py"
  },
  "app.py": {
   "url": "./app/382dc0006c6a/app.py"
  },
  "ui_theme.py": {
   "url": "./app/382dc0006c6a/ui_theme.py"
  },
  "wheels/pdfplumber-0.11.10-py3-none-any.whl": {
   "url": "./app/382dc0006c6a/wheels/pdfplumber-0.11.10-py3-none-any.whl"
  }
 },
 "pyodideUrl": "./pyodide/pyodide.mjs",
 "requirements": [
  "./wheels/et_xmlfile-2.0.0-py3-none-any.whl",
  "./wheels/itsdangerous-2.2.0-py3-none-any.whl",
  "./wheels/openpyxl-3.1.5-py2.py3-none-any.whl",
  "./wheels/pdfminer_six-20260107-py3-none-any.whl",
  "./wheels/python_multipart-0.0.34-py3-none-any.whl",
  "./wheels/xlsxwriter-3.3.1-py3-none-any.whl"
 ],
 "wheelUrls": {
  "streamlit": "./stlite/wheels/streamlit-1.65.0-cp314-none-any.whl",
  "stliteLib": "./stlite/wheels/stlite_lib-0.1.0-py3-none-any.whl"
 },
 "streamlitConfig": {
  "client.toolbarMode": "minimal",
  "browser.gatherUsageStats": false,
  "theme.base": "light",
  "theme.primaryColor": "#2457D6",
  "theme.backgroundColor": "#FFFFFF",
  "theme.secondaryBackgroundColor": "#F5F6F8",
  "theme.textColor": "#14171F",
  "theme.font": "sans serif"
 }
};

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
  const list = ["ArrowVegaLiteChart-DESdGa-n-CEaS8POZ.js", "Autocomplete-yBl0QZl8-BEE9EvYw.js", "Button-DhJyQroy-B0Cv_LtY.js", "ButtonGroup-D_brxMJk-BOjSceyZ.js", "Cancel.esm-CtMNidjq-CXB-pKHk.js", "Checkbox-DiR2_V_8-CXHk70Gn.js", "DataFrame-DRF8lFxD-CzB3xmp7.js", "Delete.esm-C6XWoANM-vurQtJtA.js", "DownloadButton-BDPs5fKe-CaNr19dT.js", "ErrorOutline.esm-BTDiocCk-BcENiBMZ.js", "FileDownload.esm-CRjxpEeO-BaCWUjYd.js", "FileUploader-owv7Gz8c-BhqJc8-M.js", "Input-B1waFcLc-Ckq09rqm.js", "InputInstructions-CbZRC43y-BKqlI7Nl.js", "Metric-B4Y_nDFF-BZYvb_ri.js", "Multiselect-DBXDK3cr-3J8OBdHw.js", "NumberInput-C7YGxq-_-YqHWBRvg.js", "Radio-BhjCl1ye-Dl8N1b4y.js", "Selectbox-nIDushPA-D6d1TubB.js", "TableChart.esm-pzrJ7Hep-BMvXRoA-.js", "TextField-Co5gRJYP-Dyt18gzB.js", "UploadFileInfo-DdcsXhjv-C0F82PE-.js", "WidgetLabel--oJQrsAd-IbrOPlTn.js", "WidgetLabelHelpIcon-CWnOrY3T-BtbNCfjY.js", "WidgetLabelHelpIconInline-CmMO3-ig-CNt0dgU_.js", "_baseAssignValue-h4lglAau-CHZc32PX.js", "checkboxIndicatorStyles-5aHp9rTE-wuG81IsF.js", "colors-BD7LS4qt-BehGd4Ls.js", "createDownloadLinkElement-DiNIFj9z-DoAwXp-8.js", "cubic-Dir1Ko---Ccey17jF.js", "defaultLocale-2bEbhetO-QGFVckfi.js", "downloadDataUrl-DWF0xXIp-B1lPap8q.js", "formatMoment-CSglijqE-wHP8MmD-.js", "formatNumber-Q1A8AyDZ-C1p6HSP6.js", "fuzzyFilterSelectOptions-KB6RlC97-DFGqimxU.js", "index-CMxjGYGc-Cq-UqsLs.js", "index-CVld_lKx-DBjTNNj_.js", "index-CtOUUcfI-DNqIEPU5.js", "index-Df-1Z3LJ-BbKzDPIK.js", "index-fsFmsChH-Dni1dpUL.js", "init-5BClRdiB-LyILMlTE.js", "linear-CJvvCWKw-rrRTERsA.js", "numbro-CDdPhOTG-vF1UvoJy.js", "ordinal-DkyryJlW-DURmPlUH.js", "pandasStylerUtils-CW7C-2r_-shYCGj7z.js", "range-CdxqIeI4-DXvN35R3.js", "range-DdOGybNB-Ba7Spj1J.js", "reactJsonViewCompat-PzF5iqZ4-oi2jTtgM.js", "resolveDefaultExport-Cy5TTESD-CcwO08HL.js", "serialization-BSMBF8e2-CqZaT18J.js", "sprintfjs-CjmCzARP-HuCjLGam.js", "string-BvOnLx8K-BsWpS-s0.js", "styled-components-DOYIt51e-DLCP0S-5.js", "styled-components-QCR0zGl1-gqUrmVXI.js", "threshold-je-9V4hw-qdwK0deF.js", "time-p2i1Qn9v-RYMFf5JC.js", "toConsumableArray-B4DpFEAW-6YGARpRB.js", "unzip-B41UTbNh-D5sjV7cq.js", "useBasicWidgetState-DVivDFu--yiQ4kKRs.js", "useCollator-DP4BnoIq-QM8AOSx3.js", "useDebouncedCallback-BCfvDBFe-DLr1Sw-B.js", "useField-BVpgvwQT-C8iZdscS.js", "useFilter-DrWea0bI-BL4UsXQg.js", "useFormReset-BZ7HXuA_-BoM-dbzr.js", "useFormValidation-Cnit8K9v-CsmEyeH7.js", "useLoadMoreSentinel-7ezKn0I6-CVdwtTzs.js", "useMenuTrigger-BjNvpiW8-jg9Gu40v.js", "useSlot-DKJSZCIj-BYcKzeSG.js", "useTextField-Dnr0FC1--M69xt9uz.js", "utils-KJzGoNUG-DTAUhUPK.js", "value-Fb9HFOxE-BHCNJ526.js", "withFullScreenWrapper-C8-Fpvyp-DxnGM32Q.js", "zip-DFW5sP7Z-DCXENPDG.js", "zoom-C9yGXsgU-cg-4X7cE.js"], base = new URL("./stlite/", import.meta.url).href;
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
mount(abs(options), document.getElementById("root"));
