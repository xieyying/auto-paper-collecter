"""De-duplicate raw items across sources. Prefer DOI, fall back to normalized title."""
import re

_norm = re.compile(r"[^a-z0-9\u4e00-\u9fff]+")


def _key(item):
    if item.doi:
        return ("doi", item.doi.lower())
    t = _norm.sub("", (item.title or "").lower())
    return ("title", t[:80])


def dedup(items):
    seen = {}
    for it in items:
        k = _key(it)
        if k not in seen:
            seen[k] = it
        else:
            # keep the one with a richer abstract / a tldr
            cur = seen[k]
            if (len(it.abstract or "") > len(cur.abstract or "")) or (it.tldr and not cur.tldr):
                seen[k] = it
    return list(seen.values())
