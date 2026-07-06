"""Journal Impact Factor lookup from 2026IF.xlsx (JCR 2025 data)."""
import os, re
import openpyxl

_dir = os.path.join(os.path.dirname(__file__), "sources")
_path = os.path.join(_dir, "2026IF.xlsx")

_IF_MAP: dict[str, float] = {}
_IF_NORM: dict[str, float] = {}

if os.path.isfile(_path):
    try:
        wb = openpyxl.load_workbook(_path, read_only=True)
        ws = wb.active
        for row in ws.iter_rows(min_row=2, values_only=True):
            full_name = str(row[1]).strip() if row[1] else ""
            abbr_name = str(row[2]).strip() if row[2] else ""
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
        wb.close()
        print(f"[impact] loaded {len(_IF_MAP)} entries, {len(_IF_NORM)} normalized", flush=True)
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
    # 2) Normalized match (strip dots/spaces/hyphens)
    norm = re.sub(r"[^a-z0-9]", "", j)
    if norm in _IF_NORM:
        return _IF_NORM[norm]
    # 3) Substring match — only if the key is at least 5 chars AND
    #    is a substantial portion (>= 50%) of the journal name
    for key, val in _IF_MAP.items():
        if len(key) >= 5 and (key in j or j in key):
            if len(key) >= len(j) * 0.5:
                return val
    return None
