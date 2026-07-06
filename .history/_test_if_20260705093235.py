"""Test ISSN-based IF"""
import asyncio, sys
sys.path.insert(0, '.')
from app.sources.pubmed import search
from app.impact import get_impact_factor

async def t():
    items = await search('ESM2', 3)
    for it in items:
        issn = getattr(it, 'issn', None)
        if_val = get_impact_factor(issn) if issn else get_impact_factor(it.venue)
        print(f'Venue={it.venue}  ISSN={issn}  IF={if_val}')
asyncio.run(t())
