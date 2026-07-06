"""Register PMC source across all files"""
import ast, re

# 1) fetch.py
with open("app/pipeline/fetch.py", "r", encoding="utf-8") as f:
    c = f.read()
c = c.replace(
    "from ..sources import (arxiv, crossref, semanticscholar, rss_news, github,\n                       huggingface, paperswithcode, nature, acs, biorxiv,\n                       chemrxiv, pubmed)",
    "from ..sources import (arxiv, crossref, semanticscholar, rss_news, github,\n                       huggingface, paperswithcode, nature, acs, biorxiv,\n                       chemrxiv, pubmed, pmc)"
)
c = c.replace(
    '"PubMed": pubmed.search,',
    '"PubMed": pubmed.search,\n    "PMC": pmc.search,'
)
c = c.replace(
    '"PubMed": True',
    '"PubMed": True, "PMC": True'
)
with open("app/pipeline/fetch.py", "w", encoding="utf-8") as f:
    f.write(c)
print("fetch.py OK")

# 2) deep_search.py
with open("app/pipeline/deep_search.py", "r", encoding="utf-8") as f:
    c = f.read()
c = c.replace(
    "from ..sources import (arxiv, crossref, semanticscholar, github,\n                       huggingface, paperswithcode, nature, acs, pubmed)",
    "from ..sources import (arxiv, crossref, semanticscholar, github,\n                       huggingface, paperswithcode, nature, acs, pubmed, pmc)"
)
c = c.replace(
    '"PubMed": pubmed.search,',
    '"PubMed": pubmed.search,\n    "PMC": pmc.search,'
)
with open("app/pipeline/deep_search.py", "w", encoding="utf-8") as f:
    f.write(c)
print("deep_search.py OK")

# 3) api.py
with open("app/api.py", "r", encoding="utf-8") as f:
    c = f.read()
c = c.replace(
    '"PubMed":         {"color": "#2E8B57", "bg": "#E8F5EE"},',
    '"PubMed":         {"color": "#2E8B57", "bg": "#E8F5EE"},'
    '\n    "PMC":            {"color": "#E65100", "bg": "#FDE8D8"},'
)
c = c.replace(
    '"PubMed": "PubMed/MEDLINE 生物医学",',
    '"PubMed": "PubMed/MEDLINE 生物医学",\n                          "PMC": "PubMed Central 全文库",'
)
c = c.replace(
    '"PubMed"]]',
    '"PubMed", "PMC"]]'
)
with open("app/api.py", "w", encoding="utf-8") as f:
    f.write(c)
print("api.py OK")

# 4) index.html
with open("static/index.html", "r", encoding="utf-8") as f:
    c = f.read()
c = c.replace(
    "'PubMed': { color:'#2E8B57', bg:'#E8F5EE', desc:'PubMed / MEDLINE 生物医学文献' },",
    "'PubMed': { color:'#2E8B57', bg:'#E8F5EE', desc:'PubMed / MEDLINE 生物医学文献' },\n      'PMC': { color:'#E65100', bg:'#FDE8D8', desc:'PubMed Central 全文库（含正文检索）' },"
)
c = c.replace(
    "'PubMed': true, 'bioRxiv': true, 'ChemRxiv': true }",
    "'PubMed': true, 'bioRxiv': true, 'ChemRxiv': true, 'PMC': true }"
)
c = c.replace(
    "'ChemRxiv':['#8B5CF6','#F0EAFE'] };",
    "'ChemRxiv':['#8B5CF6','#F0EAFE'], 'PMC':['#E65100','#FDE8D8'] };"
)
with open("static/index.html", "w", encoding="utf-8") as f:
    f.write(c)
print("index.html OK")

# Verify all
for path in ["app/pipeline/fetch.py", "app/pipeline/deep_search.py", "app/api.py"]:
    with open(path, "r", encoding="utf-8") as f:
        ast.parse(f.read())
    print(f"  {path} syntax OK")
print("All done!")
