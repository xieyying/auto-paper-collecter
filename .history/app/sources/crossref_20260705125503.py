"""Crossref REST API. Free, covers IEEE/ACM/journal metadata. Abstracts often present (JATS).

Per-journal search: when journals are configured, each journal is queried
individually via filter=issn:, ensuring every selected journal contributes results.
"""
import asyncio
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


def _get_issn_for_journal(jn: str) -> str:
    """Resolve a journal name to its ISSN using pubmed's mapping."""
    key = jn.strip().lower()
    issn = _pm._PUBMED_ISSN_MAP.get(key, "")
    if issn:
        return issn
    issn = _pm._FALLBACK_ISSN.get(key, "")
    return issn


async def _fetch_journal(client: httpx.AsyncClient, keyword: str,
                         issn: str, rows: int, headers: dict) -> list:
    """Fetch Crossref results for a single journal (by ISSN filter)."""
    params = {
        "query": keyword,
        "filter": f"issn:{issn}",
        "sort": "published",
        "order": "desc",
        "rows": rows,
        "select": "DOI,title,author,abstract,URL,container-title,published,type,ISSN,issn-type",
    }
    try:
        r = await client.get(API, params=params, headers=headers)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[crossref] error for ISSN {issn}: {e}", flush=True)
        return []
    return data.get("message", {}).get("items", [])


def _parse_crossref_item(it: dict) -> RawItem | None:
    """Parse a Crossref API item into a RawItem."""
    title_list = it.get("title") or []
    if not title_list:
        return None
    container = (it.get("container-title") or [""])
    venue = container[0] if container else ""
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
    issn_list = it.get("ISSN") or []
    issn_val = issn_list[0] if issn_list else ""
    eissn_val = ""
    for itype in (it.get("issn-type") or []):
        if itype.get("type") == "electronic":
            eissn_val = itype.get("value", "")

    return RawItem(
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
    )


async def search(keyword: str, rows: int = 15):
    """Search Crossref, one journal at a time.

    When a journal list is active, each journal is queried individually
    via filter=issn: to guarantee coverage.  Otherwise falls back to a
    single unfiltered query.
    """
    headers = {"User-Agent": "ScholarPulse/1.0 (mailto:scholarpulse@example.com)"}

    # Determine which journals to search
    jlist = _pm._ACTIVE_JOURNALS if _pm._ACTIVE_JOURNALS is not None else _pm.PUBMED_JOURNALS
    has_journals = bool(jlist)

    seen_dois: set[str] = set()
    all_items: list[RawItem] = []

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        if has_journals:
            # ── Per-journal iteration ────────────────────────────
            sem = asyncio.Semaphore(3)  # max 3 concurrent

            async def _fetch_one(jn: str) -> list:
                async with sem:
                    issn = _get_issn_for_journal(jn)
                    if not issn:
                        return []
                    raw_items = await _fetch_journal(c, keyword, issn, rows, headers)
                    parsed = []
                    for it in raw_items:
                        item = _parse_crossref_item(it)
                        if item is None:
                            continue
                        if item.doi and item.doi in seen_dois:
                            continue
                        if item.doi:
                            seen_dois.add(item.doi)
                        parsed.append(item)
                    return parsed

            tasks = [_fetch_one(jn) for jn in jlist]
            results = await asyncio.gather(*tasks)
            for chunk in results:
                all_items.extend(chunk)

            # Sort by date descending
            all_items.sort(key=lambda x: x.published_at or dt.datetime.min, reverse=True)
        else:
            # ── Single unfiltered query ──────────────────────────
            params = {
                "query": keyword,
                "sort": "published",
                "order": "desc",
                "rows": rows,
                "select": "DOI,title,author,abstract,URL,container-title,published,type,ISSN,issn-type",
            }
            try:
                r = await c.get(API, params=params, headers=headers)
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                print(f"[crossref] error: {e}", flush=True)
                return []

            for it in data.get("message", {}).get("items", []):
                item = _parse_crossref_item(it)
                if item is not None:
                    all_items.append(item)

    return all_items
