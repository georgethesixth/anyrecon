"""Pre-commit hook: block commits that contain card numbers (Luhn-valid PANs).

Well-known public test card numbers used in documentation are allowed.
Usage (via .pre-commit-config.yaml) or directly:  python scripts/pan_scan.py FILE [FILE ...]
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from anyrecon.pci import PAN_RE, is_pan  # noqa: E402

ALLOWED = {"4111111111111111", "5555555555554444", "4000056655665556", "378282246310005", "6011111111111117",
           "5105105105105100", "4242424242424242", "4012888888881881"}


def main(paths):
    bad = 0
    for p in paths:
        try:
            text = Path(p).read_text(encoding="utf-8", errors="ignore")
        except (OSError, IsADirectoryError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for m in PAN_RE.finditer(line):
                d = re.sub(r"\D", "", m.group(0))
                if is_pan(d) and d not in ALLOWED:
                    print(f"{p}:{n}: possible card number {d[:6]}…{d[-4:]}. Remove it or replace with a public test number")
                    bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
