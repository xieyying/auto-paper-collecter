"""Compare [ta] vs [issn] search results."""
import asyncio
import httpx

async def main():
    async with httpx.AsyncClient(timeout=30) as c:
        # Test 1: Using [ta] (journal title abbreviation)
        r1 = await c.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={
                "db": "pubmed",
                "term": '("Nature"[ta] AND ESM2)',
                "retmax": "10",
                "retmode": "json",
                "email": "test@test.com",
            },
        )
        d1 = r1.json()
        print(f"[ta] query 'Nature': {d1.get('esearchresult',{}).get('count',0)} results")
        idlist1 = d1.get("esearchresult", {}).get("idlist", [])
        if idlist1:
            print(f"  First IDs: {idlist1[:3]}")

        # Test 2: Using [issn]
        r2 = await c.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={
                "db": "pubmed",
                "term": '("0028-0836"[issn] AND ESM2)',
                "retmax": "10",
                "retmode": "json",
                "email": "test@test.com",
            },
        )
        d2 = r2.json()
        print(f"\n[issn] query '0028-0836': {d2.get('esearchresult',{}).get('count',0)} results")
        idlist2 = d2.get("esearchresult", {}).get("idlist", [])
        if idlist2:
            print(f"  First IDs: {idlist2[:3]}")

        # Test 3: Check if Nature's ISSN in JCR is different from PubMed's
        r3 = await c.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={
                "db": "pubmed",
                "term": '("Nature"[ta] AND 2026[dp] AND ESM2)',
                "retmax": "10",
                "retmode": "json",
                "email": "test@test.com",
            },
        )
        d3 = r3.json()
        print(f"\n[ta] 'Nature' + 2026: {d3.get('esearchresult',{}).get('count',0)} results")
        idlist3 = d3.get("esearchresult", {}).get("idlist", [])
        if idlist3:
            print(f"  First IDs: {idlist3[:3]}")

        # Test 4: Nature Biotechnology
        r4 = await c.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={
                "db": "pubmed",
                "term": '("Nat Biotechnol"[ta] AND ESM2)',
                "retmax": "10",
                "retmode": "json",
                "email": "test@test.com",
            },
        )
        d4 = r4.json()
        print(f"\n[ta] 'Nat Biotechnol': {d4.get('esearchresult',{}).get('count',0)} results")

        # Test 5: Nat Biotechnol by ISSN
        r5 = await c.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={
                "db": "pubmed",
                "term": '("1087-0156"[issn] AND ESM2)',
                "retmax": "10",
                "retmode": "json",
                "email": "test@test.com",
            },
        )
        d5 = r5.json()
        print(f"\n[issn] '1087-0156' (Nat Biotechnol): {d5.get('esearchresult',{}).get('count',0)} results")


asyncio.run(main())
