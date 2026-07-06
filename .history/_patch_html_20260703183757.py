with open("static/index.html", "r", encoding="utf-8") as f:
    c = f.read()

# 1) SRC_META
c = c.replace(
    "'ACS': { color:'#00629B', bg:'#E1EEF6', desc:'JACS / ACS SynBio 等 ACS 期刊' },",
    "'ACS': { color:'#00629B', bg:'#E1EEF6', desc:'JACS / ACS SynBio 等 ACS 期刊' },\n      'PubMed': { color:'#2E8B57', bg:'#E8F5EE', desc:'PubMed / MEDLINE 生物医学文献' },"
)

# 2) defaultForm sources
c = c.replace(
    "'Nature': true, 'ACS': true }",
    "'Nature': true, 'ACS': true, 'PubMed': true }"
)

# 3) SRCMAP (for feed badge colors)
c = c.replace(
    "'学术新闻':['#7C4DD9','#F0EAFB'] };",
    "'学术新闻':['#7C4DD9','#F0EAFB'], 'PubMed':['#2E8B57','#E8F5EE'] };"
)

with open("static/index.html", "w", encoding="utf-8") as f:
    f.write(c)
print("OK")
