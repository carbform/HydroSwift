"""SWOT satellite KaRIn altimetry & in-situ gauge harmonization module.

This module is staged as an experimental / research component of HydroSwift
for multi-source satellite altimetry validation with CWC reservoir bulletins.
"""

from __future__ import annotations

import glob
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional, Union

import numpy as np
import pandas as pd

from ..utils import Console


class UnifiedReservoirBuilder:
    """Builds unified multi-source reservoir databases (GPKG, SQLite, Parquet)."""

    @staticmethod
    def build_database(
        reservoir_shp: Union[str, Path],
        swot_observations: Union[str, Path, pd.DataFrame],
        gauge_source: Union[str, Path, pd.DataFrame],
        output_gpkg: Optional[Union[str, Path]] = None,
        output_sqlite: Optional[Union[str, Path]] = None,
        output_parquet: Optional[Union[str, Path]] = None,
        cwc_metadata: Optional[Union[str, Path, pd.DataFrame]] = None,
        tolerance_days: float = 3.5,
        fix_anomalies: bool = True,
    ) -> Dict[str, Any]:
        """
        Merge SWOT KaRIn satellite observations with in-situ gauge measurements
        and shapefile geometries to produce unified spatial & time series artifacts.

        Parameters
        ----------
        reservoir_shp : str or Path
            Path to reservoir polygon shapefile or GeoPackage.
        swot_observations : str, Path, or DataFrame
            Path to SQLite database containing `observations` table, or DataFrame.
        gauge_source : str, Path, or DataFrame
            Directory of gauge CSVs (`<reservoir_id>.csv`), single CSV file, or DataFrame.
        output_gpkg : str or Path, optional
            Path for destination GeoPackage.
        output_sqlite : str or Path, optional
            Path for destination SQLite database.
        output_parquet : str or Path, optional
            Path for destination Parquet unified time series file.
        cwc_metadata : str, Path, or DataFrame, optional
            Metadata table containing FRL, DSL, capacities.
        tolerance_days : float, default 3.5
            Temporal tolerance in days to match SWOT overpass with weekly gauge data.
        fix_anomalies : bool, default True
            Fix known transcription outliers (Manikdoh 10x typo, Rihand ft/m unit shift).

        Returns
        -------
        dict
            Summary metrics including row counts and output paths.
        """
        import geopandas as gpd

        Console.section("SWOT & Gauge Unified Reservoir Database Builder")

        # 1. Load Geometries
        Console.info("Step 1: Loading reservoir geometries & dissolving multipart features...")
        shp = gpd.read_file(reservoir_shp)
        id_col = "id" if "id" in shp.columns else ("reservoir_id" if "reservoir_id" in shp.columns else shp.columns[0])
        name_col = "name" if "name" in shp.columns else ("reservoir_name" if "reservoir_name" in shp.columns else id_col)
        basin_col = "basin" if "basin" in shp.columns else None

        cols_to_keep = [id_col, name_col]
        if basin_col:
            cols_to_keep.append(basin_col)
        cols_to_keep.append("geometry")

        res_geom = shp[cols_to_keep].dissolve(by=id_col, as_index=False)
        res_geom.rename(columns={id_col: "reservoir_id", name_col: "reservoir_name"}, inplace=True)
        res_geom["centroid_lon"] = res_geom.geometry.centroid.x
        res_geom["centroid_lat"] = res_geom.geometry.centroid.y
        try:
            res_geom["area_sqkm"] = res_geom.to_crs(epsg=3857).geometry.area / 1e6
        except Exception:
            res_geom["area_sqkm"] = np.nan

        # Merge metadata if provided
        if cwc_metadata is not None:
            if isinstance(cwc_metadata, (str, Path)):
                meta_df = pd.read_csv(cwc_metadata)
            else:
                meta_df = pd.DataFrame(cwc_metadata)
            res_geom = res_geom.merge(meta_df, on="reservoir_id", how="left")

        Console.info(f"Prepared {len(res_geom)} unique reservoir geometries.")

        # 2. Load Gauge Data
        Console.info("Step 2: Compiling in-situ gauge records...")
        gauge_dfs = []
        if isinstance(gauge_source, (str, Path)) and os.path.isdir(gauge_source):
            for csv_file in glob.glob(os.path.join(gauge_source, "*.csv")):
                rid_str = os.path.splitext(os.path.basename(csv_file))[0]
                if not rid_str.isdigit():
                    continue
                rid = int(rid_str)
                gdf = pd.read_csv(csv_file)
                gdf["reservoir_id"] = rid
                gauge_dfs.append(gdf)
            all_gauge = pd.concat(gauge_dfs, ignore_index=True) if gauge_dfs else pd.DataFrame()
        elif isinstance(gauge_source, (str, Path)) and os.path.isfile(gauge_source):
            all_gauge = pd.read_csv(gauge_source)
        else:
            all_gauge = pd.DataFrame(gauge_source)

        all_gauge["date"] = pd.to_datetime(all_gauge["date"])
        all_gauge["gauge_wse_m"] = pd.to_numeric(all_gauge.get("gauge_wse_m"), errors="coerce")
        all_gauge["gauge_storage_bcm"] = pd.to_numeric(all_gauge.get("gauge_storage_bcm"), errors="coerce")

        if fix_anomalies:
            # Fix Manikdoh 10x decimal typo (ID 88)
            all_gauge.loc[(all_gauge["reservoir_id"] == 88) & (all_gauge["gauge_wse_m"] > 1000), "gauge_wse_m"] /= 10.0
            # Fix Rihand feet-to-meters conversion shift (ID 57)
            all_gauge.loc[(all_gauge["reservoir_id"] == 57) & (all_gauge["gauge_wse_m"] < 200), "gauge_wse_m"] /= 0.3048

        all_gauge = all_gauge.sort_values(["reservoir_id", "date"]).reset_index(drop=True)
        Console.info(f"Loaded {len(all_gauge):,} gauge observations.")

        # 3. Load SWOT Observations & Temporal Match
        Console.info("Step 3: Loading SWOT satellite observations & matching with gauge data...")
        if isinstance(swot_observations, (str, Path)):
            con = sqlite3.connect(swot_observations)
            try:
                swot_obs = pd.read_sql_query("SELECT * FROM observations", con)
            except Exception:
                tbls = [t[0] for t in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
                swot_obs = pd.read_sql_query(f"SELECT * FROM {tbls[0]}", con)
            con.close()
        else:
            swot_obs = pd.DataFrame(swot_observations)

        swot_obs["time_utc"] = pd.to_datetime(swot_obs["time_utc"])

        if fix_anomalies:
            swot_obs.loc[(swot_obs["reservoir_id"] == 88) & (swot_obs.get("gauge_wse_m", 0) > 1000), "gauge_wse_m"] = 706.54

        # Perform nearest-date merge_asof within tolerance
        matched_rows = []
        gauge_by_res = {rid: grp.sort_values("date") for rid, grp in all_gauge.groupby("reservoir_id")}

        for rid, grp in swot_obs.groupby("reservoir_id"):
            g_data = gauge_by_res.get(rid)
            if g_data is None or g_data.empty:
                matched_rows.append(grp)
                continue

            grp = grp.copy()
            g_valid = g_data.dropna(subset=["gauge_wse_m", "gauge_storage_bcm"], how="all").copy()
            if g_valid.empty:
                matched_rows.append(grp)
                continue

            g_valid["gauge_datetime"] = g_valid["date"] + pd.Timedelta(hours=12)
            grp_sorted = grp.sort_values("time_utc")
            g_sorted = g_valid.sort_values("gauge_datetime")[["gauge_datetime", "gauge_wse_m", "gauge_storage_bcm"]]

            merged = pd.merge_asof(
                grp_sorted,
                g_sorted,
                left_on="time_utc",
                right_on="gauge_datetime",
                direction="nearest",
                tolerance=pd.Timedelta(days=tolerance_days),
                suffixes=("", "_new"),
            )

            if "gauge_wse_m_new" in merged.columns:
                has_new = merged["gauge_wse_m_new"].notna()
                merged.loc[has_new, "gauge_wse_m"] = merged.loc[has_new, "gauge_wse_m_new"]
                merged.drop(columns=["gauge_wse_m_new"], inplace=True)
            if "gauge_storage_bcm_new" in merged.columns:
                has_new = merged["gauge_storage_bcm_new"].notna()
                merged.loc[has_new, "gauge_storage_bcm"] = merged.loc[has_new, "gauge_storage_bcm_new"]
                merged.drop(columns=["gauge_storage_bcm_new"], inplace=True)

            has_match = merged["gauge_datetime"].notna()
            merged["gauge_time"] = np.where(
                has_match,
                merged["gauge_datetime"].dt.strftime("%Y-%m-%d %H:%M:%S"),
                merged.get("gauge_time", None),
            )
            merged["gauge_dt_h"] = np.where(
                has_match,
                (merged["gauge_datetime"] - merged["time_utc"]).dt.total_seconds() / 3600.0,
                merged.get("gauge_dt_h", np.nan),
            )

            merged.drop(columns=["gauge_datetime"], inplace=True, errors="ignore")
            matched_rows.append(merged)

        all_swot_matched = (
            pd.concat(matched_rows, ignore_index=True)
            .sort_values(["reservoir_id", "time_utc"])
            .reset_index(drop=True)
        )
        all_swot_matched["time_utc"] = all_swot_matched["time_utc"].dt.strftime("%Y-%m-%d %H:%M:%S")
        n_matched = all_swot_matched["gauge_wse_m"].notna().sum()
        Console.success(f"Matched {n_matched:,} / {len(all_swot_matched):,} SWOT passes with in-situ gauge data.")

        # 4. Build Unified Time Series Table
        Console.info("Step 4: Harmonizing multi-source observation time series...")
        name_map = dict(zip(res_geom["reservoir_id"], res_geom["reservoir_name"]))

        swot_part = pd.DataFrame(
            {
                "reservoir_id": all_swot_matched["reservoir_id"],
                "reservoir_name": all_swot_matched["reservoir_id"].map(name_map),
                "timestamp_utc": all_swot_matched["time_utc"],
                "date": pd.to_datetime(all_swot_matched["time_utc"]).dt.strftime("%Y-%m-%d"),
                "source": "SWOT_SATELLITE",
                "wse_m": all_swot_matched.get("wse_m_q01"),
                "wse_std_m": all_swot_matched.get("wse_std_m"),
                "storage_bcm": all_swot_matched.get("gauge_storage_bcm"),
                "area_km2": all_swot_matched.get("area_km2"),
                "quality_flag": all_swot_matched.get("sparse_flag", 0),
                "swot_cycle": all_swot_matched.get("cycle"),
                "swot_pass": all_swot_matched.get("pass"),
            }
        )

        gauge_part = pd.DataFrame(
            {
                "reservoir_id": all_gauge["reservoir_id"],
                "reservoir_name": all_gauge["reservoir_id"].map(name_map),
                "timestamp_utc": all_gauge["date"].dt.strftime("%Y-%m-%d 12:00:00"),
                "date": all_gauge["date"].dt.strftime("%Y-%m-%d"),
                "source": "IN_SITU_GAUGE",
                "wse_m": all_gauge.get("gauge_wse_m"),
                "wse_std_m": None,
                "storage_bcm": all_gauge.get("gauge_storage_bcm"),
                "area_km2": None,
                "quality_flag": 0,
                "swot_cycle": None,
                "swot_pass": None,
            }
        )

        unified_ts = pd.concat([swot_part, gauge_part], ignore_index=True)
        unified_ts = unified_ts.sort_values(["reservoir_id", "timestamp_utc"]).reset_index(drop=True)
        Console.success(f"Unified time series assembled: {len(unified_ts):,} total records.")

        # 5. Export Deliverables
        out_summary = {
            "n_reservoirs": len(res_geom),
            "n_swot_observations": len(all_swot_matched),
            "n_swot_matched": int(n_matched),
            "n_gauge_observations": len(all_gauge),
            "n_unified_records": len(unified_ts),
        }

        # SQLite Export
        if output_sqlite:
            import sqlite3
            s_path = Path(output_sqlite)
            s_path.parent.mkdir(parents=True, exist_ok=True)
            if s_path.exists():
                s_path.unlink()
            with sqlite3.connect(s_path) as con:
                res_non_geom = pd.DataFrame(res_geom.drop(columns=["geometry"], errors="ignore"))
                res_non_geom.to_sql("reservoirs", con, index=False, if_exists="replace")
                all_swot_matched.to_sql("swot_observations", con, index=False, if_exists="replace")
                all_gauge.assign(date=all_gauge["date"].dt.strftime("%Y-%m-%d")).to_sql(
                    "gauge_timeseries", con, index=False, if_exists="replace"
                )
                unified_ts.to_sql("unified_timeseries", con, index=False, if_exists="replace")

                con.execute("CREATE INDEX ix_res_id ON reservoirs(reservoir_id);")
                con.execute("CREATE INDEX ix_swot_res_date ON swot_observations(reservoir_id, time_utc);")
                con.execute("CREATE INDEX ix_gauge_res_date ON gauge_timeseries(reservoir_id, date);")
                con.execute("CREATE INDEX ix_unified_res_time ON unified_timeseries(reservoir_id, timestamp_utc);")
            Console.info(f"Saved SQLite DB -> {s_path} ({s_path.stat().st_size / 1e6:.1f} MB)")
            out_summary["sqlite_path"] = str(s_path)

        # GeoPackage Export
        if output_gpkg:
            g_path = Path(output_gpkg)
            g_path.parent.mkdir(parents=True, exist_ok=True)
            if g_path.exists():
                g_path.unlink()

            res_gdf = gpd.GeoDataFrame(res_geom, geometry="geometry", crs="EPSG:4326")
            res_gdf.to_file(g_path, layer="reservoirs", driver="GPKG")

            with sqlite3.connect(g_path) as con:
                all_swot_matched.to_sql("swot_observations", con, index=False, if_exists="replace")
                all_gauge.assign(date=all_gauge["date"].dt.strftime("%Y-%m-%d")).to_sql(
                    "gauge_timeseries", con, index=False, if_exists="replace"
                )
                unified_ts.to_sql("unified_timeseries", con, index=False, if_exists="replace")
            Console.info(f"Saved GeoPackage -> {g_path} ({g_path.stat().st_size / 1e6:.1f} MB)")
            out_summary["gpkg_path"] = str(g_path)

        # Parquet Export
        if output_parquet:
            p_path = Path(output_parquet)
            p_path.parent.mkdir(parents=True, exist_ok=True)
            unified_ts.to_parquet(p_path, index=False, compression="snappy")
            Console.info(f"Saved Parquet -> {p_path} ({p_path.stat().st_size / 1e6:.1f} MB)")
            out_summary["parquet_path"] = str(p_path)

        Console.success("Unified reservoir database build successfully completed!")
        return out_summary


build_reservoir_database = UnifiedReservoirBuilder.build_database


def swot_reservoir_merge(
    reservoir_shp,
    swot_observations,
    gauge_source,
    output_gpkg="output/cwc_rsms/unified_reservoir_swot_gauge.gpkg",
    output_sqlite="output/cwc_rsms/unified_reservoir_swot_gauge.sqlite",
    output_parquet="output/cwc_rsms/unified_reservoir_swot_gauge.parquet",
    **kwargs,
):
    """Convenience wrapper for UnifiedReservoirBuilder.build_database."""
    return UnifiedReservoirBuilder.build_database(
        reservoir_shp=reservoir_shp,
        swot_observations=swot_observations,
        gauge_source=gauge_source,
        output_gpkg=output_gpkg,
        output_sqlite=output_sqlite,
        output_parquet=output_parquet,
        **kwargs,
    )
