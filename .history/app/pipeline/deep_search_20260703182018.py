"""Deep search: (kw1_OR) AND (kw2_OR) at the retrieval level.

Strategy:
  1. Each keyword is expanded and searched independently (OR recall).
  2. Results are merged and a lightweight text-matching AND filter keeps
     only papers whose title+abstract contains key terms from EVERY keyword.
  3. No LLM used for AND filtering — pure string matching, zero token cost.

This ensures broad recall + full metadata (abstracts) + cross-keyword AND.
"""
import asyncio
import re
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

# Tokenizer: split into lowercase alphanumeric tokens
_TOK = re.compile(r"[a-z0-9]+")


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


def _extract_key_tokens(keyword: str) -> set[str]:
    """Extract meaningful low-frequency tokens from a keyword phrase.

    Strips common stopwords so we match on the distinctive content words.
    Returns a set of lowercase tokens the paper MUST contain evidence of.
    """
    STOP = {"a","an","the","of","in","on","at","to","for","with","by","and",
            "or","not","is","are","was","were","be","been","has","have","had",
            "do","does","did","will","would","could","should","may","might",
            "this","that","these","those","its","their","our","your","from",
            "into","through","during","before","after","above","below","between",
            "out","off","over","under","again","further","then","once","here",
            "there","when","where","why","how","all","each","every","both",
            "few","more","most","other","some","such","no","nor","only","own",
            "same","so","than","too","very","just","because","as","about",
            "based","using","new","novel","approach","method","system",
            "study","analysis","application"}
    tokens = _TOK.findall(keyword.lower())
    return {t for t in tokens if t not in STOP and len(t) > 2}


def _matches_all_keywords(text: str, kw_tokens: list[set[str]]) -> bool:
    """Check if `text` contains at least one significant token from EACH keyword."""
    if not text:
        return True  # can't judge → keep
    tokens = set(_TOK.findall(text.lower()))
    for needed in kw_tokens:
        if needed.isdisjoint(tokens):
            return False
    return True


async def deep_search(keywords: list[str], time_range_days: int = 365,
                      enabled_sources: dict[str, bool] | None = None) -> list[dict]:
    """Deep search: per-keyword OR recall + lightweight text AND filter.

    Args:
        keywords: Up to 3 search keywords.
        time_range_days: Look back window (default 1 year).
        enabled_sources: Per-source enable map (None = all enabled).

    Returns:
        List of serialised result dicts with full metadata + AI summaries.
    """
    keywords = [k.strip() for k in keywords if k.strip()]
    if not keywords or len(keywords) > 3:
        return []

    # 0. Precompute key tokens for AND filter (one set per keyword)
    kw_tokens = [_extract_key_tokens(kw) for kw in keywords]

    # 1. Expand each keyword
    expanded_per_kw: list[list[str]] = []
    for kw in keywords:
        queries = await expand_queries(kw)
        expanded_per_kw.append(queries[:3])

    # 2. Cutoff date
    cutoff = dt.datetime.now() - dt.timedelta(days=time_range_days)

    # 3. Fetch each keyword's expanded queries independently (OR recall)
    sem = asyncio.Semaphore(5)

    async def _fetch(fn, query: str) -> list:
        async with sem:
            try:
                return await fn(query)
            except Exception as e:
                print(f"[deep-search] error for {query!r}: {e}", flush=True)
                return []

    src_enabled = enabled_sources or {}
    all_items: list[RawItem] = []
    for kw_queries in expanded_per_kw:
        tasks = [
            _fetch(fn, q)
            for name, fn in SOURCE_FUNCS.items()
            if src_enabled.get(name, True)
            for q in kw_queries
        ]
        for res in await asyncio.gather(*tasks):
            all_items.extend(res)

    # 4. Filter by publication date
    all_items = [it for it in all_items if it.published_at and it.published_at >= cutoff]

    # 5. Deduplicate
    all_items = dedup(all_items)

    # 6. Lightweight AND filter: title+abstract must contain at least one
    #    significant token from EACH keyword.  No LLM cost.
    if len(kw_tokens) > 1:
        before = len(all_items)
        kept = []
        for it in all_items:
            haystack = f"{it.title} {it.abstract}"
            if _matches_all_keywords(haystack, kw_tokens):
                kept.append(it)
        all_items = kept or all_items  # fall back if everything filtered out
        print(f"[deep-search] AND filter: {before} -> {len(all_items)}", flush=True)

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

    serialised = await asyncio.gather(*[_process(it) for it in all_items[:50]])
    return serialised
