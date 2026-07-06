with open("app/pipeline/deep_search.py", "r", encoding="utf-8") as f:
    c = f.read()
c = c.replace(
    'from ..sources import (arxiv, crossref, semanticscholar, github,\n                       huggingface, paperswithcode, nature, acs)',
    'from ..sources import (arxiv, crossref, semanticscholar, github,\n                       huggingface, paperswithcode, nature, acs, pubmed)'
)
c = c.replace(
    '"ACS": acs.search,\n}',
    '"ACS": acs.search,\n    "PubMed": pubmed.search,\n}'
)
with open("app/pipeline/deep_search.py", "w", encoding="utf-8") as f:
    f.write(c)
print("OK")
