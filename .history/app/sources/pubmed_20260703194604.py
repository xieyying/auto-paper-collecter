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
NCBI_EMAIL = "xieyy@imb.pumc.edu.cn"

# ── Journal filter ──────────────────────────────────────────────
# Set to a list of journal names to restrict PubMed searches.
# Uses the [ta] (Journal TA / Title Abbreviation) field tag.
# PubMed expects journal TITLE ABBREVIATIONS (e.g. "Nat Biotechnol" not "Nature Biotechnology").
# If a name is not found in the abbreviation map below, it's used as-is.
# Leave empty to search all PubMed.
PUBMED_JOURNALS: list[str] = [
    "Nat Biotechnol",
    "Nat Commun",
    "Science",
    "Nature",
    "Cell",
    "Nat Chem Biol",
    "Nat Methods",
    "Nat Microbiol",
    "Nat Synth",
    "Nat Protoc",
    "Nat Rev Genet",
    "Nat Catal",
    "Nat Comput Sci",
    "Nat Metab",
    "Nat Chem Eng",
    "Nat Mach Intell",
    "Nat Ecol Evol",
    "Nat Biomed Eng",
    "J Am Chem Soc",
    "JACS Au",
    "ACS Synth Biol",
    "ACS Chem Biol",
    "Biochemistry",
    "ACS Cent Sci",
    "J Med Chem",
    "ACS Catal",
    "Org Lett",
    "J Org Chem",
    "Anal Chem",
    "J Agric Food Chem",
    "J Nat Prod",
    "Angew Chem Int Ed Engl",
    "J Antibiot",
    "J Chem Inf Model",
]

# Common full → abbreviated journal name mapping for PubMed [ta] field
_JOURNAL_ABBR: dict[str, str] = {
    # Nature series
    "Nature": "Nature",
    "Nature Biotechnology": "Nat Biotechnol",
    "Nature Chemical Biology": "Nat Chem Biol",
    "Nature Communications": "Nat Commun",
    "Nature Methods": "Nat Methods",
    "Nature Microbiology": "Nat Microbiol",
    "Nature Synthesis": "Nat Synth",
    "Nature Protocols": "Nat Protoc",
    "Nature Reviews Genetics": "Nat Rev Genet",
    "Nature Catalysis": "Nat Catal",
    "Nature Computational Science": "Nat Comput Sci",
    "Nature Metabolism": "Nat Metab",
    "Nature Chemical Engineering": "Nat Chem Eng",
    "Nature Machine Intelligence": "Nat Mach Intell",
    "Nature Ecology & Evolution": "Nat Ecol Evol",
    "Nature Biomedical Engineering": "Nat Biomed Eng",
    # ACS — many use J-prefix abbreviations
    "JACS": "J Am Chem Soc",
    "JACS Au": "JACS Au",
    "ACS Synthetic Biology": "ACS Synth Biol",
    "ACS Chemical Biology": "ACS Chem Biol",
    "Biochemistry": "Biochemistry",
    "ACS Central Science": "ACS Cent Sci",
    "Journal of Medicinal Chemistry": "J Med Chem",
    "ACS Catalysis": "ACS Catal",
    "Organic Letters": "Org Lett",
    "The Journal of Organic Chemistry": "J Org Chem",
    "Analytical Chemistry": "Anal Chem",
    "Journal of Agricultural and Food Chemistry": "J Agric Food Chem",
    "Journal of Natural Products": "J Nat Prod",
    # Other
    "Science": "Science",
    "Cell": "Cell",
    "Angewandte Chemie International Edition": "Angew Chem Int Ed Engl",
    "J Antibiot": "J Antibiot",
    "Journal of Chemical Information and Modeling": "J Chem Inf Model",
}

# Reverse map: full journal name → abbreviated name (for display)
_JOURNAL_ABBR_REV: dict[str, str] = {v.lower(): v for v in _JOURNAL_ABBR.values()}
# Also add full→abbr mapping
for full, abbr in _JOURNAL_ABBR.items():
    _JOURNAL_ABBR_REV[full.lower()] = abbr


def _abbr_journal(name: str) -> str:
    """Return abbreviated journal name if known, else original."""
    return _JOURNAL_ABBR_REV.get(name.strip().lower(), name)


_XML_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _build_journal_filter() -> str:
    """Build a PubMed query fragment like (\"Nature\"[ta] OR \"Nat Biotechnol\"[ta]).

    Uses _JOURNAL_ABBR to map full names to PubMed-compatible abbreviations.
    """
    if not PUBMED_JOURNALS:
        return ""
    abbrs = [_JOURNAL_ABBR.get(j, j) for j in PUBMED_JOURNALS]
    parts = " OR ".join(f'"{a}"[ta]' for a in abbrs)
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
