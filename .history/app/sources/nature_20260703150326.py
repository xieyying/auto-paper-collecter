"""Nature family journals via Crossref API with ISSN filtering.

Covers: Nature, Nature Biotechnology, Nature Chemical Biology,
Nature Communications, Nature Methods, Nature Microbiology, Nature Synthesis.
"""
import datetime as dt
import re
import httpx
from . import RawItem

API = "https://api.crossref.org/works"
_TAG = re.compile(r"<[^>]+>")

# Key Nature-family ISSNs
NATURE_ISSNS = [
    "0028-0836",  # Nature
    "1087-0156",  # Nature Biotechnology
    "1552-4450",  # Nature Chemical Biology
    "2041-1723",  # Nature Communications
    "1548-7091",  # Nature Methods
    "2058-5276",  # Nature Microbiology
    "2731-0576",  # Nature Synthesis (2022+)
    "1754-2189",  # Nature Protocols
    "1471-0072",  # Nature Reviews
    "1471-0056",  # Nature Reviews Genetics
    "2397-7532",  # Nature Catalysis
    "2397-334X",  # Nature Computational Science
    "2522-5812",  # Nature Metabolism
    "2520-1158",  # Nature Chemical Engineering
    "2397-334X",  # Nature Computational Science
    "2397-334X",  # Nature Machine Intelligence
    "2397-334X",  # Nature Ecology & Evolution
    "2397-334X",  # Nature Biomedical Engineering  
]

ACS_ISSNS = [
    "0002-7863",  # JACS
    "2161-5063",  # ACS Synthetic Biology
    "1554-8929",  # ACS Chemical Biology
    "0006-2960",  # Biochemistry
    "2374-7943",  # ACS Central Science
    "0022-2623",  # Journal of Medicinal Chemistry
    "2155-5435",  # ACS Catalysis
    "1523-7060",  # Organic Letters
    "0022-3263",  # The Journal of Organic Chemistry
    "0003-2700",  # Analytical Chemistry
    "0021-8561",  # Journal of Agricultural and Food Chemistry
]


def _clean_abstract(a: str) -> str:
    if not a:
        return ""
    return " ".join(_TAG.sub(" ", a).split())


async def search(keyword: str, rows: int = 15):
    items = []
    headers = {"User-Agent": "ScholarPulse/1.0 (mailto:scholarpulse@example.com)"}
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        # Search per ISSN to get even coverage across journals
        for issn in NATURE_ISSNS:
            params = {
                "query": keyword,
                "filter": f"issn:{issn},type:journal-article",
                "sort": "published",
                "order": "desc",
                "rows": max(3, rows // len(NATURE_ISSNS)),
                "select": "DOI,title,author,abstract,URL,container-title,published,type",
            }
            try:
                r = await c.get(API, params=params, headers=headers)
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                print(f"[nature] error for issn={issn}: {e}", flush=True)
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
                    source="Nature",
                    title=" ".join(title_list[0].split()),
                    abstract=_clean_abstract(it.get("abstract", "")),
                    url=it.get("URL", "https://doi.org/" + doi if doi else ""),
                    ext_id=f"doi:{doi}" if doi else f"nature:{title_list[0][:60]}",
                    authors=authors,
                    venue=venue,
                    doi=doi,
                    published_at=published,
                ))

    # Deduplicate within this source
    seen = {}
    uniq = []
    for it in items:
        if it.ext_id and it.ext_id not in seen:
            seen[it.ext_id] = True
            uniq.append(it)
    return uniq
