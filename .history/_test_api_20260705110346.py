"""Quick test for journal-filtered deep search."""
import httpx

r = httpx.post("http://localhost:8000/api/deep-search", json={
    "keywords": ["ESM2"],
    "time_range_days": 365,
    "sources": ["PubMed", "PMC", "Crossref"]
}, timeout=180)
print("Status:", r.status_code)
data = r.json()
print("Total:", data.get("total"))
for item in (data.get("results") or [])[:5]:
    print(f"  [{item['source']}] IF={item.get('if','?')} {item['title'][:70]}")
