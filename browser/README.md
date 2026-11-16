# anyrecon · Web app

Nothing to install. Open the link and add your files. Works on locked-down work laptops.

**Your files never leave the browser tab.** Choosing a file lets the page open it, like a desktop program opens a
file from your disk; it is never uploaded. The page's security policy only allows it to load its own files.

## Use it

1. Open **[anyrecon.vercel.app](https://anyrecon.vercel.app)** in Chrome or Edge (other modern browsers should work, but only Chromium is tested).
2. Click **Start reconciling** and add your files. The page is usable straight away; the engine finishes loading
   in the background (about 20 seconds on a first visit, quicker after).

**Add it as an app (optional):** in Chrome or Edge, click the install icon at the right end of the address bar, or
the **Install app** button at the top of the page. It opens in its own window and, once opened, works with no
internet connection. Remove it from the app's ⋮ menu → Uninstall.

| Handles well | Use the [download version](../editions/desktop/README.md) instead for |
|---|---|
| CSV, Excel (several sheets), JSON, PDF statements | Scanned documents and photos |
| Up to about 250,000 rows per file (37 MB for three files); 500,000 at most | Larger files: up to about 1,000,000 rows per file with 8 GB of memory |

Measurements: [Data size and speed](https://anyrecon.vercel.app/guide.html#data-size-and-speed). The browser gives
the engine at most 4 GB of memory per tab, which is what sets the limit.

## Publish it (maintainers)

The live site is the prebuilt `web/` folder at the repo root, which Vercel serves as-is (`vercel.json` sets the
security headers, `.vercelignore` hides everything else). After changing the code:

```bash
pip install markdown playwright && python -m playwright install chromium
python browser/build.py && rm web/_headers     # builds web/; needs npm and internet
python browser/check.py                        # end-to-end test with outside network blocked
git add -A && git commit && git push           # Vercel redeploys automatically
```

`build.py` also writes the guide (`guide.html`), the changelog (`changelog.html`), the app manifest and the
service worker that makes the installed app work offline.

**Another host:** upload the contents of the output folder to any static host (GitHub Pages, Netlify, Cloudflare
Pages, an intranet web server) and link to the folder, not to `index.html`. The page carries its security policy
itself; hosts that support response headers (Netlify, Cloudflare Pages: use the generated `_headers` file) apply
it to the background Python worker too, which is the stronger setup. GitHub Pages can't set headers.

Everything the page uses is served from its own address: no CDNs, no PyPI, so it keeps working behind corporate
proxies.
