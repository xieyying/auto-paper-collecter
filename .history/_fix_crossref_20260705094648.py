"""Fix ISSN indentation in crossref.py and acs.py"""
import ast

for path in ["app/sources/crossref.py", "app/sources/acs.py"]:
    with open(path, "r", encoding="utf-8") as f:
        c = f.read()
    
    # Find the misplaced ISSN block - it's after authors loop
    old = '''        # Extract ISSN from Crossref response
        issn_list = it.get("ISSN") or []
        issn = issn_list[0] if issn_list else ""
        eissn = ""
        for itype in (it.get("issn-type") or []):
            if itype.get("type") == "electronic":
                eissn = itype.get("value", "")
'''
    
    new = '''                # Extract ISSN
                issn_list = it.get("ISSN") or []
                issn_val = issn_list[0] if issn_list else ""
                eissn_val = ""
                for itype in (it.get("issn-type") or []):
                    if itype.get("type") == "electronic":
                        eissn_val = itype.get("value", "")
'''
    
    if old in c:
        c = c.replace(old, new)
        # Also fix the items.append and .issn references
        c = c.replace(
            "items[-1].issn = issn\n        items[-1].eissn = eissn",
            "items[-1].issn = issn_val\n        items[-1].eissn = eissn_val"
        )
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(c)
        ast.parse(c)
        print(f"{path} fixed")
    else:
        print(f"{path}: pattern not found")
        # Show what's around items.append
        idx = c.find("items.append(RawItem(")
        if idx >= 0:
            print(c[idx-100:idx+200])

