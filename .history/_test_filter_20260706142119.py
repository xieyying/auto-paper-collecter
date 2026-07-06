"""Test deep search text filter."""
import httpx

# Test with "protein language model" + "deep learning"
r = httpx.post("http://localhost:8000/api/deep-search", json={
    "keywords": ["protein language model", "deep learning"],
    "time_range_days": 365,
    "sources": ["PubMed", "Crossref"]
}, timeout=180)
d = r.json()
print("Total:", d.get("total"))
for item in (d.get("results") or [])[:8]:
    ven = (item.get("venue") or "?")[:30]
    title = item["title"][:60]
    kw = item.get("topic", "")[:50]
    print(f"  [{ven}] {title}")
    print(f"    kw: {kw}")
