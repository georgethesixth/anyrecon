"""anyrecon: reconcile any set of documents. The AI layer proposes how, the engine
decides deterministically, and every decision is logged."""
__version__ = "0.3.0"
__released__ = "2026-11-16"   # keep in step with CHANGELOG.md

from .ingest import load  # noqa: E402
from .discover import discover  # noqa: E402
from .match import AggregateSpec, KeySpec, PairConfig, reconcile  # noqa: E402
from .chain import auto_config, run_all  # noqa: E402

__all__ = ["load", "discover", "reconcile", "auto_config", "run_all", "PairConfig", "KeySpec", "AggregateSpec"]
