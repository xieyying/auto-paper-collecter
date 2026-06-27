"""HuggingFace Papers — trending, arXiv-linked papers (community upvotes)."""
import datetime as dt
import httpx
from . import RawItem


async def search(keyword: str, limit: int = 15):
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        r = await c.get("https://huggingface.co/api/papers/search", params={"q": keyword})
        if r.status_code != 200:
            return []
        data = r.json()
    items = []
    for entry in (data or [])[:limit]:
        p = entry.get("paper", entry) if isinstance(entry, dict) else {}
        if not p or not p.get("title"):
            continue
        pid = p.get("id", "")
        d = None
        pub = p.get("publishedAt") or p.get("published_at") or ""
        if pub:
            try:
                d = dt.datetime.strptime(pub[:10], "%Y-%m-%d")
            except ValueError:
                pass
        authors = [a.get("name", "") if isinstance(a, dict) else str(a)
                   for a in (p.get("authors") or [])]
        items.append(RawItem(
            source="HuggingFace",
            title=" ".join((p.get("title") or "").split()),
            abstract=(p.get("summary") or "").strip(),
            url=f"https://huggingface.co/papers/{pid}" if pid else "",
            ext_id=f"hf:{pid}" if pid else f"hf:{(p.get('title') or '')[:50]}",
            authors=authors, venue="HuggingFace", doi="", published_at=d,
        ))
    return items
