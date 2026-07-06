"""Patch ISSN extraction into Crossref-based sources"""
import glob, re

# Files that use Crossref API
files = [
    ("app/sources/crossref.py", 'select": "DOI,title,author,abstract,URL,container-title,published,type'),
    ("app/sources/nature.py", 'select": "DOI,title,author,abstract,URL,container-title,published,type'),
    ("app/sources/acs.py", 'select": "DOI,title,author,abstract,URL,container-title,published,type'),
]

for path, select_str in files:
    with open(path, "r", encoding="utf-8") as f:
        c = f.read()
    
    # Add ISSN to select
    old_select = select_str
    new_select = select_str.replace("container-title,published,type", "container-title,published,type,ISSN,issn-type")
    c = c.replace(old_select, new_select)
    
    # Find the items.append(RawItem( block and add issn after doi
    # Pattern: doi=doi, published_at=pub_date
    c = c.replace(
        'doi=doi,\n            published_at=pub_date,',
        'doi=doi,\n            issn=issn,\n            published_at=pub_date,'
    )
    
    # Add ISSN extraction after venue definition
    # Pattern varies - need to add issn = ... before items.append
    # Let's find `items.append(RawItem(` and add issn before it
    old = 'items.append(RawItem('
    new = '        issn = _extract_issn(it)\n\n        items.append(RawItem('
    c = c.replace(old, new)
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(c)
    print(f"{path} OK")

# Now add _extract_issn helper function and class-level issn field to each
# Actually simpler: just add the issn to RawItem via setattr after append
# Let me redo - instead modify the pattern differently
print("\nNow adding issn via dynamic attribute...")

for path, _ in files:
    with open(path, "r", encoding="utf-8") as f:
        c = f.read()
    # Find `issn = _extract_issn(it)` and the items.append block
    # Replace the extraction + append with: extract issn, append, then set attr
    old = '''issn = _extract_issn(it)

        items.append(RawItem('''
    new = '''# Extract ISSN from Crossref response
        issn_list = it.get("ISSN") or []
        issn = issn_list[0] if issn_list else ""
        eissn = ""
        for itype in (it.get("issn-type") or []):
            if itype.get("type") == "electronic":
                eissn = itype.get("value", "")

        items.append(RawItem('''
    c = c.replace(old, new)
    
    # Add .issn and .eissn after the append
    c = c.replace(
        'published_at=pub_date,\n        ))\n        return items\n',
        'published_at=pub_date,\n        ))\n        items[-1].issn = issn\n        items[-1].eissn = eissn\n        return items\n'
    )
    # Also handle the single-item return case in nature/acs
    c = c.replace(
        'published_at=pub_date,\n        ))\n    return uniq\n',
        'published_at=pub_date,\n        ))\n        items[-1].issn = issn\n        items[-1].eissn = eissn\n    return uniq\n'
    )
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(c)
    print(f"{path} - added ISSN extraction")

print("Done")
