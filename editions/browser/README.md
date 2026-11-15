# anyrecon · Browser edition

Nothing to install. Open the link and drag in your files. Works on locked-down work laptops.

**Your files never leave the browser tab.** The page can't send data anywhere: its security policy
only allows it to load its own files.

## Use it

1. Open **[anyrecon.vercel.app](https://anyrecon.vercel.app)** in Chrome or Edge.
2. Click **Start reconciling** and add your files. The page is usable straight away; the engine finishes loading in the background (about 20 seconds on a first visit).

| Supported | Not in this edition (use Desktop or Server) |
|---|---|
| CSV, Excel, JSON, PDF statements | Scanned documents and photos |
| Up to tens of thousands of rows comfortably | Very large files (hundreds of thousands of rows) |
| Excel report, audit file, templates | AI commentary |

## Publish it (maintainers)

The live site is the prebuilt `web/` folder at the repo root, which Vercel serves as-is (`vercel.json`
sets the security headers, `.vercelignore` hides everything else). After changing the code:

```bash
pip install markdown                                    # renders docs/GUIDE.md into guide.html
python editions/browser/build.py --out web && rm web/_headers   # needs npm and internet (~80 MB)
git add web && git commit -m "Rebuild browser edition" && git push   # Vercel redeploys automatically
```

To host it anywhere else, build to the default `editions/browser/site/` instead:

Upload the **contents** of `site/` to any static host: a folder on kemdi.co, GitHub Pages, Netlify,
Cloudflare Pages, or an intranet web server. Link to the folder (`…/anyrecon/`), not to `index.html`.

The page carries its security policy itself. Hosts that support response headers (Netlify, Cloudflare
Pages, the bundled `_headers` file) apply it to the background Python worker too, which is the stronger
setup. GitHub Pages can't set headers.

Everything the page uses is served from your own domain: no CDNs, no PyPI. It keeps working behind
corporate proxies.
