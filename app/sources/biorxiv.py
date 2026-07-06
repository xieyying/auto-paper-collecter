"""bioRxiv preprint server. Uses the bioRxiv Content API.

API docs: https://api.biorxiv.org/ 
Search endpoint: https://api.biorxiv.org/search/<term>/<cursor>
"""
import datetime as dt
import httpx
from . import RawItem

API = "https://api.biorxiv.org/search"


def _parse_date(date_str: str):
    """bioRxiv returns dates like '2023-07-03'."""
    if not date_str:
        return None
    try:
        return dt.datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None


async def search(keyword: str, limit: int = 12):
    items = []
    # bioRxiv search API — paginated via cursor
    url = f"{API}/{keyword}/0"
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        try:
            r = await c.get(url)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"[biorxiv] search error: {e}", flush=True)
            return []

    collection = data.get("collection") or []
    for entry in collection[:limit]:
        title = (entry.get("title") or "").strip()
        if not title:
            continue
        authors_str = entry.get("authors", "")
        authors = [a.strip() for a in authors_str.split(";") if a.strip()]
        doi = entry.get("doi", "")
        published = _parse_date(entry.get("date", ""))
        category = entry.get("category", "")

        items.append(RawItem(
            source="bioRxiv",
            title=title,
            abstract=(entry.get("abstract") or "").strip(),
            url=f"https://www.biorxiv.org/content/{doi}v1" if doi else "",
            ext_id=f"biorxiv:{doi}" if doi else f"biorxiv:{title[:60]}",
            authors=authors,
            venue=f"bioRxiv ({category})" if category else "bioRxiv",
            doi=doi,
            published_at=published,
        ))
    return items
