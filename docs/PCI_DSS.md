# Card data (PCI DSS) and personal data: how anyrecon handles them

Reconciliation files in payments routinely contain card data: processor exports with full PANs,
chargeback files, switch logs. This document explains what the tool does about that, and what
remains **your** responsibility as the person running it. It is guidance, not legal or QSA advice.

## Definitions (PCI DSS v4.0.1)

| Term | Includes | Rule |
|---|---|---|
| Cardholder data (CHD) | PAN, cardholder name, expiry, service code | May be stored only if protected. The PAN is what brings a system into scope |
| Sensitive authentication data (SAD) | Full track / chip data, CVV/CVC, PIN / PIN block | **Never stored after authorisation, even encrypted** (Req 3.3.1) |
| Masked PAN | At most first 6 + last 4 visible | Display rule (Req 3.4.1). Masked PANs alone are not stored CHD |
| Truncated / tokenised / keyed-hash PAN | Irreversible forms | Acceptable ways to render PAN unreadable at rest (Req 3.5.1); hashes must be keyed (Req 3.5.1.1) |

## What the engine does (the PCI guard)

The guard runs on every file **immediately after parsing**, before profiling, matching, report
writing, template saving or any AI call. Nothing downstream ever sees a full PAN or SAD.

| Detected | Action | Where it's logged |
|---|---|---|
| CVV/CVC column (by name + 3–4 digit values) | Column dropped | PCI log sheet + audit JSON |
| PIN / PIN block / track data (by name or track-data pattern) | Column dropped | same |
| Column of full PANs (Luhn-valid, card-network prefix) | Masked to first 6 / last 4, plus a keyed HMAC-SHA256 token column so card number can still be a matching key | same |
| PAN inside free text (narrations, notes) | Masked in place | same |
| 13–19 digit reference column where most values fail Luhn | Treated as references, not card numbers; the few chance Luhn-valid ones are left as-is and logged as `PAN_EXEMPT` | same |
| Already-masked PANs | Left as-is, noted | same |
| Unlabelled 3–4 digit or 16-hex column next to card numbers | Dropped, flagged for your review | same |

### What happens automatically vs what needs your decision

There is **no "accept" prompt for confirmed card numbers or labelled CVV/PIN/track data**. Keeping them
unmasked is never a legitimate option for a reconciliation output, so asking would only invite a wrong
click. The tool acts and tells you: a banner at the top, details per file, and a PCI log sheet in the report.

You are asked **only where the tool is genuinely unsure**:

| Situation | Default | Your option |
|---|---|---|
| Reference column where a few values happen to pass the card-number (Luhn) check | Left as-is (otherwise ~10% of references would be broken by chance) | "Mask anyway" (`--mask-col name:column`) |
| Unlabelled column of 3–4 digit values next to card numbers (possible CVV) | **Dropped** | "I confirm this is not a CVV, restore it" (`--keep-col name:column`), logged for audit |
| Unlabelled 16-character hex column next to card numbers (possible PIN block) | **Dropped** | Same as above |

When unsure, the default always errs on the side that can be undone: dropping a column you need costs
one click to restore, but a retained CVV can't be un-stored.

### How CVV, PIN and track data are recognised

| Data | Signal used | Can it be missed? |
|---|---|---|
| CVV/CVC | Column name contains cvv, cvc, cvv2, cvc2, cav2, cid, csc, "security code", "card verification", **and** ≥ 80% of values are 3–4 digits | A CVV in a column with a meaningless header (e.g. `col_5`, `Field 7`) is caught by the next rule only if card numbers are in the same file |
| Suspected CVV | Unlabelled or cv/sec/verif-named column, ≥ 95% 3–4 digit values, **in a file that contains card numbers** | A CVV under a misleading header (e.g. "Branch") won't be detected. Pattern alone can't distinguish it from any other 3-digit code |
| PIN / PIN block | Column name contains pin / pin block; or unlabelled 16-hex-character values next to card numbers | Encrypted PIN blocks under arbitrary names in files without card numbers |
| Track data | Value pattern `%B<PAN>^…` (track 1) or `;<PAN>=YYMM…` (track 2), regardless of column name | Reliable: the format is distinctive |

Detection is a safety net, not a substitute for not exporting SAD in the first place. If a system you
own produces files containing CVV or PIN data after authorisation, that system has a compliance problem.

### Storing vs processing

anyrecon stores nothing by default (see below). But PCI DSS applies to anything that **stores, processes
or transmits** card data, so a machine that *reads* a raw file containing full card numbers is
processing it, even if it masks them a millisecond later. Not storing reduces risk and scope; it does
not take the machine out of scope. That's why the advice is to run anyrecon where the data already lives,
and why a hosted public instance with uploads would make *you* a service provider even though it saves nothing.

### By edition

| Edition | Where card data is processed | Your exposure as publisher |
|---|---|---|
| Browser | In the user's browser tab; the page is barred from sending data anywhere | None for data. You serve code, so protect the site that hosts it |
| Desktop | On the user's computer | None |

### What anyrecon keeps

| Item | Kept? |
|---|---|
| Uploaded files (web UI) | Held in memory for the session. Written to a private temp file only while being parsed, then deleted |
| Parsed data, results | In memory until you click **Clear all data**, close the tab, or stop the app |
| Excel report / audit JSON | Only if you click download (UI) or name an output file (CLI). Saved where you choose. Contains masked data only |
| Templates | Column names and rules only, never values |
| Logs, cache, database | None |
| Anything sent off your computer | Nothing, unless you turn on AI commentary (summary figures and column names only) |

Modes: `--pci strict` (default), `--pci paranoid` (no reference exemption, masks every Luhn-valid
number), `--pci block` (refuses to load any file containing PAN/SAD; use in CI or anything hosted).

Tokens use `ANYRECON_PAN_KEY` if set (stable across runs, so templates/tokens can be compared
month to month); otherwise a random per-run key that never touches disk.

## Scenarios and consequences

| # | Scenario | Who carries PCI scope | What can go wrong | Consequence | Mitigation in this repo |
|---|---|---|---|---|---|
| 1 | You or a user run anyrecon **locally** on files from their own payments environment | The user's organisation. The laptop becomes part of its cardholder data environment (CDE) if raw files with PAN sit on it | Raw processor exports with full PAN left on a personal laptop outside the segmented CDE | Laptop pulled into the organisation's PCI scope; audit finding; if lost/stolen, a reportable breach | Guard ensures *outputs* never contain PAN/SAD; docs tell users to run inside their CDE or on pre-masked extracts |
| 2 | A **hosted public demo** linked from kemdi.co accepts uploads | **You.** Anything that receives and processes card data on behalf of others is acting as a service provider | Someone uploads a real file with PANs | You're in scope as an unassessed service provider; any breach is yours to own; acquirers/brands can pursue the entity whose data leaked, and NDPA liability applies to you as the processor of personal data The public site is the web app: only its code is served; files are read inside the visitor's tab and the page is barred from sending data anywhere, so no one receives card data |
| 3 | Input files contain **full PANs** | User | PAN copied into Excel report, logs, templates, screenshots | Report becomes CHD at rest, spreading scope to every inbox/drive it reaches | Masked at ingest; report, audit JSON and templates only ever see masked/tokenised values |
| 4 | Input files contain **CVV, PIN block or track data** | User (and whoever produced the file) | Stored after authorisation | Direct breach of Req 3.3.1, among the most serious findings; card-brand fines are levied on the acquirer, then passed down by contract | Dropped at ingest; `block` mode refuses the file |
| 5 | **AI commentary** enabled (`--explain`) | User, and the AI provider becomes a third party receiving data | Raw rows sent to an external API | PAN sent to a third party not covered by your PCI assessment; NDPA cross-border transfer issue | AI is off by default; only summary stats, column names and value *shapes* are sent; `--share-samples` sends at most 15 already-masked exception rows |
| 6 | **Contributors** commit sample files to the public repo | You (repo owner) | A real export with PANs or customer names pushed to GitHub | Public exposure; permanent in git history and forks; NDPA breach; reputational damage | `.gitignore` excludes data folders; pre-commit hook scans for Luhn-valid PANs; only synthetic data generator is committed |
| 7 | Files contain only **masked PAN** (first 6 / last 4) | Out of CHD storage scope | None from PAN; still personal data if names/phones present | NDPA still applies to names, phone numbers, account numbers | Treated as ordinary columns |
| 8 | Files contain **names, phone numbers, account numbers** but no card data | Not PCI; NDPA applies | Over-sharing reports or AI payloads | NDPA penalties (below) | Keep reports internal; AI payload excludes row values by default |
| 9 | Running it **at an employer** (e.g. on settlement files) | Employer | Using a personal copy of an open-source tool on company data without approval | Policy breach regardless of PCI; change-management issue | Run from the employer's environment, via their approval process; templates contain no data so can be shared safely |

### What non-compliance actually costs

- **Card-brand / acquirer:** PCI DSS is contractual, not law. Non-compliance penalties are set by
  card brands and passed through acquirers. They are not published as a fixed schedule; they
  escalate monthly while non-compliance continues, and after a breach you also carry forensic
  investigation (PFI) costs, card reissuance and fraud losses. In the worst case you lose the
  ability to accept or process cards.
- **Nigeria Data Protection Act 2023 (s.48):** fines up to the greater of ₦10m or 2% of prior-year
  annual gross revenue for data controllers/processors of major importance, or the greater of ₦2m
  or 2% for others. The NDPC has issued real fines, including ₦766.2m against MultiChoice and
  ₦555.8m against Fidelity Bank.
- **CBN-regulated entities** have their own information-security and data-handling expectations on top.

## Rules of thumb for users

1. Prefer pre-masked or tokenised extracts. Most reconciliations don't need the full PAN; RRN, STAN, session ID or a token works.
2. Run locally, inside the environment that already holds the data.
3. Use `--pci block` for automated or shared deployments.
4. Never upload real data to a public demo.
5. Set `ANYRECON_PAN_KEY` from a secrets manager if you need card number as a stable matching key.
