"""
Unit tests for CWC RSMS and Reservoir SWOT integration in HydroSwift.
"""

import sys
from pathlib import Path
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hydroswift
from swift_app.cwc_rsms import (
    CwcRsmsClient,
    UnifiedReservoirBuilder,
    encrypt_payload,
    decrypt_payload,
    clean_reservoir_name,
)
from swift_app.cli import build_parser


def test_rsms_crypto_roundtrip():
    """Verify AES-128-CBC encryption and decryption round-trip."""
    original = {"vchBulletinName": "", "from_date": "2026-01-01", "to_date": "2026-10-01", "limit": 50}
    encrypted = encrypt_payload(original)
    assert isinstance(encrypted, str)
    assert len(encrypted) > 10

    decrypted = decrypt_payload(encrypted)
    assert decrypted == original


def test_clean_reservoir_name():
    """Verify reservoir name normalization rules."""
    assert clean_reservoir_name("HIRAKUD DAM") == "HIRAKUD"
    assert clean_reservoir_name("NAGARJUNA SAGAR") == "NAGARJUNA"
    assert clean_reservoir_name("PANSHET DAM (TANAJISAGAR)") == "PANSHET"
    assert clean_reservoir_name("UND-1") == "UND1"


def test_cwc_reservoirs_namespace_public_api():
    """Verify that hydroswift.cwc.reservoirs and hydroswift.rsms are exported and callable."""
    assert hasattr(hydroswift.cwc, "reservoirs")
    assert hasattr(hydroswift, "rsms")
    assert hasattr(hydroswift, "swot_reservoir_merge")

    # Verify namespace methods
    assert callable(hydroswift.cwc.reservoirs.daily)
    assert callable(hydroswift.cwc.reservoirs.bulletins)
    assert callable(hydroswift.cwc.reservoirs.backfill)
    assert callable(hydroswift.cwc.reservoirs.build_database)

    assert callable(hydroswift.rsms.daily)
    assert callable(hydroswift.rsms.bulletins)
    assert callable(hydroswift.rsms.backfill)
    assert callable(hydroswift.rsms.build_database)


def test_cli_flags_present():
    """Verify that CLI parser includes RSMS and reservoir merge flags."""
    parser = build_parser()
    actions = {a.dest: a for a in parser._actions}

    assert "rsms_daily" in actions
    assert "rsms_bulletins" in actions
    assert "rsms_backfill" in actions
    assert "swot_reservoir_merge" in actions
    assert "reservoir_shp" in actions
    assert "swot_db" in actions
    assert "gauge_cache" in actions


def test_anomaly_correction_in_builder(tmp_path):
    """Test that Manikdoh 10x decimal typo and Rihand feet-to-meters shift are fixed."""
    import geopandas as gpd
    from shapely.geometry import Polygon

    # Create dummy shapefile
    poly = Polygon([(75.0, 15.0), (75.1, 15.0), (75.1, 15.1), (75.0, 15.1)])
    shp_df = gpd.GeoDataFrame(
        {
            "id": [88, 57],
            "name": ["MANIKDOH", "RIHAND"],
            "basin": ["Godavari", "Ganga"],
            "geometry": [poly, poly],
        },
        crs="EPSG:4326",
    )
    shp_path = tmp_path / "test_reservoirs.shp"
    shp_df.to_file(shp_path)

    # Create dummy gauge dataframe
    gauge_df = pd.DataFrame(
        {
            "reservoir_id": [88, 57, 88, 57],
            "date": ["2026-06-01", "2026-06-01", "2026-06-08", "2026-06-08"],
            "gauge_wse_m": [7065.4, 78.5, 706.54, 258.0],  # Manikdoh typo (7065.4) & Rihand ft (78.5)
            "gauge_storage_bcm": [0.25, 1.5, 0.25, 1.6],
        }
    )

    # Create dummy SWOT observations
    swot_df = pd.DataFrame(
        {
            "reservoir_id": [88, 57],
            "time_utc": ["2026-06-02 04:00:00", "2026-06-09 10:00:00"],
            "wse_m_q01": [706.2, 257.8],
            "wse_std_m": [0.1, 0.15],
            "area_km2": [25.0, 450.0],
            "sparse_flag": [0, 0],
            "cycle": [1, 1],
            "pass": [10, 20],
        }
    )

    out_gpkg = tmp_path / "test_unified.gpkg"
    out_sqlite = tmp_path / "test_unified.sqlite"
    out_parquet = tmp_path / "test_unified.parquet"

    metrics = UnifiedReservoirBuilder.build_database(
        reservoir_shp=shp_path,
        swot_observations=swot_df,
        gauge_source=gauge_df,
        output_gpkg=out_gpkg,
        output_sqlite=out_sqlite,
        output_parquet=out_parquet,
        tolerance_days=3.5,
        fix_anomalies=True,
    )

    assert metrics["n_reservoirs"] == 2
    assert metrics["n_swot_observations"] == 2
    assert metrics["n_swot_matched"] == 2

    # Check that SQLite table has corrected values
    import sqlite3

    with sqlite3.connect(out_sqlite) as con:
        g_rows = pd.read_sql_query("SELECT * FROM gauge_timeseries ORDER BY reservoir_id, date", con)

        # Manikdoh row 0 should be corrected from 7065.4 to ~706.54
        manikdoh_level = g_rows.loc[g_rows["reservoir_id"] == 88, "gauge_wse_m"].iloc[0]
        assert 700.0 < manikdoh_level < 715.0

        # Rihand row 0 should be corrected from 78.5 to ~257.5
        rihand_level = g_rows.loc[g_rows["reservoir_id"] == 57, "gauge_wse_m"].iloc[0]
        assert 250.0 < rihand_level < 265.0
