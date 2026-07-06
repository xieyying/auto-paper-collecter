"""Deep search: (kw1_OR) AND (kw2_OR) at the retrieval level.

Strategy:
  1. Each keyword is expanded and searched independently (OR recall).
  2. All results are merged and deduplicated.
  3. A lightweight text-matching AND filter keeps only papers whose
     title+abstract contains key terms from EVERY keyword.
  4. If strict AND yields too few results, relax to best-effort AND
     (papers matching at least N-1 keywords), so the user always
     sees something useful.
"""
import asyncio
import re
import datetime as dt

from ..sources import RawItem
from ..sources import (arxiv, crossref, semanticscholar, github,
                       huggingface, paperswithcode, pubmed, pmc)
from ..sources.pubmed import set_journals as set_pubmed_journals
from .summarize import summarize
from .smart import expand_queries
from ..impact import get_impact_factor

SOURCE_FUNCS = {
    "arXiv": arxiv.search,
    "Crossref": crossref.search,
    "Google Scholar": semanticscholar.search,
    "GitHub": github.search,
    "HuggingFace": huggingface.search,
    "PapersWithCode": paperswithcode.search,
    "PubMed": pubmed.search,
    "PMC": pmc.search,
}

SOURCE_COLORS = {
    "arXiv": "#B31B1B", "Crossref": "#5B6470", "Google Scholar": "#1A73E8",
    "GitHub": "#1F2328", "HuggingFace": "#D97706", "PapersWithCode": "#0EA5A5",

}

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


async def deep_search(keywords: list[str], time_range_days: int = 365,
                      enabled_sources: dict[str, bool] | None = None,
                      db=None) -> list[dict]:
    """Deep search: per-keyword OR recall + best-effort AND filter."""
    keywords = [k.strip() for k in keywords if k.strip()]
    if not keywords or len(keywords) > 3:
        return []

    # 1. Expand each keyword
    expanded_per_kw: list[list[str]] = []
    for kw in keywords:
        queries = await expand_queries(kw)
        expanded_per_kw.append(queries[:3])


    # 2. Fetch each keyword's queries independently
    sem = asyncio.Semaphore(5)

    async def _fetch(fn, query: str) -> list:
        async with sem:
            try:
                return await fn(query)
            except Exception as e:
                print(f"[deep-search] error for {query!r}: {e}", flush=True)
                return []

    async def _fetch_wq(fn, query: str) -> tuple[str, list]:
        return (query, await _fetch(fn, query))

    src_enabled = enabled_sources or {}
    use_all_sources = not enabled_sources or len(enabled_sources) == 0
    all_items: list[RawItem] = []
    for kw_queries in expanded_per_kw:
        tasks = [
            _fetch_wq(fn, q)
            for name, fn in SOURCE_FUNCS.items()
            if use_all_sources or src_enabled.get(name, False)
            for q in kw_queries
        ]
        for query, res in await asyncio.gather(*tasks):
            for it in res:
                existing = getattr(it, "_kw_matches", [])
                if query not in existing:
                    existing.append(query)
                it._kw_matches = existing
            all_items.extend(res)

    # 3. Filter by date + dedup
    if time_range_days and time_range_days > 0:
        cutoff = dt.datetime.now() - dt.timedelta(days=time_range_days)
        all_items = [it for it in all_items if it.published_at and it.published_at >= cutoff]
    # time_range_days <= 0 means no date limit

    # Custom dedup that merges _kw_matches
    from .dedup import _key as dk
    seen = {}
    for it in all_items:
        k = dk(it)
        if k in seen:
            existing = seen[k]
            # Merge _kw_matches
            cur_matches = getattr(existing, "_kw_matches", [])
            new_matches = getattr(it, "_kw_matches", [])
            for q in new_matches:
                if q not in cur_matches:
                    cur_matches.append(q)
            existing._kw_matches = cur_matches
            # Keep richer abstract
            if (len(it.abstract or "") > len(existing.abstract or "")) or (it.tldr and not existing.tldr):
                # Transfer merged matches to the better copy
                it._kw_matches = cur_matches
                seen[k] = it
        else:
            seen[k] = it
    all_items = list(seen.values())

    # 4. Fetch-based AND filter:
    #    Use _kw_matches (which queries actually found this paper) to determine
    #    if a paper was found by BOTH keyword groups' expanded queries.
    #    e.g. keyword A=["ESM2", "ESM2 protein...", "ESM2 evolutionary..."]
    #         keyword B=["protein design", "protein engineering", ...]
    #    A paper passes strict AND iff at least one A-query AND one B-query matched it.
    if len(expanded_per_kw) > 1:
        # Build a set of expanded queries per original keyword group
        kw_query_sets = [set(qs) for qs in expanded_per_kw]
        scored: list[tuple[int, RawItem]] = []
        for it in all_items:
            matches = getattr(it, "_kw_matches", []) or []
            match_set = set(m.lower() for m in matches)
            # Count how many keyword groups this paper was found by
            matched_groups = sum(
                1 for qset in kw_query_sets
                if any(q.lower() in match_set for q in qset)
            )
            scored.append((matched_groups, it))
        scored.sort(key=lambda x: -x[0])

        strict_and = [it for m, it in scored if m == len(kw_query_sets)]
        relaxed = [it for m, it in scored if m >= len(kw_query_sets) - 1]

        if len(strict_and) >= 5:
            all_items = strict_and
        elif len(relaxed) >= 3:
            all_items = relaxed
        else:
            all_items = [it for m, it in scored if m > 0] or all_items[:10]

        print(f"[deep-search] AND filter: {len(scored)} -> "
              f"strict={len(strict_and)}, relaxed={len(relaxed)}, "
              f"final={len(all_items)}", flush=True)

    # 4b. Secondary text filter:
    #     Removes false positives where the search API returned a paper that
    #     doesn't actually contain any query-relevant terms in title/abstract.
    #     For each keyword group that matched, checks that at least one query
    #     has ≥2 tokens appearing in the paper's text.
    if all_items and expanded_per_kw:
        _T2 = re.compile(r"[a-z0-9]{3,}")
        kw_qsets = [set(qs) for qs in expanded_per_kw]
        filtered = []
        for it in all_items:
            text = f"{it.title or ''} {it.abstract or ''}".lower()
            text_tokens = set(_T2.findall(text))
            matches = getattr(it, "_kw_matches", []) or []
            match_set = set(m.lower() for m in matches)
            ok = True
            for qset in kw_qsets:
                matching = [q for q in qset if q.lower() in match_set]
                if not matching:
                    continue
                group_ok = False
                for q in matching:
                    qt = _T2.findall(q.lower())
                    overlap = sum(1 for t in qt if t in text_tokens)
                    if overlap >= 2:
                        group_ok = True
                        break
                if not group_ok:
                    ok = False
                    break
            if ok:
                filtered.append(it)
        if filtered:
            all_items = filtered
            print(f"[deep-search] text filter: kept {len(filtered)}/{len(scored) if 'scored' in dir() else len(all_items)}", flush=True)

    # Tag each paper with the ACTUAL queries that matched it
    for it in all_items:
        matches = getattr(it, "_kw_matches", [])
        # Deduplicate while preserving order
        seen_q = set()
        unique = []
        for q in matches:
            if q.lower() not in seen_q:
                seen_q.add(q.lower())
                unique.append(q)
        it.topic = " | ".join(unique) if len(unique) > 1 else (unique[0] if unique else "")

    # Configure PubMed journal filter
    pm_journals = getattr(db, "_pubmed_journals", None)
    set_pubmed_journals(pm_journals)

    # 5. Summarise + serialise
    # Look up existing paper IDs and saved state from DB
    _paper_ids: dict[str, int] = {}
    _saved_map: dict[int, tuple[bool, str]] = {}  # paper_id → (saved, feedback)
    if db is not None:
        from ..models import Paper as PaperModel, SavedItem
        all_ext_ids = [it.ext_id for it in all_items[:50] if it.ext_id]
        if all_ext_ids:
            for row in db.query(PaperModel.id, PaperModel.ext_id).filter(
                    PaperModel.ext_id.in_(all_ext_ids)).all():
                _paper_ids[row.ext_id] = row.id
            # Batch load saved state
            for sv in db.query(SavedItem).filter(
                    SavedItem.paper_id.in_(list(_paper_ids.values()))).all():
                _saved_map[sv.paper_id] = (sv.saved or False, sv.feedback or "")

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
            "topic": getattr(it, "topic", ""),
            "title": it.title,
            "url": it.url,
            "abstract": it.abstract,
            "authors": it.authors[:5],
            "authorsStr": ", ".join(it.authors[:4]) + (" et al." if len(it.authors) > 4 else ""),
            "venue": it.venue,
            "if": get_impact_factor(
                getattr(it, "issn", None) or
                getattr(it, "eissn", None) or
                getattr(it, "journal_full", None) or
                it.venue),
            "doi": it.doi,
            "published": it.published_at.strftime("%Y-%m-%d") if it.published_at else "",
            "publishedAgo": _ago(it.published_at) if it.published_at else "",
            "tldr": summ.get("tldr", ""),
            "method": summ.get("method", ""),
            "contributions": summ.get("contributions", []),
            "extId": it.ext_id,
            "id": _paper_ids.get(it.ext_id, None),
            "saved": _saved_map.get(_paper_ids.get(it.ext_id), (False, ""))[0],
            "feedback": _saved_map.get(_paper_ids.get(it.ext_id), (False, ""))[1],
        }

    serialised = await asyncio.gather(*[_process(it) for it in all_items[:50]])
    return serialised
