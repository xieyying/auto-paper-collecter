"""Deep search: multiple keywords AND-combined at the API level.

Query construction: (kw1_orig OR kw1_exp1 OR ...) AND (kw2_orig OR kw2_exp1 OR ...)

arXiv supports native boolean syntax; other sources receive a concatenated
query whose relevance ranking naturally favours papers matching all keywords.
"""
import asyncio
import datetime as dt
import httpx
import feedparser

from ..sources import RawItem
from ..sources import (arxiv, crossref, semanticscholar, github,
                       huggingface, paperswithcode, nature, acs)
from .dedup import dedup
from .summarize import summarize
from .smart import expand_queries

ARXIV_API = "http://export.arxiv.org/api/query"

SOURCE_FUNCS = {
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


def _build_arxiv_query(expanded_per_kw: list[list[str]]) -> str:
    """Build arXiv boolean query.

    (all:"kw1_orig" OR all:"kw1_exp1" OR ...)
    AND (all:"kw2_orig" OR all:"kw2_exp1" OR ...)
    """
    clauses = []
    for terms in expanded_per_kw:
        or_parts = [f'all:"{t}"' for t in terms[:3]]
        clauses.append(f"({' OR '.join(or_parts)})")
    return " AND ".join(clauses)


async def _arxiv_and_search(expanded_per_kw: list[list[str]],
                            max_results: int = 20) -> list:
    """Search arXiv with boolean AND query across keywords."""
    query = _build_arxiv_query(expanded_per_kw)
    params = {
        "search_query": query,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": max_results,
    }
    text = None
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        for attempt in range(2):
            r = await c.get(ARXIV_API, params=params)
            if r.status_code == 429 and attempt == 0:
                await asyncio.sleep(3)
                continue
            r.raise_for_status()
            text = r.text
            break
    if not text:
        return []

    feed = feedparser.parse(text)
    items = []
    for e in feed.entries:
        published = None
        if getattr(e, "published_parsed", None):
            published = dt.datetime(*e.published_parsed[:6])
        items.append(RawItem(
            source="arXiv",
            title=" ".join(e.title.split()),
            abstract=getattr(e, "summary", "").strip(),
            url=e.link,
            ext_id=f"arXiv:{e.id.split('/abs/')[-1]}",
            authors=[a.get("name", "") for a in getattr(e, "authors", [])],
            venue="arXiv",
            doi=getattr(e, "arxiv_doi", "") or "",
            published_at=published,
        ))
    return items


async def deep_search(keywords: list[str], time_range_days: int = 365,
                      enabled_sources: dict[str, bool] | None = None) -> list[dict]:
    """Deep search: (kw1_OR ...) AND (kw2_OR ...) AND ... at the API level.

    arXiv uses native boolean query syntax.
    Other sources receive a concatenated query string for relevance-based AND.
    """
    keywords = [k.strip() for k in keywords if k.strip()]
    if not keywords or len(keywords) > 3:
        return []

    # 1. Expand each keyword
    expanded_per_kw: list[list[str]] = []
    for kw in keywords:
        queries = await expand_queries(kw)
        expanded_per_kw.append(queries[:3])

    # 2. Cutoff date
    cutoff = dt.datetime.now() - dt.timedelta(days=time_range_days)

    # 3. Combined text query for non-ArXiv sources
    text_query = " ".join(keywords)

    # 4. Fetch concurrently
    sem = asyncio.Semaphore(4)

    async def _fetch(fn, query: str) -> list:
        async with sem:
            try:
                return await fn(query)
            except Exception as e:
                print(f"[deep-search] error: {e}", flush=True)
                return []

    tasks = []
    # arXiv — boolean AND query
    src_enabled = enabled_sources or {}
    if src_enabled.get("arXiv", True):
        tasks.append(_arxiv_and_search(expanded_per_kw))
    # Other sources — text query
    for name, fn in SOURCE_FUNCS.items():
        if src_enabled.get(name, True):
            tasks.append(_fetch(fn, text_query))

    results = await asyncio.gather(*tasks)
    items: list[RawItem] = []
    for res in results:
        items.extend(res)

    # 5. Filter by date
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
