"""Deep search mode: multiple keywords AND-combined with configurable time range.

Strategy: instead of OR-ing each keyword's expansions separately (which would
require an expensive LLM AND-filter pass), we construct API-level AND queries:
each source receives a query containing terms from ALL keywords, so the source
API natively returns papers matching every keyword.  This keeps full metadata
(abstracts) intact and avoids LLM token cost for cross-keyword filtering.
"""
import asyncio
import datetime as dt

from ..sources import RawItem
from ..sources import (arxiv, crossref, semanticscholar, github,
                       huggingface, paperswithcode, nature, acs)
from .dedup import dedup
from .summarize import summarize
from .smart import expand_queries

SOURCE_FUNCS = {
    "arXiv": arxiv.search,
    "Crossref": crossref.search,
    "Google Scholar": semanticscholar.search,
    "GitHub": github.search,
    "HuggingFace": huggingface.search,
    "PapersWithCode": paperswithcode.search,
    "Nature": nature.search,
    "ACS": acs.search,
}

SOURCE_COLORS = {
    "arXiv": "#B31B1B", "Crossref": "#5B6470", "Google Scholar": "#1A73E8",
    "GitHub": "#1F2328", "HuggingFace": "#D97706", "PapersWithCode": "#0EA5A5",
    "Nature": "#D42A14", "ACS": "#00629B",
}


def _ago(dt_obj: dt.datetime) -> str:
    """Human-readable relative time in Chinese."""
    delta = dt.datetime.now() - dt_obj
    h = delta.total_seconds() / 3600
    if h < 1:
        return "刚刚"
    if h < 24:
        return f"{int(h)} 小时前"
    days = int(h // 24)
    if days == 1:
        return "昨天"
    if days < 30:
        return f"{days} 天前"
    months = days // 30
    return f"{months} 个月前"


def _build_and_queries(keywords: list[str],
                       expanded_per_kw: list[list[str]]) -> list[str]:
    """Build AND-combined query strings for API-level search.

    - Original keywords joined (broadest AND query).
    - A few expansion combos to catch synonym/related-term matches.
    Returns at most 4 combined queries.
    """
    queries: list[str] = []
    queries.append(" ".join(keywords))

    alt_sets = [kw_q[1:3] for kw_q in expanded_per_kw]
    if all(alt_sets):
        first_alts = [q[0] for q in alt_sets if q]
        if len(first_alts) == len(keywords):
            q = " ".join(first_alts)
            if q.lower() not in [x.lower() for x in queries]:
                queries.append(q)
        second_alts = [q[1] if len(q) > 1 else q[0] for q in alt_sets if q]
        if len(second_alts) == len(keywords):
            q = " ".join(second_alts)
            if q.lower() not in [x.lower() for x in queries]:
                queries.append(q)

    return queries[:4]


async def deep_search(keywords: list[str], time_range_days: int = 365,
                      enabled_sources: dict[str, bool] | None = None) -> list[dict]:
    """Run a deep search with API-level AND-combined queries.

    Each source receives queries containing terms from ALL keywords, so the
    source API natively returns papers matching every keyword.  This keeps
    full metadata (abstracts) intact with zero LLM token cost for AND logic.
    """
    keywords = [k.strip() for k in keywords if k.strip()]
    if not keywords or len(keywords) > 3:
        return []

    # 1. Expand each keyword
    expanded_per_kw: list[list[str]] = []
    for kw in keywords:
        queries = await expand_queries(kw)
        expanded_per_kw.append(queries[:3])

    # 2. Build AND-combined queries (API-level AND)
    and_queries = _build_and_queries(keywords, expanded_per_kw)

    # 3. Cutoff date
    cutoff = dt.datetime.now() - dt.timedelta(days=time_range_days)

    # 4. Fetch each source with each AND query
    sem = asyncio.Semaphore(4)

    async def _fetch(fn, query: str) -> list:
        async with sem:
            try:
                return await fn(query)
            except Exception as e:
                print(f"[deep-search] error for {query!r}: {e}", flush=True)
                return []

    tasks = [
        _fetch(fn, q)
        for name, fn in SOURCE_FUNCS.items()
        if enabled_sources is None or enabled_sources.get(name, True)
        for q in and_queries
    ]
    results = await asyncio.gather(*tasks)
    items: list[RawItem] = []
    for res in results:
        items.extend(res)

    # 5. Filter by publication date
    items = [it for it in items if it.published_at and it.published_at >= cutoff]

    # 6. Deduplicate
    items = dedup(items)

    # 7. Summarise + serialise
    async def _process(it: RawItem) -> dict:
        summ = await summarize(it) if (it.abstract or it.tldr) else {}
        if not summ.get("tldr"):
            summ["tldr"] = (it.abstract or it.title or "")[:80] + "…" if (it.abstract or it.title) else ""
        if not summ.get("method"):
            summ["method"] = ""
        return {
            "source": it.source,
            "sourceColor": SOURCE_COLORS.get(it.source, "#5B6470"),
            "sourceBg": SOURCE_COLORS.get(it.source, "#5B6470") + "20",
            "title": it.title,
            "url": it.url,
            "abstract": it.abstract,
            "authors": it.authors[:5],
            "authorsStr": ", ".join(it.authors[:4]) + (" et al." if len(it.authors) > 4 else ""),
            "venue": it.venue,
            "doi": it.doi,
            "published": it.published_at.strftime("%Y-%m-%d") if it.published_at else "",
            "publishedAgo": _ago(it.published_at) if it.published_at else "",
            "tldr": summ.get("tldr", ""),
            "method": summ.get("method", ""),
            "contributions": summ.get("contributions", []),
        }

    serialised = await asyncio.gather(*[_process(it) for it in items[:50]])
    return serialised
