"""GitHub repository search — real-time, topic-relevant repos (paper code,
awesome-lists, daily-arXiv mirrors). Free; a token raises the rate limit.
The relevance filter downstream drops the inevitable noise (star-list repos)."""
import os
import datetime as dt
import httpx
from . import RawItem
from ..config import settings

API = "https://api.github.com/search/repositories"


def _token():
    return settings.GITHUB_TOKEN or os.environ.get("GITHUB_TOKEN", "")


async def search(keyword: str, limit: int = 12):
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "ScholarPulse/1.0"}
    tok = _token()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    # name,description only (README matches are too loose and pull in noise like
    # personal star-lists). Still sorted by most-recently-updated for real-time.
    params = {"q": f"{keyword} in:name,description",
              "sort": "updated", "order": "desc", "per_page": limit}
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        r = await c.get(API, params=params, headers=headers)
        if r.status_code in (403, 422, 429):   # rate-limited / bad query -> skip
            return []
        r.raise_for_status()
        data = r.json()

    items = []
    for it in data.get("items", []):
        pushed = it.get("pushed_at") or it.get("updated_at")
        published = None
        if pushed:
            try:
                published = dt.datetime.strptime(pushed, "%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                pass
        owner = (it.get("owner") or {}).get("login", "")
        stars = it.get("stargazers_count", 0)
        items.append(RawItem(
            source="GitHub",
            title=it.get("full_name") or it.get("name", ""),
            abstract=it.get("description") or "",
            url=it.get("html_url", ""),
            ext_id=f"gh:{it.get('id')}",
            authors=[owner] if owner else [],
            venue=f"★{stars}",
            published_at=published,
        ))
    return items
