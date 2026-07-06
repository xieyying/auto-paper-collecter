"""PubMed Central (PMC) via NCBI E-utilities — searches FULL TEXT.

Unlike PubMed (which only searches titles/abstracts/metadata),
PMC searches the complete open-access article body.  Use this
when you want to find papers where your keyword appears anywhere
in the text, not just the abstract.
"""
import asyncio
import datetime as dt
import re
import httpx
from . import RawItem

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

NCBI_EMAIL = "scholarpulse@example.com"

_XML_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _clean(s: str) -> str:
    return _WS.sub(" ", _XML_TAG.sub("", s or "")).strip()


async def search(keyword: str, retmax: int = 15) -> list:
    """Search PMC full text by keyword. Covers the entire open-access article body."""
    headers = {"User-Agent": "ScholarPulse/1.0"}
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        # --- Step 1: ESearch in PMC ---
        # The `term` searches ALL fields including full-text body by default.
        # Use all: prefix to be explicit: all:"keyword"
        term = f'all:"{keyword}"'
        params = {
            "db": "pmc",
            "term": term,
            "retmax": str(retmax),
            "retmode": "json",
            "email": NCBI_EMAIL,
        }
        try:
            r = await c.get(ESEARCH, params=params, headers=headers)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"[pmc] esearch error: {e}", flush=True)
            return []

        id_list = data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return []

        # --- Step 2: EFetch — get metadata (not full XML, just summary) ---
        params = {
            "db": "pmc",
            "id": ",".join(id_list),
            "retmode": "xml",
            "rettype": "abstract",  # returns article metadata with abstract
            "email": NCBI_EMAIL,
        }
        xml_text = ""
        for attempt in range(3):
            try:
                r = await c.get(EFETCH, params=params, headers=headers)
                if r.status_code == 429:
                    await asyncio.sleep(2 ** attempt)
                    continue
                r.raise_for_status()
                xml_text = r.text
                break
            except Exception as e:
                if attempt == 2:
                    print(f"[pmc] efetch error: {e}", flush=True)
                    return []
                await asyncio.sleep(1)

    # --- Step 3: Parse ---
    return _parse_pmc_xml(xml_text, id_list)


def _parse_pmc_xml(xml: str, expected_ids: list[str]) -> list:
    """Parse NLM JATS XML from PMC efetch."""
    items = []
    # Split on <article ...> boundaries (PMC returns NLM JATS XML)
    articles = re.split(r"<article\s[^>]*>", xml, re.S)
    for i, block in enumerate(articles[1:], 1):  # skip everything before first article
        if not block.strip():
            continue
        # Get PMC ID from article-meta
        pmcid = _ptag(block, 'article-id', 'pub-id-type', 'pmcid')
        pmid = _ptag(block, 'article-id', 'pub-id-type', 'pmid')
        pid = (pmcid or pmid or "").strip()
        if not pid or pid not in expected_ids:
            continue

        # Title
        title = _ctag(block, "article-title") or ""

        # Abstract (JATS: <abstract><p>...</p></abstract> or <abstract><p>...</p>...)
        abstract = ""
        abs_m = re.search(r"<abstract[^>]*>(.*?)</abstract>", block, re.S)
        if abs_m:
            paras = re.findall(r"<p[^>]*>(.*?)</p>", abs_m.group(1), re.S)
            abstract = " ".join(_clean(p) for p in paras)

        # DOI
        doi = _ptag(block, 'article-id', 'pub-id-type', 'doi')

        # Date from <pub-date>
        pub_date = None
        pub_block = _ctag(block, "pub-date")
        if pub_block:
            y_m = re.search(r"<year[^>]*>(.*?)</year>", pub_block, re.S)
            if y_m:
                try:
                    y = int(_clean(y_m.group(1)))
                    m, d = 1, 1
                    mm = re.search(r"<month[^>]*>(.*?)</month>", pub_block, re.S)
                    if mm:
                        m_str = _clean(mm.group(1)).lower()[:3]
                        months = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
                                  "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
                        m = months.get(m_str, int(m_str) if m_str.isdigit() else 1)
                    dd = re.search(r"<day[^>]*>(.*?)</day>", pub_block, re.S)
                    if dd:
                        d = int(_clean(dd.group(1)))
                    pub_date = dt.datetime(y, m, d)
                except (ValueError, OverflowError):
                    pass

        # Authors
        authors = []
        contribs = re.findall(r"<contrib[^>]*contrib-type=\"author\"[^>]*>(.*?)</contrib>", block, re.S)
        for cb in contribs:
            sn = _ctag(cb, "surname")
            gn = _ctag(cb, "given-names")
            if sn or gn:
                authors.append(f"{gn or ''} {sn or ''}".strip())

        # Journal
        journal = _ctag(block, "journal-title") or "PMC"

        pmid_clean = re.sub(r"\D", "", pmid or "")
        pmcid_clean = re.sub(r"\D", "", pmcid or "")
        ext_id = f"pmc:{pmcid_clean}" if pmcid_clean else f"pubmed:{pmid_clean}"
        url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid_clean}/" if pmcid_clean else ""

        items.append(RawItem(
            source="PMC",
            title=title or "(no title)",
            abstract=abstract or "",
            url=url,
            ext_id=ext_id,
            authors=authors,
            venue=journal or "PMC",
            doi=doi or "",
            published_at=pub_date,
        ))
    return items


def _ctag(xml: str, tag: str) -> str:
    """Extract clean text from a tag."""
    m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", xml, re.S)
    return _clean(m.group(1)) if m else ""


def _ptag(xml: str, tag: str, attr: str, val: str) -> str:
    """Extract text from a tag with a specific attribute value."""
    m = re.search(rf'<{tag}[^>]*{attr}="{val}"[^>]*>(.*?)</{tag}>', xml, re.S)
    if not m:
        m = re.search(rf'<{tag}[^>]*{attr}=\'{val}\'[^>]*>(.*?)</{tag}>', xml, re.S)
    return _clean(m.group(1)) if m else ""
