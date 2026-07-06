"""Journal Impact Factor lookup from local data/impact_factors.json."""
import json
import os

_dir = os.path.join(os.path.dirname(__file__), "..", "data")
_path = os.path.join(_dir, "impact_factors.json")

_IF_MAP: dict[str, float] = {}
if os.path.isfile(_path):
    try:
        with open(_path, encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if not k.startswith("_"):
                _IF_MAP[k.lower()] = float(v)
    except Exception as e:
        print(f"[impact] failed to load {_path}: {e}", flush=True)


def get_impact_factor(journal: str) -> float | None:
    """Return the impact factor for a journal, or None if unknown.

    Matches first by exact lowercase, then by containment (journal name
    is a substring of a known key or vice versa).
    """
    if not journal:
        return None
    j = journal.strip().lower()
    # Exact match
    if j in _IF_MAP:
        return _IF_MAP[j]
    # Known key is contained in journal name (e.g. "Nature" in "Nature Biotechnology")
    for key, val in _IF_MAP.items():
        if key in j or j in key:
            return val
    return None
