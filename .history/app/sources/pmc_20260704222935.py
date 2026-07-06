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

# ── Journal filter (same as PubMed) ────────────────────────────
PMC_JOURNALS: list[str] = []

_JOURNAL_ABBR: dict[str, str] = {}

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
    """Minimal parser for PMC efetch XML."""
    items = []
    articles = re.split(r"<\/?PubmedArticle\s*>", xml)
    for block in articles:
        if not block.strip():
            continue
        pmid = _extract_tag(block, "PMID")
        pmcid_match = re.search(r'<ArticleId[^>]*IdType="pmc"[^>]*>(PMC\d+)</ArticleId>', block)
        pmcid = pmcid_match.group(1) if pmcid_match else ""
        if not pmid or pmid not in expected_ids:
            # Also check by ArticleId
            if pmcid and pmcid.replace("PMC", "") in expected_ids:
                pass
            elif not pmcid:
                continue

        title = _extract_tag(block, "ArticleTitle")
        abstract = _extract_abstract(block)
        doi = _extract_doi(block)

        # Date
        pub_date = None
        all_years = list(re.finditer(r"<Year[^>]*>(.*?)</Year>", block, re.S))
        if all_years:
            last_y = all_years[-1]
            try:
                y = int(_clean(last_y.group(1)))
                rest = block[last_y.end():]
                m, d = 1, 1
                mm = re.search(r"<Month[^>]*>(.*?)</Month>", rest, re.S)
                if mm:
                    m_str = _clean(mm.group(1)).lower()[:3]
                    months = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
                              "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
                    m = months.get(m_str, 1)
                    try:
                        m = int(m_str)
                    except ValueError:
                        pass
                dd = re.search(r"<Day[^>]*>(.*?)</Day>", rest, re.S)
                if dd:
                    d = int(_clean(dd.group(1)))
                pub_date = dt.datetime(y, m, d)
            except (ValueError, OverflowError):
                ym = re.search(r"(\d{4})", block)
                if ym:
                    pub_date = dt.datetime(int(ym.group(1)), 1, 1)

        # Authors
        authors = []
        for m in re.finditer(r"<Author[^>]*>.*?</Author>", block, re.S):
            last = _extract_tag(m.group(0), "LastName")
            fore = _extract_tag(m.group(0), "ForeName")
            if last or fore:
                authors.append(f"{fore or ''} {last or ''}".strip())

        journal = _extract_tag(block, "Journal") or _extract_tag(block, "Title") or "PMC"
        ext_id = f"pmc:{pmcid.replace('PMC','')}" if pmcid else f"pubmed:{pmid}"

        items.append(RawItem(
            source="PMC",
            title=title or "(no title)",
            abstract=abstract or "",
            url=f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/" if pmcid else f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            ext_id=ext_id,
            authors=authors,
            venue=journal,
            doi=doi,
            published_at=pub_date,
        ))
    return items


def _extract_tag(xml: str, tag: str) -> str:
    m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", xml, re.S)
    return _clean(m.group(1)) if m else ""


def _extract_abstract(xml: str) -> str:
    parts = re.findall(r"<AbstractText[^>]*>(.*?)</AbstractText>", xml, re.S)
    return " ".join(_clean(p) for p in parts) if parts else ""


def _extract_doi(xml: str) -> str:
    for m in re.finditer(r"<ELocationID[^>]*>(.*?)</ELocationID>", xml, re.S):
        val = m.group(1).strip()
        if val.startswith("10."):
            return val
    for m in re.finditer(r"<ArticleId[^>]*>(.*?)</ArticleId>", xml, re.S):
        val = m.group(1).strip()
        if val.startswith("10."):
            return val
    return ""
