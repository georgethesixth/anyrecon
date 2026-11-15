import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from anyrecon import auto_config, discover, load, run_all  # noqa: E402
from anyrecon.ingest import frame_from_raw  # noqa: E402
from anyrecon.match import KeySpec, PairConfig, reconcile  # noqa: E402
from anyrecon.models import Dataset  # noqa: E402
from anyrecon.pci import PCIBlocked, guard, is_pan, luhn, mask_pan  # noqa: E402
from anyrecon.profile import parse_amount, parse_date  # noqa: E402


# ------------------------------------------------------------------ unit

def test_luhn_and_mask():
    assert luhn("4111111111111111") and is_pan("4111111111111111")
    assert not is_pan("4111111111111112")
    assert mask_pan("4111111111111111") == "411111******1111"


def _ds(df, name="t"):
    df = df.copy()
    df.insert(0, "__row", [f"L{i}" for i in range(len(df))])
    return Dataset(name, df, "mem", "csv")


def test_pci_masks_pan_drops_cvv_and_tokenises():
    ds = guard(_ds(pd.DataFrame({"Card Number": ["4111111111111111", "5555555555554444"], "CVV": ["123", "456"],
                                 "Narration": ["paid with 4111 1111 1111 1111 ok", "none"]})))
    assert "CVV" not in ds.df.columns
    assert ds.df["Card Number"].tolist() == ["411111******1111", "555555******4444"]
    assert "4111" in ds.df["Narration"][0] and "411111******1111" in ds.df["Narration"][0]
    assert ds.df["__tok_Card Number"].str.startswith("TOK").all()
    assert {f.kind for f in ds.findings} == {"SAD_CVV", "PAN", "PAN_IN_TEXT"}


def test_pci_reference_column_exempt_in_strict_masked_in_paranoid():
    refs = [f"{i:016d}" for i in range(1000000000000000, 1000000000000040)]
    refs[5] = "4111111111111111"  # one chance Luhn-valid value in a reference column
    ds = guard(_ds(pd.DataFrame({"Reference": refs})), "strict")
    assert ds.df["Reference"][5] == "4111111111111111"
    assert ds.findings[0].kind == "PAN_EXEMPT"
    ds = guard(_ds(pd.DataFrame({"Reference": refs})), "paranoid")
    assert ds.df["Reference"][5] == "411111******1111"


def test_pci_block_mode():
    with pytest.raises(PCIBlocked):
        guard(_ds(pd.DataFrame({"pan": ["4111111111111111"]})), "block")


def test_parse_amount_variants():
    s = parse_amount(pd.Series(["1,234.50", "(200.00)", "₦ 3,000", "1.234,56", "45.10 DR", None, "abc"]))
    assert s.tolist()[:5] == [1234.5, -200.0, 3000.0, 1234.56, -45.10]
    assert pd.isna(s[5]) and pd.isna(s[6])


def test_parse_date_dayfirst():
    d, fmt, rate = parse_date(pd.Series(["01/10/2026 08:15", "13/10/2026 09:00"]))
    assert fmt == "%d/%m/%Y" and rate == 1.0 and d[1].month == 10


def test_header_detection_skips_preamble_and_totals():
    raw = pd.DataFrame([["Report title", None, None], ["Generated 2026-10-01", None, None],
                        ["Date", "Ref", "Amount"], ["01/10/2026", "A1", "10"], ["02/10/2026", "A2", "20"],
                        ["Total", None, "30"]], index=[f"L{i}" for i in range(6)])
    notes = []
    df = frame_from_raw(raw, notes)
    assert list(df.columns) == ["Date", "Ref", "Amount"] and len(df) == 2


# ------------------------------------------------------------------ matching

def _pair(left_rows, right_rows, **cfg):
    L = _ds(pd.DataFrame(left_rows), "L")
    R = _ds(pd.DataFrame(right_rows), "R")
    c = PairConfig("L", "R", **cfg)
    return reconcile(L, R, c)


def test_one_to_many_batch_and_variance():
    r = _pair({"batch": ["B1", "B1", "B2", "B2"], "amt": ["10", "20", "5", "5"]},
              {"batch": ["B1", "B2"], "amt": ["30", "9"]},
              keys=[KeySpec("batch", "batch", "exact", "exact")], left_amount="amt", right_amount="amt")
    st = dict(zip(r.matches.key, r.matches.status))
    assert st == {"B1": "matched", "B2": "amount_variance"}


def test_expected_fee_and_composite_fallback():
    r = _pair({"ref": ["X1", "X2", None], "amt": ["1000", "2000", "777"], "d": ["2026-10-01"] * 3},
              {"ref": ["X1", "X2", None], "amt": ["985", "1970", "765.35"], "d": ["2026-10-02"] * 3},
              keys=[KeySpec("ref", "ref")], left_amount="amt", right_amount="amt", left_date="d", right_date="d",
              expected_fee_pct=1.5)
    assert (r.matches.status == "matched").all() and len(r.matches) == 3
    assert "composite" in set(r.matches.tier)


def test_duplicate_key_flagged():
    r = _pair({"ref": ["A", "B"], "amt": ["1", "2"]}, {"ref": ["A", "A", "B"], "amt": ["1", "1", "2"]},
              keys=[KeySpec("ref", "ref")], left_amount="amt", right_amount="amt", use_composite=False)
    assert "duplicate_key" in set(r.exceptions.category)


# ------------------------------------------------------------------ end to end on synthetic data

@pytest.fixture(scope="module")
def sample(tmp_path_factory):
    from examples.generate_samples import main
    out = main(out=tmp_path_factory.mktemp("data"))
    files = dict(processor="processor.csv", ledger="ledger.xlsx", bank="bank_statement.pdf", settlement="settlement_report.json")
    return {n: load(out / f, name=n) for n, f in files.items()}, json.loads((out / "ground_truth.json").read_text())


def test_discovery_finds_planted_identifiers(sample):
    d, _ = sample
    top = discover(d["processor"], d["ledger"])[0]
    assert (top.left_col, top.right_col, top.left_tf) == ("RRN", "Txn Reference", "noprefix")
    top = discover(d["processor"], d["bank"])[0]
    assert (top.left_col, top.right_col, top.mode) == ("RRN", "Narration", "extract_right")


def test_end_to_end_matches_ground_truth(sample):
    d, truth = sample
    cfgs = [auto_config(d["processor"], d[x])[0] for x in ("ledger", "bank", "settlement")]
    res, chain = run_all(d, cfgs)
    pl = res["processor⟷ledger"].summary["exceptions_by_category"]
    assert pl["missing_in_ledger"] == truth["missing_in_ledger"]
    assert pl["amount_variance"] == truth["ledger_amount_errors"]
    assert pl["missing_in_processor"] == truth["ledger_manual_journals"]
    assert pl["duplicate_key"] == truth["ledger_duplicate"]
    pb = res["processor⟷bank"]
    assert any("1.50%" in i for i in pb.insights)            # MDR detected without being told
    cfgs[1].expected_fee_pct = truth["mdr_pct"]
    res, chain = run_all(d, cfgs)
    pb = res["processor⟷bank"].summary
    assert pb["exceptions_by_category"]["missing_in_bank"] == truth["missing_in_bank"]
    assert pb["by_status"] == {"matched": 296}
    ps = res["processor⟷settlement"].matches
    assert ps.loc[ps.status == "amount_variance", "key"].tolist() == [truth["short_settled_batch"]]
    assert chain.status.value_counts()["complete"] > 240


def test_outputs_never_contain_full_pan(sample, tmp_path):
    from anyrecon.report import audit_json, write_excel
    d, _ = sample
    cfgs = [auto_config(d["processor"], d["ledger"])[0]]
    res, chain = run_all(d, cfgs)
    out = write_excel(str(tmp_path / "r.xlsx"), d, res, chain)
    sheets = pd.read_excel(out, sheet_name=None, dtype=str)
    text = " ".join(s.to_csv() for s in sheets.values()) + json.dumps(audit_json(d, res), default=str)
    import re
    for m in re.finditer(r"(?<!\d)\d{13,19}(?!\d)", text):
        assert not is_pan(m.group(0)), "full PAN leaked into outputs"


def test_aggregate_without_shared_key_net_of_fee():
    from anyrecon.match import AggregateSpec
    left = {"day": ["2026-10-01", "2026-10-01", "2026-10-02"], "amt": ["1000", "3000", "500"], "d": ["2026-10-01", "2026-10-01", "2026-10-02"]}
    right = {"narr": ["SETTLEMENT CREDIT", "SETTLEMENT CREDIT"], "amt": ["3940", "492.5"], "d": ["2026-10-02", "2026-10-03"]}
    r = _pair(left, right, keys=[], left_amount="amt", right_amount="amt", left_date="d", right_date="d",
              expected_fee_pct=1.5, use_composite=False, aggregate=AggregateSpec(side="left", group_by="day"))
    assert len(r.matches) == 2 and (r.matches.status == "matched").all()
    assert set(r.matches.cardinality) == {"2:1", "1:1"}


# ------------------------------------------------------------------ round 2: review flow, parsing, sheets, narrations

def test_suspected_cvv_dropped_and_restorable():
    df = pd.DataFrame({"Card": ["4111111111111111", "5555555555554444", "4000056655665556"], "col_5": ["123", "045", "999"],
                       "Branch": ["101", "102", "103"]})
    ds = guard(_ds(df))
    assert "col_5" not in ds.df.columns and "Branch" in ds.df.columns
    f = [x for x in ds.findings if x.column == "col_5"][0]
    assert f.kind == "SAD_SUSPECTED_CVV" and f.review == "can_keep"
    ds = guard(_ds(df), keep_columns={"col_5"})
    assert "col_5" in ds.df.columns


def test_named_cvv_cannot_be_kept():
    ds = guard(_ds(pd.DataFrame({"Card": ["4111111111111111"] * 3, "CVV": ["123", "456", "789"]})), keep_columns={"CVV"})
    assert "CVV" not in ds.df.columns


def test_exempt_reference_can_be_masked_on_request():
    refs = [f"{i:016d}" for i in range(1000000000000000, 1000000000000040)]
    refs[5] = "4111111111111111"
    ds = guard(_ds(pd.DataFrame({"Reference": refs})), mask_columns={"Reference"})
    assert ds.df["Reference"][5] == "411111******1111"


def test_parsing_safeguards(tmp_path):
    p = tmp_path / "gl.csv"
    p.write_text("Session ID,Ref,Posting Date,Amount\n"
                 "1.00001E+29,42833770659.0,45931,100.00\n"
                 "1.00001E+29,49980710157.0,45932,200.00\n")
    ds = load(p)
    assert any("scientific notation" in w for w in ds.warnings)
    assert ds.df["Ref"].tolist() == ["42833770659", "49980710157"]
    assert ds.df["Posting Date"].tolist() == ["2025-10-01", "2025-10-02"]


def test_password_or_corrupt_file_message(tmp_path):
    from anyrecon.ingest import UnreadableFile
    p = tmp_path / "locked.xlsx"
    p.write_bytes(b"\xd0\xcf\x11\xe0 not really a workbook")   # encrypted xlsx files are OLE containers
    with pytest.raises(UnreadableFile, match="password-protected"):
        load(p)


def test_continuation_rows_merged():
    raw = pd.DataFrame([["Date", "Narration", "Amount"], ["01/10/2026", "TRF FROM ADA OKAFOR REF", "100.00"],
                        [None, "042833770659 LAGOS", None], ["02/10/2026", "POS SETTL", "50.00"]],
                       index=[f"P1:R{i}" for i in range(4)])
    df = frame_from_raw(raw, [], merge_continuations=True)
    assert len(df) == 2 and df["Narration"].iloc[0] == "TRF FROM ADA OKAFOR REF 042833770659 LAGOS"


def test_multi_sheet_modes(tmp_path):
    import openpyxl
    from anyrecon.ingest import list_sheets, load_each_sheet
    wb = openpyxl.Workbook()
    for title, rows in [("Oct", [["Ref", "Amount"], ["A1001", 10], ["A1002", 20]]),
                        ("Nov", [["Ref", "Amount"], ["A1003", 30]]),
                        ("Notes", [["Prepared by", "Checked by"], ["x", "y"], ["z", "w"]]),
                        ("Old", [["Ref", "Amount"], ["Z9", 1], ["Z8", 2]])]:
        ws = wb.create_sheet(title)
        for r in rows:
            ws.append(r)
    del wb["Sheet"]
    wb["Old"].sheet_state = "hidden"
    p = tmp_path / "gl.xlsx"
    wb.save(p)
    assert [s["name"] for s in list_sheets(p) if s["hidden"]] == ["Old"]
    stacked = load(p, sheet="*")
    assert len(stacked) == 3 and set(stacked.df["Sheet"]) == {"Oct", "Nov"}
    assert load(p, sheet="Nov").df["Ref"].tolist() == ["A1003"]
    assert [d.name for d in load_each_sheet(p, name="gl")] == ["gl:Oct", "gl:Nov", "gl:Notes"]   # hidden 'Old' skipped


def test_unstructured_narrations():
    L = _ds(pd.DataFrame({"RRN": ["042833770659", "049980710157", "071234567890", "082345678901"],
                          "Amount": ["100.00", "200.00", "400.00", "500.00"]}), "L")
    R = _ds(pd.DataFrame({"Narration": ["Trf frm ADA ref 0428 3377 0659 tnx", "POS049980710157NGN",
                                        "being payment for inv 22 - 0712-3456-7890", "REF:08234S678901 payment"],
                          "Amount": ["100.00", "200.00", "400.00", "500.00"]}), "R")
    r = reconcile(L, R, PairConfig("L", "R", keys=[KeySpec("RRN", "Narration", "nozeros", "extract", "extract_right")],
                                   left_amount="Amount", right_amount="Amount", use_composite=False))
    assert len(r.matches) == 3 and (r.matches.status == "matched").all()
    assert r.matches.rule.str.contains("separators removed").sum() == 2
    right = r.exceptions[r.exceptions.side == "right"].set_index("rows").suggestion
    assert "likely typo or OCR misread" in right["L3"]          # suggested, not matched


def test_composite_never_pairs_refund_with_sale():
    r = _pair({"amt": ["-100.00"], "d": ["2026-10-01"]}, {"amt": ["100.00"], "d": ["2026-10-01"]},
              keys=[], left_amount="amt", right_amount="amt", left_date="d", right_date="d")
    assert len(r.matches) == 0


def test_auto_pairs_links_every_document_once():
    from anyrecon.chain import auto_pairs
    ids = [f"TX{1000 + i}" for i in range(40)]
    a = _ds(pd.DataFrame({"ref": ids, "amount": [100.0 + i for i in range(40)]}), "a")
    b = _ds(pd.DataFrame({"reference": ids, "value": [100.0 + i for i in range(40)]}), "b")
    c = _ds(pd.DataFrame({"txn": ids[:30], "amt": [100.0 + i for i in range(30)]}), "c")
    pairs = auto_pairs({"a": a, "b": b, "c": c})
    assert len(pairs) == 2
    linked = {n for p in pairs for n in p}
    assert linked == {"a", "b", "c"}


def test_percentage_fee_detected_and_applied():
    from anyrecon.chain import reconcile_auto
    ids = [f"TX{1000 + i}" for i in range(30)]
    gross = [200.0 + 7 * i for i in range(30)]
    a = _ds(pd.DataFrame({"ref": ids, "amount": gross}), "a")
    b = _ds(pd.DataFrame({"ref": ids, "amount": [round(g * 0.985, 2) for g in gross]}), "b")
    cfg = PairConfig(left="a", right="b", keys=[KeySpec("ref", "ref", "exact", "exact")], left_amount="amount", right_amount="amount")
    assert reconcile(a, b, cfg).summary["detected_fee_pct"] == 1.5
    res = reconcile_auto(a, b, cfg)
    assert res.config.expected_fee_pct == 1.5
    assert res.summary["matched_groups"] == 30
