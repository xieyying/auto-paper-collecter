"""Test PMC full pipeline"""
import asyncio, sys; sys.path.insert(0,'.')
from app.sources.pmc import search

async def t():
    items = await search('ESM2', retmax=5)
    print(f'Items: {len(items)}')
    for it in items:
        print(f'  Date: {it.published_at}')
        print(f'  Title: {it.title[:50]}')
    print()
    # Check if any have dates in the last year
    import datetime as dt
    cutoff = dt.datetime.now() - dt.timedelta(days=365)
    filtered = [it for it in items if it.published_at and it.published_at >= cutoff]
    print(f'After 1-year filter: {len(filtered)}')

asyncio.run(t())
