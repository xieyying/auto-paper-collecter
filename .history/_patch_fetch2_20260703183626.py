with open("app/pipeline/fetch.py", "r", encoding="utf-8") as f:
    c = f.read()
c = c.replace('"bioRxiv": True, "ChemRxiv": True',
              '"bioRxiv": True, "ChemRxiv": True, "PubMed": True')
with open("app/pipeline/fetch.py", "w", encoding="utf-8") as f:
    f.write(c)
print("OK")
