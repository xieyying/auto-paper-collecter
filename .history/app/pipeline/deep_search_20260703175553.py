"""Deep search mode: multiple keywords AND-combined with configurable time range.

Unlike the always-on radar (which ORs expanded queries for one keyword),
deep search accepts up to 3 keywords, expands each independently, searches
each keyword individually (broad OR recall), then uses LLM filtering to
keep only papers relevant to ALL keywords simultaneously (AND across keywords).

This gives broad recall from source APIs while ensuring the AND semantic.
"""
import asyncio
import json
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


async def _filter_all_keywords(items: list, keywords: list[str]) -> list:
    """Keep items relevant to ALL keywords simultaneously (AND across keywords).

    Uses LLM to judge — each paper must be meaningfully about every keyword.
    Fail-open: if LLM is unavailable, keep everything (better to over-include).
    """
    if not items or len(keywords) < 2:
        return items

    domain = "计算机科学"
    system = (
        f"你是{domain}领域文献筛选助手。给定 {len(keywords)} 个研究关键词和若干论文（标题+摘要），"
        f"逐篇判断是否同时与<b>所有</b>关键词相关。只有同时满足所有关键词的才保留。"
        f"严格只输出 JSON 数组，每项形如 {{\"i\":序号,\"keep\":true 或 false}}，不要任何其它文字。"
    )

    kw_list = "、".join(keywords)
    keep = [True] * len(items)
    batch_size = 20

    async def _batch(start: int, chunk: list):
        listing = "\n\n".join(
            f'{j}. 标题：{it.title}\n   摘要：{(it.abstract or "")[:300]}'
            for j, it in enumerate(chunk))
        user = f"关键词：{kw_list}\n\n论文列表：\n{listing}"
        raw = await chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.0, max_tokens=1200, timeout=90,
        )
        if not raw:
            return
        m = _ARR.search(raw)
        if not m:
            return
        try:
            for o in json.loads(m.group(0)):
                j = int(o["i"])
                if 0 <= j < len(chunk):
                    keep[start + j] = bool(o.get("keep"))
        except Exception:
            pass

    await asyncio.gather(*[
        _batch(start, items[start:start + batch_size])
        for start in range(0, len(items), batch_size)
    ])
    kept = [it for i, it in enumerate(items) if keep[i]]
    return kept or items  # fall back to all if everything was rejected


async def deep_search(keywords: list[str], time_range_days: int = 365,
                      enabled_sources: dict[str, bool] | None = None) -> list[dict]:
    """Run a deep search with AND-combined expanded keywords.

    Strategy: each keyword is searched independently (OR within keyword for broad
    recall), then the LLM filters to keep only papers relevant to ALL keywords
    (AND across keywords).

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

    # 2. Cutoff date for time-range filter
    cutoff = dt.datetime.now() - dt.timedelta(days=time_range_days)

    # 3. Fetch each keyword's expanded queries independently (OR recall)
    sem = asyncio.Semaphore(4)

    async def _fetch(fn, query: str) -> list:
        async with sem:
            try:
                return await fn(query)
            except Exception as e:
                print(f"[deep-search] error for {query!r}: {e}", flush=True)
                return []

    # Collect results per keyword separately so we know which keyword matched
    per_kw_results: list[list[RawItem]] = []
    for kw_queries in expanded_per_kw:
        kw_items: list[RawItem] = []
        tasks = [
            _fetch(fn, q)
            for name, fn in SOURCE_FUNCS.items()
            if enabled_sources is None or enabled_sources.get(name, True)
            for q in kw_queries
        ]
        for res in await asyncio.gather(*tasks):
            kw_items.extend(res)
        per_kw_results.append(kw_items)

    # 4. Merge all results (union) before filtering
    all_items: list[RawItem] = []
    for items in per_kw_results:
        all_items.extend(items)

    # 5. Filter by publication date
    all_items = [it for it in all_items if it.published_at and it.published_at >= cutoff]

    # 6. Deduplicate
    all_items = dedup(all_items)

    # 7. LLM filter: keep only items relevant to ALL keywords (AND across keywords)
    if len(keywords) > 1:
        before = len(all_items)
        all_items = await _filter_all_keywords(all_items, keywords)
        print(f"[deep-search] AND filter: {before} -> {len(all_items)}", flush=True)

    # 8. Summarise top results and serialise
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

    serialised = await asyncio.gather(*[_process(it) for it in all_items[:50]])
    return serialised
