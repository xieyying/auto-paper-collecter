"""Journal Impact Factor lookup from 2026IF.xlsx (JCR 2025 data)."""
import os, re
import openpyxl

_dir = os.path.join(os.path.dirname(__file__), "sources")
_path = os.path.join(_dir, "2026IF.xlsx")

_IF_MAP: dict[str, float] = {}
_IF_NORM: dict[str, float] = {}
_IF_ISSN: dict[str, float] = {}

if os.path.isfile(_path):
    try:
        wb = openpyxl.load_workbook(_path, read_only=True)
        ws = wb.active
        for row in ws.iter_rows(min_row=2, values_only=True):
            full_name = str(row[1]).strip() if row[1] else ""
            abbr_name = str(row[2]).strip() if row[2] else ""
            issn = str(row[4] or "").strip().lower()
            eissn = str(row[5] or "").strip().lower()
            if_value = row[9]
            if if_value is None:
                continue
            try:
                if_val = float(if_value)
            except (ValueError, TypeError):
                continue
            for name in (abbr_name, full_name):
                if name:
                    _IF_MAP[name.lower()] = if_val
                    norm = re.sub(r"[^a-z0-9]", "", name.lower())
                    _IF_NORM[norm] = if_val
            if issn:
                _IF_ISSN[issn] = if_val
            if eissn:
                _IF_ISSN[eissn] = if_val
        wb.close()
        print(f"[impact] loaded {len(_IF_MAP)} names + {len(_IF_ISSN)} ISSNs", flush=True)
    except Exception as e:
        print(f"[impact] failed to load: {e}", flush=True)
else:
    print(f"[impact] {_path} not found", flush=True)


def get_impact_factor(journal: str) -> float | None:
    if not journal:
        return None
    j = journal.strip().lower()
    # 1) Exact match
    if j in _IF_MAP:
        return _IF_MAP[j]
    # 2) ISSN match
    if re.match(r"^\d{4}-\d{3}[\dxX]$", j) and j in _IF_ISSN:
        return _IF_ISSN[j]
    # 3) Normalized match
    norm = re.sub(r"[^a-z0-9]", "", j)
    if norm in _IF_NORM:
        return _IF_NORM[norm]
    # 4) Substring match — at least 65% coverage to avoid false matches
    for key, val in _IF_MAP.items():
        if len(key) >= 5 and (key in j or j in key):
            if len(key) >= len(j) * 0.65:
                return val
    return None
