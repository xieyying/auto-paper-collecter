import asyncio, sys
sys.path.insert(0, '.')
from app.pipeline.deep_search import deep_search

async def test():
    results = await deep_search(['ESM2', 'prediction'], time_range_days=365)
    print(f'Results: {len(results)}')
    for r in results[:5]:
        topic = r.get("topic", "")
        print(f'  Topic: {topic!r}')
        print(f'  Title: {r["title"][:70]}')
        print()

asyncio.run(test())
