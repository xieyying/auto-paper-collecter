"""Debug why FtsZ paper matched 'protein language model' in Crossref."""
import httpx

doi = "10.1038/s41564-026-01111-3"  # guessed DOI, let me search first

# Search for the paper
r = httpx.get("https://api.crossref.org/works", params={
    "query": "Bacterial cell division protein FtsZ complexes with a phage protein to activate bacterial immunity",
    "rows": 3,
    "select": "DOI,title,container-title,author,abstract",
}, timeout=30, headers={"User-Agent": "test/1.0"})
d = r.json()
for it in d.get("message", {}).get("items", []):
    doi = it.get("DOI", "")
    title = (it.get("title") or [""])[0][:80]
    journal = (it.get("container-title") or [""])[0]
    abstract = it.get("abstract", "")[:200] if it.get("abstract") else "(no abstract)"
    print(f"DOI: {doi}")
    print(f"Journal: {journal}")
    print(f"Title: {title}")
    print(f"Abstract: {abstract}")
    print()

# Now check what Crossref returns for 'protein language model' filtered to Nature Microbiology
r2 = httpx.get("https://api.crossref.org/works", params={
    "query": "protein language model",
    "filter": "issn:2058-5276",
    "rows": 5,
    "select": "DOI,title,abstract",
}, timeout=30, headers={"User-Agent": "test/1.0"})
d2 = r2.json()
print(f"\n=== 'protein language model' in Nature Microbiology (ISSN 2058-5276) ===")
print(f"Total results: {d2.get('message',{}).get('total-results','?')}")
for it in d2.get("message", {}).get("items", [])[:5]:
    title = (it.get("title") or [""])[0][:80]
    abstract = (it.get("abstract") or "")[:150]
    print(f"  {title}")
    if abstract:
        print(f"    abs: {abstract}")
