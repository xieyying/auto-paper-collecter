"""Deep search mode: multiple keywords AND-combined with configurable time range.

Unlike the always-on radar (which ORs expanded queries for one keyword),
deep search accepts up to 3 keywords, expands each independently, generates
AND-combined queries (Cartesian product: one term per keyword), fetches every
source, filters by time range, deduplicates, and summarizes.

Typical use: a focused literature sweep with wider time window.
"""
import asyncio
import datetime as dt
from itertools import product

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

# Source display metadata
SOURCE_ICONS = {
    "arXiv": "📄", "Crossref": "📘", "Google Scholar": "🎓",
    "GitHub": "💻", "HuggingFace": "🤗", "PapersWithCode": "🔬",
    "Nature": "🌿", "ACS": "🧪",
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


async def deep_search(keywords: list[str], time_range_days: int = 365,
                      enabled_sources: dict[str, bool] | None = None) -> list[dict]:
    """Run a deep search with AND-combined expanded keywords.

    Args:
        keywords: Up to 3 search keywords.
        time_range_days: Look back window (default 1 year).
        enabled_sources: Per-source enable map (None = all enabled).

    Returns:
        List of serialised result dicts with title, authors, TLDR, etc.
    """
    keywords = [k.strip() for k in keywords if k.strip()]
    if not keywords or len(keywords) > 3:
        return []

    # 1. Expand each keyword into associative queries (cached by smart.py)
    expanded_per_kw: list[list[str]] = []
    for kw in keywords:
        queries = await expand_queries(kw)
        expanded_per_kw.append(queries[:3])  # cap at 3 per keyword

    # 2. Generate AND-combined queries: Cartesian product (one term per keyword)
    #    e.g. kw1→[a,b], kw2→[c,d] → ["a c", "a d", "b c", "b d"]
    combos = list(product(*expanded_per_kw))
    combined_queries = [" ".join(combo) for combo in combos]
    combined_queries = combined_queries[:6]  # limit API calls

    # 3. Cutoff date for time-range filter
    cutoff = dt.datetime.now() - dt.timedelta(days=time_range_days)

    # 4. Fetch from all sources concurrently
    sem = asyncio.Semaphore(4)  # politeness cap

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
        for q in combined_queries
    ]
    results = await asyncio.gather(*tasks)
    items: list[RawItem] = []
    for res in results:
        items.extend(res)

    # 5. Filter by publication date
    items = [it for it in items if it.published_at and it.published_at >= cutoff]

    # 6. Deduplicate across sources
    items = dedup(items)

    # 7. Summarise top results and serialise
    async def _process(it: RawItem) -> dict:
        summ = await summarize(it) if (it.abstract or it.tldr) else {}
        if not summ.get("tldr"):
            summ["tldr"] = (it.abstract or it.title or "")[:80] + "…" if (it.abstract or it.title) else ""
        if not summ.get("method"):
            summ["method"] = ""
        return {
            "source": it.source,
            "sourceIcon": SOURCE_ICONS.get(it.source, "📄"),
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
