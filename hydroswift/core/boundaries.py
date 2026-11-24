"""Hydrological and Administrative boundary definitions and mappings for India.

Provides cross-referencing between:
1. Hydrological Boundaries: Major Indian River Basins (CWC / India-WRIS standards).
2. Administrative Boundaries: Indian States and Union Territories.

Enables cross-boundary discovery: when a hydrological basin is selected,
NWDP (which indexes datasets administratively) can be automatically queried
for all constituent states of that basin, instead of failing or returning 0 results.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

# Official CWC / India-WRIS Major River Basins
BASIN_TO_STATES: Dict[str, List[str]] = {
    "Barak and Others": [
        "Assam", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Tripura"
    ],
    "Brahmani and Baitarni": [
        "Chhattisgarh", "Jharkhand", "Odisha"
    ],
    "Brahmaputra": [
        "Arunachal Pradesh", "Assam", "Meghalaya", "Nagaland", "Sikkim", "West Bengal"
    ],
    "Cauvery": [
        "Karnataka", "Kerala", "Puducherry", "Tamil Nadu"
    ],
    "East flowing rivers between Mahanadi and Pennar": [
        "Andhra Pradesh", "Odisha"
    ],
    "East flowing rivers between Pennar and Kanyakumari": [
        "Andhra Pradesh", "Karnataka", "Puducherry", "Tamil Nadu"
    ],
    "Ganga": [
        "Bihar", "Chhattisgarh", "Delhi", "Haryana", "Himachal Pradesh",
        "Jharkhand", "Madhya Pradesh", "Rajasthan", "Uttar Pradesh", "Uttarakhand", "West Bengal"
    ],
    "Godavari": [
        "Andhra Pradesh", "Chhattisgarh", "Karnataka", "Madhya Pradesh",
        "Maharashtra", "Odisha", "Puducherry", "Telangana"
    ],
    "Indus": [
        "Chandigarh", "Haryana", "Himachal Pradesh", "Jammu and Kashmir",
        "Ladakh", "Punjab", "Rajasthan"
    ],
    "Krishna": [
        "Andhra Pradesh", "Karnataka", "Maharashtra", "Telangana"
    ],
    "Mahanadi": [
        "Chhattisgarh", "Jharkhand", "Madhya Pradesh", "Maharashtra", "Odisha"
    ],
    "Mahi": [
        "Gujarat", "Madhya Pradesh", "Rajasthan"
    ],
    "Minor rivers draining into Myanmar and Bangladesh": [
        "Manipur", "Mizoram", "Nagaland", "Tripura"
    ],
    "Narmada": [
        "Chhattisgarh", "Gujarat", "Madhya Pradesh", "Maharashtra"
    ],
    "Pennar": [
        "Andhra Pradesh", "Karnataka"
    ],
    "Sabarmati": [
        "Gujarat", "Rajasthan"
    ],
    "Subernarekha": [
        "Jharkhand", "Odisha", "West Bengal"
    ],
    "Tapi": [
        "Gujarat", "Madhya Pradesh", "Maharashtra"
    ],
    "West flowing rivers from Tadri to Kanyakumari": [
        "Karnataka", "Kerala", "Puducherry", "Tamil Nadu"
    ],
    "West flowing rivers from Tapi to Tadri": [
        "Dadra and Nagar Haveli", "Daman and Diu", "Goa", "Gujarat", "Karnataka", "Maharashtra"
    ],
    "West flowing rivers of Kutch and Saurashtra including Luni": [
        "Daman and Diu", "Gujarat", "Rajasthan"
    ],
    "Area of Inland drainage in Rajasthan": [
        "Rajasthan"
    ],
}

# Alias standard variations
BASIN_ALIASES: Dict[str, str] = {
    "brahamaputra": "Brahmaputra",
    "indus (up to border)": "Indus",
    "yamuna basin": "Ganga",
    "yamuna": "Ganga",
    "tapti": "Tapi",
    "kaveri": "Cauvery",
    "west flowing rivers of kutch & saurashtra including luni": "West flowing rivers of Kutch and Saurashtra including Luni",
    "west-flowing rivers from tapi to tadri": "West flowing rivers from Tapi to Tadri",
    "west-flowing rivers from tadri to kanyakumari": "West flowing rivers from Tadri to Kanyakumari",
}

INDIAN_STATES: List[str] = sorted([
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Delhi", "Goa", "Gujarat", "Haryana", "Himachal Pradesh",
    "Jammu and Kashmir", "Jharkhand", "Karnataka", "Kerala", "Ladakh",
    "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
    "Nagaland", "Odisha", "Puducherry", "Punjab", "Rajasthan",
    "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh",
    "Uttarakhand", "West Bengal",
])

INDIAN_BASINS: List[str] = sorted(list(BASIN_TO_STATES.keys()))


# Derive Reverse Mapping: State -> Basins
STATE_TO_BASINS: Dict[str, List[str]] = {}
for _b, _states in BASIN_TO_STATES.items():
    for _st in _states:
        STATE_TO_BASINS.setdefault(_st, []).append(_b)
for _st in STATE_TO_BASINS:
    STATE_TO_BASINS[_st].sort()


def canonical_basin(name: Optional[str]) -> Optional[str]:
    """Resolve basin name to canonical CWC title."""
    if not name:
        return None
    raw = str(name).strip()
    norm = raw.lower()
    if norm in BASIN_ALIASES:
        return BASIN_ALIASES[norm]
    for b in BASIN_TO_STATES:
        if b.lower() == norm or norm in b.lower():
            return b
    return raw


def get_states_for_basin(basin: str) -> List[str]:
    """Get list of constituent Indian states for a given hydrological river basin."""
    c = canonical_basin(basin)
    if c and c in BASIN_TO_STATES:
        return list(BASIN_TO_STATES[c])
    return []


def get_basins_for_state(state: str) -> List[str]:
    """Get list of river basins intersecting an administrative Indian state."""
    if not state:
        return []
    needle = str(state).strip().lower()
    for st_name, basins in STATE_TO_BASINS.items():
        if st_name.lower() == needle or needle in st_name.lower():
            return list(basins)
    return []


@lru_cache(maxsize=1)
def load_basin_geojson(basin: Optional[str] = None) -> dict:
    """Load bundled CWC basin GeoJSON FeatureCollection.

    If ``basin`` is specified, filters features to that basin.
    """
    path = Path(__file__).parent.parent / "data" / "cwc_basins.geojson"
    if not path.exists():
        return {"type": "FeatureCollection", "features": []}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"type": "FeatureCollection", "features": []}

    if not basin or basin.lower() in ("all", "any"):
        # Filter out features with no basin name
        data["features"] = [f for f in data["features"] if f.get("properties", {}).get("Basin_Name") not in (None, "null")]
        return data

    canon = canonical_basin(basin)
    filtered = []
    for f in data.get("features", []):
        bname = f.get("properties", {}).get("Basin_Name")
        if bname and (bname == canon or bname.lower() == str(basin).lower() or str(basin).lower() in bname.lower()):
            filtered.append(f)

    return {"type": "FeatureCollection", "features": filtered}
