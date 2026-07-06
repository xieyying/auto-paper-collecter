"""Test with journal filtering active."""
import httpx

# First set some journals via settings
r = httpx.put("http://localhost:8000/api/settings", json={
    "keywords": ["ESM2"],
    "domain": "",
    "sources": {"PubMed": True, "Crossref": True, "PMC": True},
    "channels": {"email": False, "browser": True},
    "email": "",
    "backfill_n": 5,
    "pubmed_journals": ["Nature", "Science", "Cell"]
}, timeout=10)
print("Save settings:", r.status_code, r.text[:100])

# Now deep search - should only return results from Nature/Science/Cell
r = httpx.post("http://localhost:8000/api/deep-search", json={
    "keywords": ["ESM2"],
    "time_range_days": 365,
    "sources": ["PubMed", "PMC", "Crossref"]
}, timeout=180)
print("Status:", r.status_code)
data = r.json()
print("Total:", data.get("total"))
for item in (data.get("results") or [])[:10]:
    print(f"  [{item['source']}] IF={item.get('if','?')} | {item.get('venue','')[:40]} | {item['title'][:60]}")
