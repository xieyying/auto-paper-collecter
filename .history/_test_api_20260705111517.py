"""Test journal filtering."""
import httpx

# Test 1: PubMed only with Nature/Science/Cell filter
print("=== Test 1: PubMed only ===")
r = httpx.post("http://localhost:8000/api/deep-search", json={
    "keywords": ["ESM2"],
    "time_range_days": 365,
    "sources": ["PubMed"]
}, timeout=180)
d = r.json()
print(f"Total: {d.get('total')}")
for item in (d.get('results') or [])[:5]:
    print(f"  [{item['source']}] {item.get('venue','')} IF={item.get('if','?')} {item['title'][:60]}")

print("\n=== Test 2: Crossref only ===")
r = httpx.post("http://localhost:8000/api/deep-search", json={
    "keywords": ["ESM2"],
    "time_range_days": 365,
    "sources": ["Crossref"]
}, timeout=180)
d = r.json()
print(f"Total: {d.get('total')}")
for item in (d.get('results') or [])[:5]:
    print(f"  [{item['source']}] {item.get('venue','')} IF={item.get('if','?')} {item['title'][:60]}")
