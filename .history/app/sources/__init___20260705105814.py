from dataclasses import dataclass, field
import datetime as dt
from typing import List, Optional


@dataclass
class RawItem:
    source: str
    title: str
    abstract: str
    url: str
    ext_id: str
    authors: List[str] = field(default_factory=list)
    venue: str = ""
    doi: str = ""
    published_at: Optional[dt.datetime] = None
    tldr: str = ""        # some sources (Semantic Scholar) provide one
    issn: str = ""         # journal ISSN for impact factor / journal filtering
