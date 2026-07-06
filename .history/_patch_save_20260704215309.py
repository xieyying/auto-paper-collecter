with open("app/api.py", "r", encoding="utf-8") as f:
    c = f.read()

# Find insertion point after the save endpoint and before get_settings
insert_point = c.find("@router.get(\"/settings\")")

save_by_ref = """

@router.post("/save-by-ref")
def save_by_ref(body: dict = Body(...), db: Session = Depends(get_db)):
    \"\"\"Save/rate a paper by ext_id (for transient deep-search results).\"\"\"
    ext_id = body.get("ext_id", "")
    if not ext_id:
        return {"ok": False}
    # Find or create the paper
    paper = db.query(Paper).filter(Paper.ext_id == ext_id).first()
    if not paper:
        paper = Paper(
            ext_id=ext_id,
            source=body.get("source", ""),
            title=body.get("title", ""),
            abstract=body.get("abstract", ""),
            authors=body.get("authors", "[]"),
            url=body.get("url", ""),
            venue=body.get("venue", ""),
            doi=body.get("doi", ""),
            published_at=None,
            fetched_at=dt.datetime.utcnow(),
            tldr="", method="", contributions="[]",
        )
        # Parse date if provided
        pub_str = body.get("published", "")
        if pub_str:
            try:
                paper.published_at = dt.datetime.strptime(pub_str, "%Y-%m-%d")
            except ValueError:
                pass
        db.add(paper)
        db.flush()
    # Upsert SavedItem
    sv = db.query(SavedItem).filter(SavedItem.paper_id == paper.id).first()
    if not sv:
        sv = SavedItem(paper_id=paper.id)
        db.add(sv)
    for f in ("saved", "read"):
        if f in body:
            setattr(sv, f, bool(body[f]))
    if "note" in body:
        sv.note = str(body["note"])
    if "feedback" in body:
        fb = str(body["feedback"])
        sv.feedback = fb if fb in ("up", "down") else ""
    sv.updated_at = dt.datetime.utcnow()
    db.commit()
    return {"ok": True, "paper_id": paper.id}


""" + "\n"

c = c[:insert_point] + save_by_ref + c[insert_point:]

with open("app/api.py", "w", encoding="utf-8") as f:
    f.write(c)
print("OK")
