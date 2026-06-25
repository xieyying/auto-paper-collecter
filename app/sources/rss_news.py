"""Academic news / blogs via RSS. Filtered by keyword in title or summary."""
import datetime as dt
import asyncio
import feedparser
from . import RawItem
from ..config import settings


def _parse_one(url: str, keyword: str, limit: int = 8):
    feed = feedparser.parse(url)
    kw = keyword.lower()
    items = []
    for e in feed.entries[:40]:
        blob = (getattr(e, "title", "") + " " + getattr(e, "summary", "")).lower()
        if kw not in blob:
            continue
        published = None
        if getattr(e, "published_parsed", None):
            published = dt.datetime(*e.published_parsed[:6])
        items.append(RawItem(
            source="学术新闻",
            title=" ".join(getattr(e, "title", "").split()),
            abstract=getattr(e, "summary", "")[:600],
            url=getattr(e, "link", ""),
            ext_id=f"rss:{getattr(e, 'id', getattr(e, 'link', ''))}",
            authors=[getattr(e, "author", "")] if getattr(e, "author", "") else [],
            venue=feed.feed.get("title", "News") if feed.feed else "News",
            published_at=published,
        ))
        if len(items) >= limit:
            break
    return items


async def search(keyword: str, limit: int = 8):
    loop = asyncio.get_event_loop()
    out = []
    for url in settings.rss_list:
        try:
            items = await loop.run_in_executor(None, _parse_one, url, keyword, limit)
            out.extend(items)
        except Exception:
            continue
    return out
