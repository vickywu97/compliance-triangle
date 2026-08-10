"""Knowledge-base access — a thin, import-safe wrapper over the Bench loader.

The Bench repo is imported lazily (only when actually loading), so importing
this module never fails even if the Bench path is misconfigured — the error
surfaces at call time with a clear message.
"""
from __future__ import annotations

from typing import Dict, Optional

from .config import ensure_bench_importable

_laws_cache: Optional[Dict] = None


def distinct_laws(laws: Dict) -> list:
    """``laws`` is keyed by name/code/alias, so ``len(laws)`` overcounts.
    Collapse to the distinct underlying ``Law`` objects."""
    return list({id(v): v for v in laws.values()}.values())


def count_laws(laws: Dict) -> int:
    """Number of distinct laws (not resolution keys)."""
    return len(distinct_laws(laws))


def count_articles(laws: Dict) -> int:
    """Total number of distinct articles across all laws.

    Articles live under ``law.revisions[].articles`` (one snapshot per
    effective date). We take the union of article keys per law so temporal
    revisions don't double-count.
    """
    total = 0
    for law in distinct_laws(laws):
        keys = set()
        for rev in law.revisions.values():
            keys.update(rev.articles.keys())
        total += len(keys)
    return total


def load_kb() -> Dict:
    """Load all verified laws from the Bench repo. Cached for the process."""
    global _laws_cache
    if _laws_cache is None:
        ensure_bench_importable()
        from knowledge_base.loader import load_laws
        _laws_cache = load_laws()
    return _laws_cache


def normalize_law_name(laws: Dict, raw_name: str) -> str:
    """Map a Chinese law name (as an LLM might write it) to its KB law_code.

    Checks exact code, exact full name, and alias membership. Falls back to the
    raw name unchanged (so the resolver can still report UNKNOWN_LAW).
    """
    raw = (raw_name or "").strip()
    if not raw:
        return raw
    if raw in laws:
        return raw
    for code, law in laws.items():
        if raw == law.name or raw in (law.aliases or []):
            return code
    return raw


def resolve(law_name: str, article_no: str, as_of_date: str, laws: Dict):
    """Resolve an article against the verified KB at ``as_of_date``.

    Routes a Chinese law name to its code for current-law lookups, but passes
    a *deprecated* law name (e.g. 旧公司法 / 合同法) through unchanged so the
    Bench resolver can flag it as a temporal hallucination.

    Returns a ``ResolveResult`` with ``found``, ``used_deprecated_alias``,
    ``deprecated_repealed_date``, ``content``, ``verification_status`` and
    ``note``.
    """
    ensure_bench_importable()
    from benchmark.extract import DEPRECATED_LAW_NAMES
    from knowledge_base.loader import resolve_article

    if law_name in DEPRECATED_LAW_NAMES:
        # Pass the deprecated name verbatim so the resolver flags it.
        lookup = law_name
    else:
        lookup = normalize_law_name(laws, law_name)
    return resolve_article(laws, lookup, article_no, as_of_date)
