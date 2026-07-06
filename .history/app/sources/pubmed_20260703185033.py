"""PubMed via NCBI E-utilities. Free, no key — just needs an email.

Covers all PubMed/MEDLINE journals. Abstracts are virtually always present.
Set PUBMED_JOURNALS below to restrict to specific journals (empty = all).
Uses async httpx instead of Biopython's Entrez to stay in the async pipeline.
"""
import datetime as dt
import re
import httpx
from . import RawItem

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# NCBI requires an email for every request
NCBI_EMAIL = "scholarpulse@example.com"

# ── Journal filter ──────────────────────────────────────────────
# Set to a list of journal names (case-insensitive) to restrict PubMed
# searches to those journals only.  Leave empty to search all PubMed.
# Uses the [ta] (Journal TA / Title Abbreviation) field tag.
# Examples: "Nature", "Science", "Nat Biotechnol", "Proc Natl Acad Sci U S A"
PUBMED_JOURNALS: list[str] = [
    "Nature",
    "Science",
    "Cell",
    "JACS",
    "JACS Au",
    "ACS Synthetic Biology",
    "ACS Chemical Biology",
    "Biochemistry",
    "ACS Central Science",
    "Journal of Medicinal Chemistry",
    "ACS Catalysis",
    "Organic Letters",
    "The Journal of Organic Chemistry",
    "Analytical Chemistry",
    "Journal of Agricultural and Food Chemistry",
    "Journal of Natural Products",
    "Nature Biotechnology",
    "Nature Chemical Biology",
    "Nature Communications",
    "Nature Methods",
    "Nature Microbiology",
    "Nature Synthesis",
    "Nature Protocols",
    "Nature Reviews Genetics",
    "Nature Catalysis",
    "Nature Computational Science",
    "Nature Metabolism",
    "Nature Chemical Engineering",
    "Nature Machine Intelligence",
    "Nature Ecology & Evolution",
    "Nature Biomedical Engineering",
    "Angewandte Chemie International Edition",
    "J Antibiot",
]

_XML_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _build_journal_filter() -> str:
    """Build a PubMed query fragment like (\"Nature\"[ta] OR \"Science\"[ta])."""
    if not PUBMED_JOURNALS:
        return ""
    parts = " OR ".join(f'"{j}"[ta]' for j in PUBMED_JOURNALS)
    return f"({parts})"


def _clean(s: str) -> str:
    return _WS.sub(" ", _XML_TAG.sub("", s or "")).strip()


async def search(keyword: str, retmax: int = 15) -> list:
    """Search PubMed by keyword across ALL fields (title, abstract, MeSH, keywords...).

    Uses PubMed native boolean syntax:
      ([journal filter]) AND (keyword)
    """
    headers = {"User-Agent": "ScholarPulse/1.0"}

    # Build boolean query: [journal filter] AND (keyword)  — All Fields by default
    jf = _build_journal_filter()
    term = f"{jf} AND ({keyword})" if jf else keyword

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        # --- Step 1: ESearch — get PMIDs ---
        params = {
            "db": "pubmed",
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
            print(f"[pubmed] esearch error: {e}", flush=True)
            return []

        id_list = data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return []

        # --- Step 2: EFetch — get details in XML ---
        params = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "xml",
            "rettype": "abstract",
            "email": NCBI_EMAIL,
        }
        try:
            r = await c.get(EFETCH, params=params, headers=headers)
            r.raise_for_status()
            xml_text = r.text
        except Exception as e:
            print(f"[pubmed] efetch error: {e}", flush=True)
            return []

    # --- Step 3: Parse the XML ---
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

        # Date
        pub_date = None
        year = _extract_tag(block, "PubDate")
        # Try ISO format from PubMed XML
        try:
            # Sometimes in <PubMedDate>
            iso = _extract_tag(xml, "PubMedDate")
        except Exception:
            iso = ""
        # Try MedlineDate format "2024 Jan-Dec" or just "2024"
        if year:
            y_match = re.search(r"(\d{4})", year)
            if y_match:
                try:
                    pub_date = dt.datetime(int(y_match.group(1)), 1, 1)
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
        journal = _extract_tag(block, "Journal") or _extract_tag(block, "Title")

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
