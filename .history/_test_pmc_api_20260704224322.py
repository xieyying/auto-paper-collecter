"""Test PMC search with all: prefix"""
import httpx, asyncio

async def t():
    async with httpx.AsyncClient(timeout=15) as c:
        # Test with all: prefix (what pmc.py uses)
        params = {'db':'pmc', 'term':'all:"ESM2"', 'retmax':'3', 'retmode':'json', 'email':'test@example.com'}
        r = await c.get('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi', params=params)
        data = r.json()
        ids = data.get('esearchresult',{}).get('idlist',[])
        print(f'all: prefix IDs: {ids}')

        # Without prefix
        params2 = {'db':'pmc', 'term':'ESM2', 'retmax':'3', 'retmode':'json', 'email':'test@example.com'}
        r2 = await c.get('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi', params=params2)
        data2 = r2.json()
        ids2 = data2.get('esearchresult',{}).get('idlist',[])
        print(f'no prefix IDs: {ids2}')

        # Without quotes
        params3 = {'db':'pmc', 'term': 'all:ESM2', 'retmax':'3', 'retmode':'json', 'email':'test@example.com'}
        r3 = await c.get('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi', params=params3)
        data3 = r3.json()
        ids3 = data3.get('esearchresult',{}).get('idlist',[])
        print(f'all:ESM2 (no quotes) IDs: {ids3}')

asyncio.run(t())
