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


STANDARD_VARIABLES: List[str] = [
    "All Variables",
    "Water level",
    "Discharge",
    "Rainfall",
    "Groundwater level",
    "Reservoir storage",
    "Water quality",
    "Custom...",
]


@lru_cache(maxsize=64)
def get_basin_bounds(basin: Optional[str] = None) -> List[List[float]]:
    """Calculate Leaflet bounding box [[min_lat, min_lon], [max_lat, max_lon]] for a river basin.

    If basin is None, 'all', or unrecognized, returns India national bounding box:
    [[6.5, 68.0], [37.5, 97.5]].
    """
    india_bounds = [[6.5, 68.0], [37.5, 97.5]]
    if not basin or str(basin).strip().lower() in ("all", "any", "all basins", "all india"):
        return india_bounds

    gj = load_basin_geojson(basin)
    features = gj.get("features", [])
    if not features:
        return india_bounds

    def _extract_coords(geom):
        coords = geom.get("coordinates", [])
        def _flatten(c):
            if not c:
                return
            if isinstance(c[0], (int, float)):
                yield c
            else:
                for sub in c:
                    yield from _flatten(sub)
        return list(_flatten(coords))

    pts = []
    for f in features:
        g = f.get("geometry")
        if g:
            pts.extend(_extract_coords(g))

    if not pts:
        return india_bounds

    min_lon = min(p[0] for p in pts)
    max_lon = max(p[0] for p in pts)
    min_lat = min(p[1] for p in pts)
    max_lat = max(p[1] for p in pts)
    d_lat = max(0.05, (max_lat - min_lat) * 0.02)
    d_lon = max(0.05, (max_lon - min_lon) * 0.02)
    return [[min_lat - d_lat, min_lon - d_lon], [max_lat + d_lat, max_lon + d_lon]]


@lru_cache(maxsize=1)
def load_basin_geojson(basin: Optional[str] = None) -> dict:
    """Load bundled CWC basin GeoJSON FeatureCollection.

    If ``basin`` is specified, filters features to that basin.
    """
    paths = [
        Path(__file__).parent.parent / "data" / "cwc_basins.geojson",
        Path("/run/media/carbform/Expansion/GW_Wris_may2024/Central Water Commission Basin.geojson"),
    ]
    data = None
    for p in paths:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                break
            except Exception:
                pass

    if not data:
        return {"type": "FeatureCollection", "features": []}

    if not basin or basin.lower() in ("all", "any"):
        # Filter out features with no basin name
        data["features"] = [f for f in data.get("features", []) if f.get("properties", {}).get("Basin_Name") not in (None, "null")]
        return data

    canon = canonical_basin(basin)
    filtered = []
    for f in data.get("features", []):
        bname = f.get("properties", {}).get("Basin_Name")
        if bname and (bname == canon or bname.lower() == str(basin).lower() or str(basin).lower() in bname.lower()):
            filtered.append(f)

    return {"type": "FeatureCollection", "features": filtered}


@lru_cache(maxsize=1)
def load_india_boundary_geojson() -> dict:
    """Load India national boundary GeoJSON FeatureCollection."""
    paths = [
        Path(__file__).parent.parent / "data" / "india_boundary.geojson",
        Path("/run/media/carbform/Expansion/GW_Wris_may2024/india_boundary.geojson"),
    ]
    for p in paths:
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {"type": "FeatureCollection", "features": []}


@lru_cache(maxsize=4)
def load_aquifers_geojson(state: Optional[str] = None) -> dict:
    """Load Major Aquifers GeoJSON FeatureCollection, optionally filtered by state."""
    paths = [
        Path(__file__).parent.parent / "data" / "major_aquifers.geojson",
        Path("/run/media/carbform/Expansion/GW_Wris_may2024/Major Aquifers.geojson"),
    ]
    data = None
    for p in paths:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                break
            except Exception:
                pass

    if not data:
        return {"type": "FeatureCollection", "features": []}

    if not state or state.lower() in ("all", "any"):
        return data

    s_lower = state.strip().lower()
    filtered = []
    for f in data.get("features", []):
        st = str(f.get("properties", {}).get("state", "")).lower()
        if s_lower in st or st in s_lower:
            filtered.append(f)
    return {"type": "FeatureCollection", "features": filtered}
