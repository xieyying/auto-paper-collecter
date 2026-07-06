with open("app/pipeline/fetch.py", "r", encoding="utf-8") as f:
    c = f.read()
old = '"ChemRxiv": chemrxiv.search,         # ChemRxiv preprints\n}'
new = '"ChemRxiv": chemrxiv.search,         # ChemRxiv preprints\n    "PubMed": pubmed.search,\n}'
c = c.replace(old, new)
with open("app/pipeline/fetch.py", "w", encoding="utf-8") as f:
    f.write(c)
print("OK")
