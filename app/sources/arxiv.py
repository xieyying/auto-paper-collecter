"""arXiv official API. Free, no key. Atom XML."""
import asyncio
import datetime as dt
import httpx
import feedparser
from . import RawItem

API = "http://export.arxiv.org/api/query"


async def search(keyword: str, max_results: int = 15):
    params = {
        "search_query": f'all:"{keyword}"',
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": max_results,
    }
    # arXiv rate-limits bursts with 429; retry once after a polite pause.
    text = None
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        for attempt in range(2):
            r = await c.get(API, params=params)
            if r.status_code == 429 and attempt == 0:
                await asyncio.sleep(3)
                continue
            r.raise_for_status()
            text = r.text
            break

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
