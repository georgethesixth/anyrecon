// anyrecon service worker. Caches the app's own files so the installed app starts offline.
// It never sees user files: those are opened inside the page and never requested over the network.
const VERSION = "e377f39234d5";
const CACHE = "anyrecon-" + VERSION;
const SHELL = ["./", "./index.html", "./boot.js", "./boot.css", "./guide.html", "./changelog.html", "./guide.css", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png", "./stlite/stlite.js", "./stlite/stlite.css", "./app/fba20f8e355b/anyrecon/__init__.py", "./app/fba20f8e355b/anyrecon/__main__.py", "./app/fba20f8e355b/anyrecon/chain.py", "./app/fba20f8e355b/anyrecon/cli.py", "./app/fba20f8e355b/anyrecon/discover.py", "./app/fba20f8e355b/anyrecon/export.py", "./app/fba20f8e355b/anyrecon/fuzzy.py", "./app/fba20f8e355b/anyrecon/ingest.py", "./app/fba20f8e355b/anyrecon/llm.py", "./app/fba20f8e355b/anyrecon/match.py", "./app/fba20f8e355b/anyrecon/models.py", "./app/fba20f8e355b/anyrecon/pci.py", "./app/fba20f8e355b/anyrecon/profile.py", "./app/fba20f8e355b/anyrecon/report.py", "./app/fba20f8e355b/anyrecon/templates.py", "./app/fba20f8e355b/app.py", "./app/fba20f8e355b/ui_theme.py", "./app/fba20f8e355b/wheels/pdfplumber-0.11.11-py3-none-any.whl"];
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
