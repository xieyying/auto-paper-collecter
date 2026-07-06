"""Fix ISSN indentation in nature.py"""
with open("app/sources/nature.py", "r", encoding="utf-8") as f:
    c = f.read()

# The broken section has the ISSN block and items.append at wrong indent
old = '''                        authors.append(nm)
                        # Extract ISSN from Crossref response
        issn_list = it.get("ISSN") or []
        issn = issn_list[0] if issn_list else ""
        eissn = ""
        for itype in (it.get("issn-type") or []):
            if itype.get("type") == "electronic":
                eissn = itype.get("value", "")

        items.append(RawItem(
                    source="Nature",
                    title=" ".join(title_list[0].split()),
                    abstract=_clean_abstract(it.get("abstract", "")),
                    url=it.get("URL", "https://doi.org/" + doi if doi else ""),
                    ext_id=f"doi:{doi}" if doi else f"nature:{title_list[0][:60]}",
                    authors=authors,
                    venue=venue,
                    doi=doi,
                    published_at=published,
                ))
        items[-1].issn = issn
        items[-1].eissn = eissn'''

new = '''                        authors.append(nm)
                # Extract ISSN
                issn_list = it.get("ISSN") or []
                issn_val = issn_list[0] if issn_list else ""
                eissn_val = ""
                for itype in (it.get("issn-type") or []):
                    if itype.get("type") == "electronic":
                        eissn_val = itype.get("value", "")
                items.append(RawItem(
                    source="Nature",
                    title=" ".join(title_list[0].split()),
                    abstract=_clean_abstract(it.get("abstract", "")),
                    url=it.get("URL", "https://doi.org/" + doi if doi else ""),
                    ext_id=f"doi:{doi}" if doi else f"nature:{title_list[0][:60]}",
                    authors=authors,
                    venue=venue,
                    doi=doi,
                    published_at=published,
                ))
                items[-1].issn = issn_val
                items[-1].eissn = eissn_val'''

if old in c:
    c = c.replace(old, new)
    with open("app/sources/nature.py", "w", encoding="utf-8") as f:
        f.write(c)
    print("nature.py fixed")
    import ast; ast.parse(c); print("syntax OK")
else:
    print("Pattern not found in nature.py")
    # Debug: show what's around that area
    idx = c.find("authors.append(nm)")
    if idx >= 0:
        print(c[idx:idx+600])
