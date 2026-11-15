"""Generate a synthetic, deliberately messy reconciliation scenario.

Outputs (in examples/data/, which is git-ignored):
  processor.csv            card processor export: preamble lines, full test PANs + CVV (to exercise
                           the PCI guard), RRNs, gross amounts, total row
  ledger.xlsx              internal GL: different header, 'NX-' prefixed refs without leading zeros,
                           missing rows, amount errors, a duplicate, a typo, manual journals
  bank_statement.pdf       multi-page bank statement: RRN buried in narration, credits net of 1.5% MDR,
                           T+1/T+2 value dates, bank charges, opening/closing balance rows
  settlement_report.json   daily settlement batches (one row per day = sum of many processor rows)
  scanned_statement.png    an image of part of the bank statement (exercises OCR + review flags)

All card numbers use test BINs and are random; no real data.
"""
from __future__ import annotations

import csv
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

OUT = Path(__file__).parent / "data"
MDR = 0.015


def luhn_complete(prefix: str, length: int = 16) -> str:
    body = prefix + "".join(random.choice("0123456789") for _ in range(length - len(prefix) - 1))
    total = 0
    for i, ch in enumerate(reversed(body)):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return body + str((10 - total % 10) % 10)


def main(n: int = 300, seed: int = 7, out: Path | None = None) -> Path:
    global OUT
    OUT = Path(out) if out else Path(__file__).parent / "data"
    random.seed(seed)
    OUT.mkdir(parents=True, exist_ok=True)
    start = datetime(2026, 10, 1, 8, 0)
    txns = []   # card numbers use test-only ranges (400000, 510510)
    used = set()
    for i in range(n):
        rrn = f"{random.randint(1, 99999999999):012d}"
        while rrn in used:
            rrn = f"{random.randint(1, 99999999999):012d}"
        used.add(rrn)
        ts = start + timedelta(days=random.randint(0, 9), minutes=random.randint(0, 600))
        amt = round(random.choice([random.uniform(500, 5000), random.uniform(5000, 50000), random.uniform(50000, 250000)]), 2)
        txns.append(dict(rrn=rrn, stan=f"{random.randint(0, 999999):06d}", ts=ts, amount=amt,
                         pan=luhn_complete(random.choice(["400000", "510510"])), cvv=f"{random.randint(0, 999):03d}"))
    txns.sort(key=lambda t: t["ts"])
    for t in txns:
        t["batch"] = "STL-" + t["ts"].strftime("%Y%m%d")

    # ---------------- processor.csv
    with open(OUT / "processor.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Demo Processor Ltd - Transaction Report"])
        w.writerow(["Merchant: DEMO STORES LTD", "", "MID: 2057LA000123"])
        w.writerow(["Period: 01/10/2026 - 10/10/2026"])
        w.writerow([])
        w.writerow(["Transaction Date", "RRN", "STAN", "Card Number", "CVV", "Amount", "Fee", "Status", "Settlement Batch"])
        for t in txns:
            w.writerow([t["ts"].strftime("%d/%m/%Y %H:%M"), t["rrn"], t["stan"], t["pan"], t["cvv"],
                        f"{t['amount']:,.2f}", f"{t['amount'] * MDR:,.2f}", "APPROVED", t["batch"]])
        w.writerow(["TOTAL", "", "", "", "", f"{sum(t['amount'] for t in txns):,.2f}", "", "", ""])

    # ---------------- ledger.xlsx
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "GL Extract"
    ws.append(["Internal General Ledger - Card Collections"])
    ws.append([])
    ws.append(["Posting Date", "Txn Reference", "Description", "Gross Amount", "GL Account"])
    led = list(txns)
    missing_ledger = set(random.sample(range(n), 6))
    amount_err = set(random.sample([i for i in range(n) if i not in missing_ledger], 3))
    typo = random.choice([i for i in range(n) if i not in missing_ledger | amount_err])
    dup = random.choice([i for i in range(n) if i not in missing_ledger | amount_err | {typo}])
    for i, t in enumerate(led):
        if i in missing_ledger:
            continue
        ref = "NX-" + t["rrn"].lstrip("0")
        if i == typo:
            ref = ref[:-2] + ("9" if ref[-2] != "9" else "8") + ref[-1]
        amt = t["amount"] + (100.0 if i in amount_err else 0)
        row = [t["ts"].date(), ref, f"Card collection {t['stan']}", round(amt, 2), "4100-01"]
        ws.append(row)
        if i == dup:
            ws.append(row)
    ws.append([datetime(2026, 10, 5).date(), "JRNL-0042", "Manual adj - write off", 1500.00, "4100-01"])
    ws.append([datetime(2026, 10, 8).date(), "JRNL-0043", "Manual adj - reversal", 2750.00, "4100-01"])
    ws.append([None, None, "Total", None, None])
    wb.save(OUT / "ledger.xlsx")

    # ---------------- bank_statement.pdf
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

    missing_bank = set(random.sample(range(n), 4))
    bank_rows = []
    for i, t in enumerate(txns):
        if i in missing_bank:
            continue
        lag = random.choice([1, 1, 1, 2])
        bank_rows.append((t["ts"] + timedelta(days=lag), f"POS SETTL/{t['rrn']}/DEMO STORES", None, round(t["amount"] * (1 - MDR), 2)))
    for d in range(1, 11, 3):
        bank_rows.append((datetime(2026, 10, d, 23), "SMS ALERT CHARGES", 4.00, None))
    bank_rows.append((datetime(2026, 10, 6, 23), "ACCOUNT MAINTENANCE FEE", 1250.00, None))
    bank_rows.sort(key=lambda r: r[0])
    bal = 1_000_000.00
    table = [["Value Date", "Narration", "Debit", "Credit", "Balance"],
             ["", "Opening Balance", "", "", f"{bal:,.2f}"]]
    for dt, narr, dr, cr in bank_rows:
        bal += (cr or 0) - (dr or 0)
        table.append([dt.strftime("%d-%b-%Y"), narr, f"{dr:,.2f}" if dr else "", f"{cr:,.2f}" if cr else "", f"{bal:,.2f}"])
    table.append(["", "Closing Balance", "", "", f"{bal:,.2f}"])
    doc = SimpleDocTemplate(str(OUT / "bank_statement.pdf"), pagesize=A4, leftMargin=30, rightMargin=30)
    st = getSampleStyleSheet()
    lt = LongTable(table, repeatRows=1, colWidths=[70, 230, 70, 80, 85])
    lt.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("ALIGN", (2, 0), (-1, -1), "RIGHT")]))
    doc.build([Paragraph("DEMO BANK PLC — Statement of Account", st["Title"]),
               Paragraph("Account: DEMO STORES LTD  |  0123456789  |  01 Oct 2026 – 12 Oct 2026", st["Normal"]),
               Spacer(1, 10), lt])

    # ---------------- settlement_report.json (daily batches = sum of processor rows)
    batches = {}
    for t in txns:
        batches.setdefault(t["batch"], []).append(t)
    settlements = []
    for b, ts in sorted(batches.items()):
        gross = round(sum(t["amount"] for t in ts), 2)
        settlements.append(dict(batch_id=b, settlement_date=(ts[0]["ts"] + timedelta(days=1)).strftime("%Y-%m-%d"),
                                txn_count=len(ts), gross_amount=gross, fee=round(gross * MDR, 2), net_amount=round(gross * (1 - MDR), 2)))
    settlements[3]["gross_amount"] = round(settlements[3]["gross_amount"] - 2500.00, 2)   # one short-settled batch
    (OUT / "settlement_report.json").write_text(json.dumps(dict(merchant="DEMO STORES LTD", settlements=settlements), indent=2))

    # ---------------- scanned_statement.png (first ~14 bank lines as an image)
    from PIL import Image, ImageDraw, ImageFont
    font = None
    for f in ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "/usr/share/fonts/dejavu/DejaVuSansMono.ttf"]:
        if Path(f).exists():
            font = ImageFont.truetype(f, 26)
            break
    font = font or ImageFont.load_default()
    img = Image.new("RGB", (2000, 120 + 48 * 16), "white")
    dr_ = ImageDraw.Draw(img)
    dr_.text((40, 30), "DEMO BANK PLC - SCANNED STATEMENT", fill="black", font=font)
    xs = [40, 330, 1150, 1450, 1720]
    for j, h in enumerate(["Value Date", "Narration", "Debit", "Credit", "Balance"]):
        dr_.text((xs[j], 100), h, fill="black", font=font)
    y = 150
    for row in table[2:16]:
        for j, v in enumerate(row):
            dr_.text((xs[j], y), v, fill="black", font=font)
        y += 48
    img.save(OUT / "scanned_statement.png")

    truth = dict(missing_in_ledger=len(missing_ledger), ledger_amount_errors=len(amount_err), ledger_typo=1,
                 ledger_duplicate=1, ledger_manual_journals=2, missing_in_bank=len(missing_bank), mdr_pct=MDR * 100,
                 short_settled_batch=settlements[3]["batch_id"])
    (OUT / "ground_truth.json").write_text(json.dumps(truth, indent=2))
    return OUT


if __name__ == "__main__":
    out = main(int(sys.argv[1]) if len(sys.argv) > 1 else 300)
    print(f"Sample files written to {out}")
