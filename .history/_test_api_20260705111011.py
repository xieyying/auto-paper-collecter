"""Test with journal filtering active."""
import httpx

# Now deep search - should only return results from Nature/Science/Cell
r = httpx.post("http://localhost:8000/api/deep-search", json={
    "keywords": ["ESM2"],
    "time_range_days": 365,
    "sources": ["PubMed", "PMC", "Crossref"]
}, timeout=180)
print("Status:", r.status_code)
data = r.json()
print("Total:", data.get("total"))
for item in (data.get("results") or [])[:15]:
    src = item['source']
    ven = (item.get('venue') or '')[:35]
    iff = item.get('if', '?')
    title = item['title'][:60]
    print(f"  [{src}] {ven:35s} IF={iff}  {title}")
