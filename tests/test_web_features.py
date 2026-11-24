"""Unit tests for web dashboard features: dropdown variables, basin auto-zoom, official GeoJSON layers, folder picker, and reservoir mapping."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from hydroswift.core.boundaries import (
    STANDARD_VARIABLES,
    get_basin_bounds,
    load_basin_geojson,
    load_india_boundary_geojson,
    load_aquifers_geojson,
)
from hydroswift.core.mapping import create_map
from hydroswift.gui.desktop import choose_folder


def test_standard_variables_contains_key_types():
    assert "All Variables" in STANDARD_VARIABLES
    assert "Water level" in STANDARD_VARIABLES
    assert "Discharge" in STANDARD_VARIABLES
    assert "Rainfall" in STANDARD_VARIABLES
    assert "Groundwater level" in STANDARD_VARIABLES
    assert "Reservoir storage" in STANDARD_VARIABLES
    assert "Custom..." in STANDARD_VARIABLES


def test_get_basin_bounds_returns_valid_coords():
    # India default bounds
    default_b = get_basin_bounds("all")
    assert len(default_b) == 2
    assert default_b[0][0] < default_b[1][0]  # min_lat < max_lat
    assert default_b[0][1] < default_b[1][1]  # min_lon < max_lon

    # Specific basin bounds
    cauvery_b = get_basin_bounds("Cauvery")
    assert len(cauvery_b) == 2
    min_lat, min_lon = cauvery_b[0]
    max_lat, max_lon = cauvery_b[1]
    assert 9.0 <= min_lat <= 12.0
    assert 12.0 <= max_lat <= 15.0
    assert 74.0 <= min_lon <= 77.0
    assert 78.0 <= max_lon <= 81.0


def test_geojson_loaders_return_feature_collections():
    ind = load_india_boundary_geojson()
    assert ind.get("type") == "FeatureCollection"
    assert len(ind.get("features", [])) >= 1

    basins = load_basin_geojson("all")
    assert basins.get("type") == "FeatureCollection"
    assert len(basins.get("features", [])) >= 20

    cauvery = load_basin_geojson("Cauvery")
    assert len(cauvery.get("features", [])) == 1

    aquifers = load_aquifers_geojson()
    assert aquifers.get("type") == "FeatureCollection"
    assert len(aquifers.get("features", [])) >= 100


def test_create_map_with_bounds_and_layers():
    bounds = [[10.0, 75.0], [13.0, 80.0]]
    ind_geo = load_india_boundary_geojson()
    hmap = create_map(
        None,
        output=None,
        bounds=bounds,
        geojson_layers=[{"name": "India Boundary", "geojson": ind_geo}],
        title="Test Map with Bounds",
    )
    assert hmap.bounds == bounds
    html = hmap.to_html()
    assert "fitBounds" in html
    assert "Test Map with Bounds" in html
    assert "India Boundary" in html


def test_create_map_with_reservoir_dataframe():
    res_df = pd.DataFrame([
        {
            "reservoir_unique_id": "D001",
            "reservoir_name": "KRISHNARAJASAGARA",
            "live_cap_bcm": 1.3,
            "storage_bcm": 1.1,
            "gross_cap_bcm": 1.4,
            "frl_meter": 228.0,
            "dsl_mtr": 190.0,
            "latitude": 12.42,
            "longitude": 76.57,
            "entry_date": "2026-11-20",
        },
        {
            "reservoir_unique_id": "D002",
            "reservoir_name": "METTUR",
            "live_cap_bcm": 2.6,
            "storage_bcm": 0.8,
            "gross_cap_bcm": 2.7,
            "frl_meter": 240.0,
            "dsl_mtr": 200.0,
            "latitude": 11.80,
            "longitude": 77.80,
            "entry_date": "2026-11-20",
        },
    ])
    hmap = create_map(res_df, output=None, title="Reservoir Map")
    assert hmap.stations_count == 2
    html = hmap.to_html()
    assert "KRISHNARAJASAGARA" in html
    assert "METTUR" in html
    assert "Live Storage" in html
    assert "Live Capacity" in html
    assert "cartocdn" not in html
    assert "boundaryPane" in html
    assert "stationPane" in html
    assert "stopPropagation" in html
    assert "Esri Topographic" in html


def test_choose_folder_mock(tmp_path):
    # Test fallback / subprocess mock
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=str(tmp_path) + "\n")
        chosen = choose_folder(start=tmp_path)
        assert chosen == str(tmp_path)
