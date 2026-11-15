# anyrecon · Server edition

For IT teams: host anyrecon once on the company network; staff use it in their browser with nothing to install.

```bash
cd editions/server
docker compose up -d          # → http://<server>:8501
```

| Setting (`.env` next to `compose.yaml`) | Purpose |
|---|---|
| `ANYRECON_PAN_KEY` | Secret for card-number tokens that stay stable across runs. Store in your secrets manager |
| `ANYRECON_DEMO=1` | No uploads, synthetic data only. **Required for anything exposed to the internet** |
| `ANTHROPIC_API_KEY` | Optional AI commentary. Sends summary figures and column names only. Leave empty to keep it off |

What the container does and doesn't do:
- **Stores nothing.** Read-only filesystem; uploads live in memory per session and go when the session ends. No database, no logs of data.
- **Includes OCR** for scanned documents.
- **Has no login of its own.** Put it behind your SSO / reverse proxy and restrict it to the internal network.
- The host processes card data if users upload raw exports, so it sits inside your PCI DSS scope. See [docs/PCI_DSS.md](../../docs/PCI_DSS.md).

Update: `git pull && docker compose up -d --build`.
