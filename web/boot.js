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
  "client.toolbarMode": "viewer",
  "browser.gatherUsageStats": false
 }
};
mount(abs(options), document.getElementById("root"));
