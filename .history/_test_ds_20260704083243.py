"""Test deep search"""
import asyncio, sys
sys.path.insert(0, '.')
from app.pipeline.deep_search import deep_search

async def t():
    results = await deep_search(['ESM2', 'prediction'], time_range_days=365)
    print(f'Results: {len(results)}')
    for r in results[:3]:
        print(f'  Topic: {r.get("topic","")!r}')
asyncio.run(t())
