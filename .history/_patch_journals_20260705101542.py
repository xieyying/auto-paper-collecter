"""Add set_journals call to fetch.py and deep_search.py"""

# fetch.py
with open("app/pipeline/fetch.py", "r", encoding="utf-8") as f:
    c = f.read()

# Add import
c = c.replace(
    "from ..sources import (arxiv, crossref, semanticscholar, rss_news, github,\n                       huggingface, paperswithcode, nature, acs, biorxiv,\n                       chemrxiv, pubmed, pmc)",
    "from ..sources import (arxiv, crossref, semanticscholar, rss_news, github,\n                       huggingface, paperswithcode, nature, acs, biorxiv,\n                       chemrxiv, pubmed, pmc)\nfrom ..sources.pubmed import set_journals as set_pubmed_journals"
)

# Add set_journals call before fetching starts, after getting settings
old = """            kws = keywords[:3]
            raw = []"""
new = """            # Configure PubMed journal filter from settings
            pm_journals = json.loads(s.pubmed_journals or "null")
            set_pubmed_journals(pm_journals if isinstance(pm_journals, list) else None)
            kws = keywords[:3]
            raw = []"""
c = c.replace(old, new)

with open("app/pipeline/fetch.py", "w", encoding="utf-8") as f:
    f.write(c)
print("fetch.py OK")

# deep_search.py
with open("app/pipeline/deep_search.py", "r", encoding="utf-8") as f:
    c = f.read()

c = c.replace(
    "from ..sources import (arxiv, crossref, semanticscholar, github,\n                       huggingface, paperswithcode, nature, acs, pubmed, pmc)",
    "from ..sources import (arxiv, crossref, semanticscholar, github,\n                       huggingface, paperswithcode, nature, acs, pubmed, pmc)\nfrom ..sources.pubmed import set_journals as set_pubmed_journals"
)

c = c.replace(
    '    # 5. Summarise + serialise',
    '    # Configure PubMed journal filter\n'
    '    pm_journals = getattr(db, "_pubmed_journals", None)\n'
    '    set_pubmed_journals(pm_journals)\n\n'
    '    # 5. Summarise + serialise'
)

with open("app/pipeline/deep_search.py", "w", encoding="utf-8") as f:
    f.write(c)
print("deep_search.py OK")

# Verify
import ast
for path in ["app/pipeline/fetch.py", "app/pipeline/deep_search.py"]:
    ast.parse(open(path, encoding="utf-8").read())
    print(f"  {path} syntax OK")
