"""PubMed via NCBI E-utilities. Free, no key — just needs an email.

Covers all PubMed/MEDLINE journals. Abstracts are virtually always present.
Set PUBMED_JOURNALS below to restrict to specific journals (empty = all).
Uses async httpx instead of Biopython's Entrez to stay in the async pipeline.
"""
import asyncio
import datetime as dt
import os
import re
import httpx
from . import RawItem

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# NCBI requires an email for every request
NCBI_EMAIL = "xieyy@imb.pumc.edu.cn"

# ── Journal filter ──────────────────────────────────────────────
# Set journal names (abbreviated or full).  Will be resolved to ISSN
# for precise PubMed filtering.  Leave empty to search all PubMed.
PUBMED_JOURNALS: list[str] = [
    "Nat Biotechnol", "Nat Commun", "Science", "Nature", "Cell",
    "Nat Chem Biol", "Nat Methods", "Nat Microbiol", "Nat Synth",
    "Nat Protoc", "Nat Rev Genet", "Nat Catal", "Nat Comput Sci",
    "Nat Metab", "Nat Chem Eng", "Nat Mach Intell", "Nat Ecol Evol",
    "Nat Biomed Eng",
    "J Am Chem Soc", "JACS Au", "ACS Synth Biol", "ACS Chem Biol",
    "Biochemistry", "ACS Cent Sci", "J Med Chem", "ACS Catal",
    "Org Lett", "J Org Chem", "Anal Chem", "J Agric Food Chem",
    "J Nat Prod", "Angew Chem Int Ed Engl", "J Antibiot", "J Chem Inf Model",
]

# ── Journal filter by ISSN ─────────────────────────────────────
# Load ISSN mapping from the IF Excel for precise journal filtering.
# Falls back to [ta] (name-based) if Excel is unavailable.
_PUBMED_ISSN_MAP: dict[str, str] = {}  # journal name (lower) -> ISSN
try:
    import openpyxl
    _if_path = os.path.join(os.path.dirname(__file__), "2026IF.xlsx")
    if os.path.isfile(_if_path):
        _wb = openpyxl.load_workbook(_if_path, read_only=True)
        _ws = _wb.active
        for _row in _ws.iter_rows(min_row=2, values_only=True):
            _issn = str(_row[4] or "").strip()
            _eissn = str(_row[5] or "").strip()
            _abbr = str(_row[2] or "").strip().lower()
            _full = str(_row[1] or "").strip().lower()
            if _issn and _abbr:
                _PUBMED_ISSN_MAP[_abbr] = _issn
                _PUBMED_ISSN_MAP[_issn.lower()] = _issn
            if _eissn and _abbr:
                _PUBMED_ISSN_MAP[_eissn.lower()] = _eissn
            if _issn and _full:
                _PUBMED_ISSN_MAP[_full] = _issn
        _wb.close()
        print(f"[pubmed] loaded {len(_PUBMED_ISSN_MAP)} ISSN mappings", flush=True)
except Exception:
    pass

# Fallback: journal name -> ISSN for commonly used journals
_FALLBACK_ISSN: dict[str, str] = {
    "nature": "0028-0836", "nat biotechnol": "1087-0156", "nat chem biol": "1552-4450",
    "nat commun": "2041-1723", "nat methods": "1548-7091", "nat microbiol": "2058-5276",
    "nat synst": "2731-0576", "science": "0036-8075", "cell": "0092-8674",
    "j am chem soc": "0002-7863", "jacs au": "2691-3704",
    "acs synth biol": "2161-5063", "acs chem biol": "1554-8929",
    "biochemistry": "0006-2960", "acs cent sci": "2374-7943",
    "j med chem": "0022-2623", "acs catal": "2155-5435",
    "org lett": "1523-7060", "j org chem": "0022-3263",
    "anal chem": "0003-2700", "j agric food chem": "0021-8561",
    "j nat prod": "0163-3864",
    "angew chem int ed engl": "1433-7851",
    "j antibiot": "0021-8820",
    "j chem inf model": "1549-9596",
}


def _get_issn(name: str) -> str:
    """Resolve a journal name to its ISSN."""
    key = name.strip().lower()
    if key in _PUBMED_ISSN_MAP:
        return _PUBMED_ISSN_MAP[key]
    if key in _FALLBACK_ISSN:
        return _FALLBACK_ISSN[key]
    return ""


# Remove the old _JOURNAL_ABBR stuff since we use ISSN now
_JOURNAL_ABBR: dict[str, str] = {}
_JOURNAL_ABBR_REV: dict[str, str] = {}

_XML_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")

def _clean(s: str) -> str:
    return _WS.sub(" ", _XML_TAG.sub("", s or "")).strip()


async def search(keyword: str, retmax: int = 50) -> list:
    """Search PubMed by keyword.

    If PUBMED_JOURNALS is set, searches each journal individually by ISSN
    (like ACS/Nature via Crossref), so each journal gets its own results.
    Otherwise searches all PubMed at once.
    """
    headers = {"User-Agent": "ScholarPulse/1.0"}
    items: list[RawItem] = []

    # Resolve journal names to ISSNs, sorted by impact factor descending
    from ..impact import get_impact_factor
    raw_issns = dict.fromkeys(
        _get_issn(j) for j in PUBMED_JOURNALS if _get_issn(j))
    # Filter out empty/N/A ISSNs
    raw_issns = {issn for issn in raw_issns if issn and issn != "N/A"}
    issn_if = [(issn, get_impact_factor(issn) or 0) for issn in raw_issns]
    issn_if.sort(key=lambda x: -x[1])
    issns = [issn for issn, _ in issn_if]
    per_journal = max(3, retmax // len(issns)) if issns else retmax

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        if issns:
            # For single-keyword radar refresh: search per-journal for depth.
            # For multi-keyword deep search: use single OR query to avoid 429.
            if " AND " in keyword or len(keyword) > 60:
                # Deep search / complex query — one combined query
                jf = "(" + " OR ".join(f'"{issn}"[issn]' for issn in issns) + ")"
                term = f"{jf} AND ({keyword})"
                items = await _search_and_fetch(c, term, retmax, headers)
            else:
                # Single keyword — search each journal individually
                for i, issn in enumerate(issns):
                    term = f'{issn}[issn] AND ({keyword})'
                    batch = await _search_and_fetch(c, term, per_journal, headers)
                    items.extend(batch)
                    if i < len(issns) - 1:
                        await asyncio.sleep(0.34)
        else:
            items = await _search_and_fetch(c, keyword, retmax, headers)

    return items


async def _search_and_fetch(client, term: str, retmax: int,
                            headers: dict) -> list:
    """ESearch → EFetch pipeline for a single term."""
    # --- ESearch ---
    params = {
        "db": "pubmed",
        "term": term,
        "retmax": str(retmax),
        "retmode": "json",
        "email": NCBI_EMAIL,
    }
    data = None
    for attempt in range(3):
        try:
            r = await client.get(ESEARCH, params=params, headers=headers)
            if r.status_code == 429:
                await asyncio.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            data = r.json()
            break
        except Exception as e:
            if attempt == 2:
                print(f"[pubmed] esearch error: {e}", flush=True)
                return []
            await asyncio.sleep(1)
    if data is None:
        return []

    id_list = data.get("esearchresult", {}).get("idlist", [])
    if not id_list:
        return []

    # --- EFetch ---
    params = {
        "db": "pubmed",
        "id": ",".join(id_list),
        "retmode": "xml",
        "rettype": "abstract",
        "email": NCBI_EMAIL,
    }
    xml_text = ""
    for attempt in range(3):
        try:
            r = await client.get(EFETCH, params=params, headers=headers)
            if r.status_code == 429:
                await asyncio.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            xml_text = r.text
            break
        except Exception as e:
            if attempt == 2:
                print(f"[pubmed] efetch error: {e}", flush=True)
                return []
            await asyncio.sleep(1)

    return _parse_pubmed_xml(xml_text, id_list)


def _parse_pubmed_xml(xml: str, expected_ids: list[str]) -> list:
    """Minimal XML parser for PubMed ArticleSet XML."""
    items = []
    # Split on <PubmedArticle> boundaries
    articles = re.split(r"<\/?PubmedArticle\s*>", xml)
    for block in articles:
        if not block.strip():
            continue
        pmid = _extract_tag(block, "PMID")
        if not pmid or pmid not in expected_ids:
            continue

        title = _extract_tag(block, "ArticleTitle")
        abstract = _extract_abstract(block)
        doi = _extract_doi(block)

        # Date — parse Year/Month/Day from PubDate
        # The FIRST <Year> in PubMed XML is DateCompleted, the SECOND is usually
        # DateRevised, and PubDate's <Year> comes later inside <Journal>.
        # Find the last <Year> in the block — that's the publication year.
        all_years = list(re.finditer(r"<Year[^>]*>(.*?)<\/Year>", block, re.S))
        if all_years:
            last_y = all_years[-1]
            try:
                y = int(_clean(last_y.group(1)))
                # Now find the Month and Day that belong to the same PubDate
                # (the Month/Day after the last Year)
                rest = block[last_y.end():]
                m = 1
                d = 1
                mm = re.search(r"<Month[^>]*>(.*?)<\/Month>", rest, re.S)
                if mm:
                    m_str = _clean(mm.group(1)).lower()[:3]
                    months = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
                              "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
                    m = months.get(m_str, months.get(m_str.zfill(3), 1))
                    try:
                        m = int(m_str)
                    except ValueError:
                        pass
                dd = re.search(r"<Day[^>]*>(.*?)<\/Day>", rest, re.S)
                if dd:
                    try:
                        d = int(_clean(dd.group(1)))
                    except ValueError:
                        pass
                pub_date = dt.datetime(y, m, d)
            except (ValueError, OverflowError):
                pass

        # Fallback: MedlineDate format
        if not pub_date:
            md = re.search(r"<MedlineDate[^>]*>(.*?)<\/MedlineDate>", block, re.S)
            if md:
                ym = re.search(r"(\d{4})", md.group(1))
                if ym:
                    try:
                        pub_date = dt.datetime(int(ym.group(1)), 1, 1)
                    except ValueError:
                        pass

        # Authors
        authors = []
        # Simple author extraction from AuthorList
        for m in re.finditer(r"<Author[^>]*>.*?<\/Author>", block, re.S):
            last = _extract_tag(m.group(0), "LastName")
            fore = _extract_tag(m.group(0), "ForeName")
            if last or fore:
                authors.append(f"{fore or ''} {last or ''}".strip())

        # Journal
        journal = _extract_tag(block, "ISOAbbreviation") or _extract_tag(block, "Title") or "PubMed"
        # Full journal name from raw XML
        jtag = re.search(r"<Journal>.*?<\/Journal>", block, re.S)
        journal_full = _extract_tag(jtag.group(0), "Title") if jtag else ""
        issn = _extract_tag(block, "ISSN")
        # Also try to get eISSN (second ISSN element, usually Electronic type)
        eissn = ""
        all_issn = list(re.finditer(r"<ISSN[^>]*>(.*?)<\/ISSN>", block, re.S))
        if len(all_issn) > 1:
            eissn = _clean(all_issn[1].group(1))

        items.append(RawItem(
            source="PubMed",
            title=title or "(no title)",
            abstract=abstract or "",
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            ext_id=f"pubmed:{pmid}",
            authors=authors,
            venue=journal or "PubMed",
            doi=doi,
            published_at=pub_date,
        ))
        items[-1].issn = issn
        items[-1].eissn = eissn
        items[-1].journal_full = journal_full
    return items


def _extract_tag(xml: str, tag: str) -> str:
    m = re.search(rf"<{tag}[^>]*>(.*?)<\/{tag}>", xml, re.S)
    return _clean(m.group(1)) if m else ""


def _extract_abstract(xml: str) -> str:
    """PubMed stores abstract as one or more <AbstractText> elements."""
    parts = re.findall(r"<AbstractText[^>]*>(.*?)<\/AbstractText>", xml, re.S)
    return " ".join(_clean(p) for p in parts) if parts else ""


def _extract_doi(xml: str) -> str:
    # Check ELocationID and ArticleId lists
    for m in re.finditer(r"<ELocationID[^>]*>(.*?)<\/ELocationID>", xml, re.S):
        val = m.group(1).strip()
        if val.startswith("10."):
            return val
    for m in re.finditer(r"<ArticleId[^>]*>(.*?)<\/ArticleId>", xml, re.S):
        val = m.group(1).strip()
        if val.startswith("10."):
            return val
    return ""
