"""ACS journals via Crossref API with ISSN filtering.

Covers: JACS, ACS Synthetic Biology, ACS Chemical Biology, Biochemistry,
ACS Central Science, Nano Letters (relevant to synbio).
"""
import datetime as dt
import re
import httpx
from . import RawItem

API = "https://api.crossref.org/works"
_TAG = re.compile(r"<[^>]+>")

ACS_ISSNS = [
    "0002-7863",  # JACS
    "2161-5063",  # ACS Synthetic Biology
    "1554-8929",  # ACS Chemical Biology
    "0006-2960",  # Biochemistry
    "2374-7943",  # ACS Central Science
    "1530-6984",  # Nano Letters
]


def _clean_abstract(a: str) -> str:
    if not a:
        return ""
    return " ".join(_TAG.sub(" ", a).split())


async def search(keyword: str, rows: int = 15):
    items = []
    headers = {"User-Agent": "ScholarPulse/1.0 (mailto:scholarpulse@example.com)"}
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        for issn in ACS_ISSNS:
            params = {
                "query": keyword,
                "filter": f"issn:{issn},type:journal-article",
                "sort": "published",
                "order": "desc",
                "rows": max(3, rows // len(ACS_ISSNS)),
                "select": "DOI,title,author,abstract,URL,container-title,published,type",
            }
            try:
                r = await c.get(API, params=params, headers=headers)
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                print(f"[acs] error for issn={issn}: {e}", flush=True)
                continue

            for it in data.get("message", {}).get("items", []):
                title_list = it.get("title") or []
                if not title_list:
                    continue
                container = (it.get("container-title") or [""])
                venue = container[0] if container else ""
                doi = it.get("DOI", "")
                published = None
                parts = (it.get("published", {}) or {}).get("date-parts", [[None]])
                if parts and parts[0] and parts[0][0]:
                    y = parts[0][0]
                    m = parts[0][1] if len(parts[0]) > 1 else 1
                    d = parts[0][2] if len(parts[0]) > 2 else 1
                    try:
                        published = dt.datetime(y, m, d)
                    except ValueError:
                        published = dt.datetime(y, 1, 1)
                authors = []
                for a in it.get("author", []) or []:
                    nm = " ".join(x for x in [a.get("given", ""), a.get("family", "")] if x)
                    if nm:
                        authors.append(nm)
                items.append(RawItem(
                    source="ACS",
                    title=" ".join(title_list[0].split()),
                    abstract=_clean_abstract(it.get("abstract", "")),
                    url=it.get("URL", "https://doi.org/" + doi if doi else ""),
                    ext_id=f"doi:{doi}" if doi else f"acs:{title_list[0][:60]}",
                    authors=authors,
                    venue=venue,
                    doi=doi,
                    published_at=published,
                ))

    seen = {}
    uniq = []
    for it in items:
        if it.ext_id and it.ext_id not in seen:
            seen[it.ext_id] = True
            uniq.append(it)
    return uniq
