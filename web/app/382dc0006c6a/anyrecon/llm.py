"""Optional AI layer. The engine works fully without it.

What the AI is allowed to do:   explain results, label columns, suggest rules.
What it is never allowed to do: decide a match. Every match is made by deterministic code.

What leaves the machine: column names, profile statistics, value *shapes* (e.g. 'AA-99999999'),
counts and summary figures. Never row values, unless share_masked_samples=True, and even then
only values that have already passed the PCI guard (PANs masked, SAD dropped).

Enable with:  pip install anthropic  and  export ANTHROPIC_API_KEY=...
Model:        ANYRECON_LLM_MODEL (default below)
"""
from __future__ import annotations

import json
import os

DEFAULT_MODEL = os.environ.get("ANYRECON_LLM_MODEL", "claude-sonnet-5-5")


def available() -> bool:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def _ask(system: str, payload: dict, max_tokens: int = 900) -> str:
    import anthropic
    client = anthropic.Anthropic()
    msg = client.messages.create(model=DEFAULT_MODEL, max_tokens=max_tokens, system=system,
                                 messages=[{"role": "user", "content": json.dumps(payload, default=str)}])
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()


def explain(results: dict, share_masked_samples: bool = False) -> str | None:
    """Plain-language commentary on a reconciliation run, for the Summary sheet."""
    if not available():
        return None
    payload = {}
    for name, r in results.items():
        item = dict(summary=r.summary, insights=r.insights, rules=[k.label() for k in r.config.keys],
                    fee_pct=r.config.expected_fee_pct, date_window=r.config.date_window_days)
        if share_masked_samples and len(r.exceptions):
            item["exception_samples"] = r.exceptions.head(15)[["category", "detail", "suggestion"]].to_dict("records")
        payload[name] = item
    system = ("You are a reconciliation analyst. Explain the results below to a finance operations lead in under "
              "180 words: what reconciled, the material breaks by category and value, the likely root cause of each "
              "pattern, and the next 3 actions. Do not invent figures; use only the numbers given.")
    try:
        return _ask(system, payload)
    except Exception as e:  # network, auth, model errors: never break a run
        return f"(AI commentary unavailable: {type(e).__name__})"


def label_columns(profiles_by_ds: dict) -> dict | None:
    """Ask for semantic labels (rrn, session_id, amount, ...) from names + shapes only."""
    if not available():
        return None
    payload = {ds: [dict(name=p.name, kind=p.kind, shape=p.top_shape, uniqueness=p.uniqueness, avg_len=p.avg_len)
                    for p in profs.values()] for ds, profs in profiles_by_ds.items()}
    system = ("Label each column with one of: rrn, session_id, stan, reference, batch, amount, fee, balance, date, "
              "narration, merchant, status, pan_token, other. Reply with JSON only: {dataset: {column: label}}.")
    try:
        return json.loads(_ask(system, payload, 600))
    except Exception:
        return None
