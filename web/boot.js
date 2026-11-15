import { mount } from "./stlite/stlite.js";
const base = new URL(".", import.meta.url).href;
const abs = (v) => typeof v === "string" && v.startsWith("./") ? new URL(v, base).href
  : Array.isArray(v) ? v.map(abs) : (v && typeof v === "object") ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, abs(x)])) : v;
const options = {
 "entrypoint": "app.py",
 "files": {
  "anyrecon/__init__.py": {
   "url": "./app/anyrecon/__init__.py"
  },
  "anyrecon/__main__.py": {
   "url": "./app/anyrecon/__main__.py"
  },
  "anyrecon/chain.py": {
   "url": "./app/anyrecon/chain.py"
  },
  "anyrecon/cli.py": {
   "url": "./app/anyrecon/cli.py"
  },
  "anyrecon/discover.py": {
   "url": "./app/anyrecon/discover.py"
  },
  "anyrecon/fuzzy.py": {
   "url": "./app/anyrecon/fuzzy.py"
  },
  "anyrecon/ingest.py": {
   "url": "./app/anyrecon/ingest.py"
  },
  "anyrecon/llm.py": {
   "url": "./app/anyrecon/llm.py"
  },
  "anyrecon/match.py": {
   "url": "./app/anyrecon/match.py"
  },
  "anyrecon/models.py": {
   "url": "./app/anyrecon/models.py"
  },
  "anyrecon/pci.py": {
   "url": "./app/anyrecon/pci.py"
  },
  "anyrecon/profile.py": {
   "url": "./app/anyrecon/profile.py"
  },
  "anyrecon/report.py": {
   "url": "./app/anyrecon/report.py"
  },
  "anyrecon/templates.py": {
   "url": "./app/anyrecon/templates.py"
  },
  "app.py": {
   "url": "./app/app.py"
  },
  "ui_theme.py": {
   "url": "./app/ui_theme.py"
  },
  "examples/__init__.py": {
   "url": "./app/examples/__init__.py"
  },
  "examples/generate_samples.py": {
   "url": "./app/examples/generate_samples.py"
  },
  "examples/data/processor.csv": {
   "url": "./app/examples/data/processor.csv"
  },
  "examples/data/ledger.xlsx": {
   "url": "./app/examples/data/ledger.xlsx"
  },
  "examples/data/bank_statement.pdf": {
   "url": "./app/examples/data/bank_statement.pdf"
  },
  "examples/data/settlement_report.json": {
   "url": "./app/examples/data/settlement_report.json"
  },
  "wheels/pdfplumber-0.11.10-py3-none-any.whl": {
   "url": "./app/wheels/pdfplumber-0.11.10-py3-none-any.whl"
  }
 },
 "pyodideUrl": "./pyodide/pyodide.mjs",
 "requirements": [
  "./wheels/et_xmlfile-2.0.0-py3-none-any.whl",
  "./wheels/itsdangerous-2.2.0-py3-none-any.whl",
  "./wheels/openpyxl-3.1.5-py2.py3-none-any.whl",
  "./wheels/pdfminer_six-20260107-py3-none-any.whl",
  "./wheels/python_multipart-0.0.33-py3-none-any.whl"
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
mount(abs(options), document.getElementById("root"));
