"""Debug journal filtering."""
from app.sources import pubmed, crossref

# Simulate what deep_search does
pubmed.set_journals(["Nature", "Science", "Cell"])
print("pubmed._ACTIVE_JOURNALS =", pubmed._ACTIVE_JOURNALS)
print("crossref._pm._ACTIVE_JOURNALS =", crossref._pm._ACTIVE_JOURNALS)

# Test _journal_matches
print("\nTesting _journal_matches:")
print("  Nature:", crossref._journal_matches("Nature", ""))
print("  Nature (ISSN):", crossref._journal_matches("Nature", "0028-0836"))
print("  Discover Applied Sciences:", crossref._journal_matches("Discover Applied Sciences", ""))
print("  International Journal of Humanities:", crossref._journal_matches("International Journal of Humanities", ""))
