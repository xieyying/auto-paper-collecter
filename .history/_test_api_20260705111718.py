"""Test journal filtering with all journals."""
import httpx

# Reset to no journal filter (all journals)
r = httpx.put("http://localhost:8000/api/settings", json={
    "keywords": ["ESM2"],
    "domain": "",
    "sources": {"PubMed": True, "Crossref": True, "PMC": True},
    "channels": {"email": False, "browser": True},
    "email": "",
    "backfill_n": 5,
    "pubmed_journals": []
}, timeout=10)
print("Save:", r.status_code)

# Test deep search
r = httpx.post("http://localhost:8000/api/deep-search", json={
    "keywords": ["ESM2"],
    "time_range_days": 365,
    "sources": ["PubMed", "Crossref"]
}, timeout=180)
d = r.json()
print("Total:", d.get("total"))
for item in (d.get("results") or [])[:8]:
    src = item["source"]
    ven = (item.get("venue") or "")[:35]
    iff = item.get("if", "?")
    title = item["title"][:60]
    print(f"  [{src}] {ven:35s} IF={iff}  {title}")
