"""Papers with Code — papers paired with their official code implementations."""
import datetime as dt
import httpx
from . import RawItem


async def search(keyword: str, limit: int = 15):
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        r = await c.get("https://paperswithcode.com/api/v1/papers/",
                        params={"q": keyword, "items_per_page": limit})
        if r.status_code != 200:
            return []
        try:
            data = r.json()
        except Exception:
            return []   # API occasionally returns an empty/HTML body
    items = []
    for p in (data.get("results") or [])[:limit]:
        if not p.get("title"):
            continue
        d = None
        if p.get("published"):
            try:
                d = dt.datetime.strptime(p["published"][:10], "%Y-%m-%d")
            except ValueError:
                pass
        items.append(RawItem(
            source="PapersWithCode",
            title=" ".join((p.get("title") or "").split()),
            abstract=(p.get("abstract") or "").strip(),
            url=p.get("url_abs") or p.get("url_pdf") or "",
            ext_id=f"pwc:{p.get('id', '')}",
            authors=p.get("authors") or [],
            venue="Papers with Code", doi=p.get("doi", "") or "", published_at=d,
        ))
    return items
