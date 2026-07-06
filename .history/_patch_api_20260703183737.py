with open("app/api.py", "r", encoding="utf-8") as f:
    c = f.read()
c = c.replace(
    '"ACS":             {"color": "#00629B", "bg": "#E1EEF6"},',
    '"ACS":             {"color": "#00629B", "bg": "#E1EEF6"},'
    '\n    "PubMed":         {"color": "#2E8B57", "bg": "#E8F5EE"},'
)
c = c.replace(
    '"ACS": "JACS/ACS SynBio 等"}.get(n, "")}',
    '"ACS": "JACS/ACS SynBio 等",\n                          "PubMed": "PubMed/MEDLINE 生物医学"}.get(n, "")}'
)
c = c.replace(
    '"Nature", "ACS"]]',
    '"Nature", "ACS", "PubMed"]]'
)
with open("app/api.py", "w", encoding="utf-8") as f:
    f.write(c)
print("OK")
