"""Semantic Scholar Graph API. Free (key optional). Gives a ready TLDR."""
import asyncio
import datetime as dt
import httpx
from . import RawItem
from ..config import settings

API = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS = "title,abstract,authors,url,year,venue,tldr,publicationDate,externalIds"


async def search(keyword: str, limit: int = 15):
    # fieldsOfStudy keeps Semantic Scholar results inside computer science.
    params = {"query": keyword, "limit": limit, "fields": FIELDS,
              "fieldsOfStudy": "Computer Science"}
    headers = {}
    if settings.SEMANTIC_SCHOLAR_KEY:
        headers["x-api-key"] = settings.SEMANTIC_SCHOLAR_KEY
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        data = None
        for attempt in range(3):
            r = await c.get(API, params=params, headers=headers)
            if r.status_code == 429:               # rate limited (common without a key)
                if attempt < 2:
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                return []                          # give up gracefully
            r.raise_for_status()
            data = r.json()
            break
        if data is None:
            return []

    items = []
    for p in data.get("data", []) or []:
        published = None
        if p.get("publicationDate"):
            try:
                published = dt.datetime.strptime(p["publicationDate"], "%Y-%m-%d")
            except ValueError:
                pass
        if not published and p.get("year"):
            published = dt.datetime(p["year"], 1, 1)
        ext = p.get("externalIds", {}) or {}
        doi = ext.get("DOI", "") or ""
        items.append(RawItem(
            source="Google Scholar",   # S2 stands in for general scholarly search
            title=" ".join((p.get("title") or "").split()),
            abstract=(p.get("abstract") or "").strip(),
            url=p.get("url", ""),
            ext_id=f"s2:{p.get('paperId', '')}",
            authors=[a.get("name", "") for a in (p.get("authors") or [])],
            venue=p.get("venue", "") or "",
            doi=doi,
            published_at=published,
            tldr=(p.get("tldr") or {}).get("text", "") if p.get("tldr") else "",
        ))
    return items
