"""Crossref REST API. Free, covers IEEE/ACM/journal metadata. Abstracts often present (JATS)."""
import datetime as dt
import re
import httpx
from . import RawItem
from . import pubmed as _pm

API = "https://api.crossref.org/works"
_TAG = re.compile(r"<[^>]+>")


def _clean_abstract(a: str) -> str:
    if not a:
        return ""
    return " ".join(_TAG.sub(" ", a).split())


def _journal_matches(venue: str, issn: str) -> bool:
    """Check if a Crossref result matches the active journal list."""
    jlist = _pm._ACTIVE_JOURNALS if _pm._ACTIVE_JOURNALS is not None else _pm.PUBMED_JOURNALS
    if not jlist:
        return True  # empty list = all journals
    # Check ISSN match
    if issn:
        for jn in jlist:
            j_issn = _pm._PUBMED_ISSN_MAP.get(jn.lower())
            if j_issn and issn.strip().lower() == j_issn.lower():
                return True
    # Check venue name match (case-insensitive substring)
    vl = venue.lower().strip()
    for jn in jlist:
        if jn.lower() in vl or vl in jn.lower():
            return True
    return False


async def search(keyword: str, rows: int = 15):
    params = {
        "query": keyword,
        "sort": "published",
        "order": "desc",
        "rows": rows,
        "select": "DOI,title,author,abstract,URL,container-title,published,type,ISSN,issn-type",
    }
    headers = {"User-Agent": "ScholarPulse/1.0 (mailto:scholarpulse@example.com)"}
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        r = await c.get(API, params=params, headers=headers)
        r.raise_for_status()
        data = r.json()

    items = []
    for it in data.get("message", {}).get("items", []):
        title_list = it.get("title") or []
        if not title_list:
            continue
        container = (it.get("container-title") or [""])
        venue = container[0] if container else ""
        # crude source attribution from venue / DOI prefix
        doi = it.get("DOI", "")
        src = "ACM" if doi.startswith("10.1145") else ("IEEE" if doi.startswith("10.1109") else "Crossref")
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
        # Extract ISSN for journal filtering
        issn_list = it.get("ISSN") or []
        issn_val = issn_list[0] if issn_list else ""
        eissn_val = ""
        for itype in (it.get("issn-type") or []):
            if itype.get("type") == "electronic":
                eissn_val = itype.get("value", "")

        # Journal filter: skip if venue doesn't match active journals
        if not _journal_matches(venue, issn_val or eissn_val):
            continue

        items.append(RawItem(
            source=src,
            title=" ".join(title_list[0].split()),
            abstract=_clean_abstract(it.get("abstract", "")),
            url=it.get("URL", "https://doi.org/" + doi if doi else ""),
            ext_id=f"doi:{doi}" if doi else f"crossref:{title_list[0][:60]}",
            authors=authors,
            venue=venue,
            doi=doi,
            published_at=published,
            issn=issn_val or eissn_val,
        ))
    return items
