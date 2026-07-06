"""Journal Impact Factor lookup from 2026IF.xlsx (JCR 2025 data).

Columns in the Excel: B=Journal name, C=Abbreviated journal, J=2025 JIF.
Matches venue by: exact abbreviated name → exact full name → substring.
"""
import os
import openpyxl

_dir = os.path.join(os.path.dirname(__file__), "sources")
_path = os.path.join(_dir, "2026IF.xlsx")

_IF_MAP: dict[str, float] = {}

if os.path.isfile(_path):
    try:
        wb = openpyxl.load_workbook(_path, read_only=True)
        ws = wb.active
        for row in ws.iter_rows(min_row=2, values_only=True):
            full_name = str(row[1]).strip() if row[1] else ""
            abbr_name = str(row[2]).strip() if row[2] else ""
            if_value = row[9]  # Column J = index 9 (0-based)
            if if_value is None:
                continue
            try:
                if_val = float(if_value)
            except (ValueError, TypeError):
                continue
            if abbr_name:
                _IF_MAP[abbr_name.lower()] = if_val
            if full_name and full_name.lower() != abbr_name.lower():
                _IF_MAP[full_name.lower()] = if_val
        wb.close()
        print(f"[impact] loaded {len(_IF_MAP)} entries from 2026IF.xlsx", flush=True)
    except Exception as e:
        print(f"[impact] failed to load {_path}: {e}", flush=True)
else:
    print(f"[impact] {_path} not found", flush=True)


def get_impact_factor(journal: str) -> float | None:
    """Return the impact factor for a journal name, or None if unknown."""
    if not journal:
        return None
    j = journal.strip().lower()
    # Exact match
    if j in _IF_MAP:
        return _IF_MAP[j]
    # Substring match (e.g. "Nature" in "Nature Biotechnology")
    for key, val in _IF_MAP.items():
        if key in j or j in key:
            return val
    return None
