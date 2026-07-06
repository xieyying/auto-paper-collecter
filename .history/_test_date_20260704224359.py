"""Check PMC date format in XML"""
import httpx, asyncio

async def t():
    params = {'db':'pmc', 'id':'13044805', 'retmode':'xml', 'rettype':'abstract', 'email':'test@example.com'}
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi', params=params)
    # Find the date section
    import re
    m = re.search(r'<pub-date[^>]*>.*?</pub-date>', r.text, re.S)
    if m:
        print('pub-date block:', m.group(0))
    else:
        print('No pub-date found')
    # Check all date-related tags
    for tag in ['pub-date', 'year', 'month', 'day', 'history']:
        for mm in re.finditer(rf'<{tag}[^>]*>.*?</{tag}>', r.text, re.S):
            print(f'{tag}: {mm.group(0)[:200]}')

asyncio.run(t())
