"""Similarity scoring. Uses rapidfuzz when installed (fast); otherwise a pure-Python fallback
(used by the Browser edition, where rapidfuzz isn't available)."""
from __future__ import annotations

try:
    from rapidfuzz import fuzz as _fuzz, process as _process

    def ratio(a: str, b: str) -> float:
        return _fuzz.ratio(a, b)

    def partial_ratio(a: str, b: str) -> float:
        return _fuzz.partial_ratio(a, b)

    def extract_one(query: str, choices: dict, cutoff: float):
        """-> (value, score, key) or None"""
        return _process.extractOne(query, choices, scorer=_fuzz.ratio, score_cutoff=cutoff)

except ImportError:  # pragma: no cover - exercised in the browser build
    from difflib import SequenceMatcher

    def ratio(a: str, b: str) -> float:
        return 100.0 * SequenceMatcher(None, a, b).ratio()

    def partial_ratio(a: str, b: str) -> float:
        short, long_ = (a, b) if len(a) <= len(b) else (b, a)
        if not short:
            return 0.0
        n = len(short)
        best = 0.0
        for i in range(0, max(1, len(long_) - n + 1)):
            best = max(best, ratio(short, long_[i:i + n]))
            if best == 100.0:
                break
        return best

    def extract_one(query: str, choices: dict, cutoff: float):
        best = None
        for k, v in choices.items():
            if abs(len(v) - len(query)) > max(2, len(query) // 5):
                continue
            s = ratio(query, v)
            if s >= cutoff and (best is None or s > best[1]):
                best = (v, s, k)
        return best
