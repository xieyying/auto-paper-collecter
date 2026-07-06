"""ChemRxiv preprint server. Uses the ChemRxiv public API.

API: https://chemrxiv.org/engage/chemrxiv/public-api/v1/search
"""
import datetime as dt
import httpx
from . import RawItem

API = "https://chemrxiv.org/engage/chemrxiv/public-api/v1/search"


def _parse_iso_date(date_str: str):
    """Parse ISO-format dates like '2023-07-03T12:00:00.000Z'."""
    if not date_str:
        return None
    try:
        # Strip timezone and parse
        ts = date_str.replace("Z", "").split("T")[0]
        return dt.datetime.strptime(ts, "%Y-%m-%d")
    except (ValueError, IndexError):
        return None


async def search(keyword: str, limit: int = 12):
    headers = {
        "Accept": "application/json",
        "User-Agent": "ScholarPulse/1.0",
    }
    params = {
        "term": keyword,
        "limit": limit,
        "sort": "recent",
    }
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        try:
            r = await c.get(API, params=params, headers=headers)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"[chemrxiv] search error: {e}", flush=True)
            return []

    items = []
    # The API wraps results differently depending on version; handle both shapes.
    results = []
    if isinstance(data, list):
        results = data
    elif isinstance(data, dict):
        results = (data.get("items") or data.get("results") or data.get("hits") or [])

    for entry in results[:limit]:
        title = (entry.get("title") or "").strip()
        if not title:
            continue
        doi = entry.get("doi", "")
        published = _parse_iso_date(
            entry.get("publishedDate") or entry.get("date") or entry.get("postedDate") or ""
        )
        authors = []
        for a in entry.get("authors", []) or []:
            if isinstance(a, dict):
                nm = " ".join(x for x in [a.get("firstName", ""), a.get("lastName", "")] if x)
                if nm:
                    authors.append(nm)
            elif isinstance(a, str):
                authors.append(a)
        category = entry.get("category", "") or entry.get("subject", "")

        items.append(RawItem(
            source="ChemRxiv",
            title=title,
            abstract=(entry.get("abstract") or "").strip(),
            url=entry.get("url") or (f"https://chemrxiv.org/engage/chemrxiv/article-details/{doi}" if doi else ""),
            ext_id=f"chemrxiv:{doi}" if doi else f"chemrxiv:{title[:60]}",
            authors=authors,
            venue=f"ChemRxiv ({category})" if category else "ChemRxiv",
            doi=doi,
            published_at=published,
        ))
    return items
