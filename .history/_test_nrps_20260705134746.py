"""Test ISSN search for NRPStransformer paper."""
import asyncio
import httpx

async def main():
    async with httpx.AsyncClient(timeout=30) as c:
        # Test pISSN
        r = await c.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={"db": "pubmed", "term": '("0002-7863"[issn] AND NRPStransformer)', "retmax": "5", "retmode": "json", "email": "test@test.com"},
        )
        d = r.json()
        print(f"pISSN 0002-7863: {d.get('esearchresult',{}).get('count',0)} results")

        # Test eISSN
        r = await c.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={"db": "pubmed", "term": '("1520-5126"[issn] AND NRPStransformer)', "retmax": "5", "retmode": "json", "email": "test@test.com"},
        )
        d = r.json()
        print(f"eISSN 1520-5126: {d.get('esearchresult',{}).get('count',0)} results")

        # Test with journal name abbreviation
        r = await c.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={"db": "pubmed", "term": '("J Am Chem Soc"[ta] AND NRPStransformer)', "retmax": "5", "retmode": "json", "email": "test@test.com"},
        )
        d = r.json()
        print(f"[ta] J Am Chem Soc: {d.get('esearchresult',{}).get('count',0)} results")

        # Test with wider search
        r = await c.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={"db": "pubmed", "term": '("1520-5126"[issn] OR "0002-7863"[issn]) AND NRPStransformer', "retmax": "5", "retmode": "json", "email": "test@test.com"},
        )
        d = r.json()
        print(f"Both ISSNs: {d.get('esearchresult',{}).get('count',0)} results")

asyncio.run(main())
