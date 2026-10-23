"""
cwc_rsms.py — CWC Reservoir Storage Monitoring System (RSMS) & SWOT Integration for HydroSwift.

Integrates:
1. CWC RSMS Cryptographic API client (AES-128-CBC + HMAC-SHA256).
2. Live daily reservoir storage & level snapshot tracker (GeoServer WFS + API).
3. Historical weekly bulletin scraper and PDF table parser (180+ reservoirs).
4. SWOT satellite & in-situ gauge unified database builder (GPKG, SQLite, Parquet).
"""

from __future__ import annotations

import base64
import glob
import hashlib
import hmac
import json
import logging
import os
import re
import ssl
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from .utils import Console

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
# CONSTANTS & CRYPTOGRAPHIC KEYS
# ──────────────────────────────────────────────────────────────────────
RSMS_ADMIN_URL = "https://rsms.cwc.gov.in/admin"
RSMS_WFS_URL = (
    "https://rsms.cwc.gov.in/geoserver/wfs?service=WFS&version=1.0.0"
    "&request=GetFeature&typeName=CWC:reservoir&outputFormat=application/json"
)
RSMS_DETAILS_API = "https://rsms.cwc.gov.in/admin/api/getReservoir-details"
RSMS_SECRET_KEYS_API = "https://rsms.cwc.gov.in/admin/get-secret-keys"

BOOTSTRAP_KEY = bytes.fromhex(
    base64.b64decode("MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=").decode()
)
BOOTSTRAP_IV = base64.b64decode("MTIzNDU2Nzg5MGFiY2RlZg==")
API_HASHING_KEY = "P2@G2#N201684728499"

# SSL Context for RSMS portal endpoints
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# Name aliases for cross-referencing between official bulletins and shapefile IDs
NAME_OVERRIDES = {
    "MACHCHHU1": "MACHCHHU I",
    "MACHCHHU2": "MACHCHHU II",
    "UND-1": "UND I",
    "UND1": "UND I",
    "UJJANI": "BHIMA UJJAINI",
    "BHIMAUJJANI": "BHIMA UJJAINI",
    "HASDEO": "MINIMATA BANGO",
    "VANIVILASA SAGAR": "VANI VILAS",
    "DANTI WADA": "DANTIWADA",
    "UPPER INDRAVATHI": "UPPER INDRAVATI",
    "KOLAB": "UPPER KOLAB",
    "PANSHET DAM (TANAJISAGAR)": "PANSHET",
    "PULICHINTHALA DAM": "PULICHINTALA",
}


def clean_reservoir_name(s: Any) -> str:
    """Normalize reservoir names for robust fuzzy matching."""
    s = str(s).upper()
    s = re.sub(r"\(.*?\)", "", s).strip()
    s = re.sub(r"\bDAM\b", "", s).strip()
    s = re.sub(r"\bSAGAR\b", "", s).strip()
    s = re.sub(r"[^A-Z0-9]", "", s)
    return s


# ──────────────────────────────────────────────────────────────────────
# CRYPTOGRAPHIC UTILITIES (AES-128-CBC + PKCS7)
# ──────────────────────────────────────────────────────────────────────
def encrypt_payload(data_obj: Union[dict, list], key: bytes = BOOTSTRAP_KEY, iv: bytes = BOOTSTRAP_IV) -> str:
    """Encrypt a python object to an AES-128-CBC Base64 payload expected by RSMS."""
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    raw = json.dumps(data_obj).encode("utf-8")
    padder = padding.PKCS7(128).padder()
    padded = padder.update(raw) + padder.finalize()

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(encrypted).decode("utf-8")


def decrypt_payload(b64_str: str, key: bytes = BOOTSTRAP_KEY, iv: bytes = BOOTSTRAP_IV) -> Any:
    """Decrypt an AES-128-CBC Base64 payload from RSMS."""
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    encrypted = base64.b64decode(b64_str)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(encrypted) + decryptor.finalize()

    unpadder = padding.PKCS7(128).unpadder()
    unpadded = unpadder.update(padded) + unpadder.finalize()
    res = json.loads(unpadded.decode("utf-8"))
    if isinstance(res, str):
        try:
            res = json.loads(res)
        except Exception:
            pass
    return res


# ──────────────────────────────────────────────────────────────────────
# CWC RSMS CLIENT
# ──────────────────────────────────────────────────────────────────────
class CwcRsmsClient:
    """Client for Central Water Commission Reservoir Storage Monitoring System."""

    def __init__(self, key: bytes = BOOTSTRAP_KEY, iv: bytes = BOOTSTRAP_IV, hmac_key: str = API_HASHING_KEY):
        self.key = key
        self.iv = iv
        self.hmac_key = hmac_key

    def fetch_daily_snapshot(
        self,
        output_path: Optional[Union[str, Path]] = None,
        timeout: int = 15,
        max_reservoirs: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Fetch the latest real-time daily reservoir storage & level snapshot.

        Queries the RSMS GeoServer WFS layer to identify active monitored reservoirs,
        then queries the reservoir details endpoint for real-time live capacity and storage.

        Parameters
        ----------
        output_path : str or Path, optional
            Path to append or write the snapshot CSV.
        timeout : int, default 15
            Request timeout in seconds.
        max_reservoirs : int, optional
            Limit number of reservoirs (useful for testing).

        Returns
        -------
        pd.DataFrame
            DataFrame of reservoir storage and elevation records.
        """
        Console.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Querying RSMS GeoServer WFS...")
        req = urllib.request.Request(RSMS_WFS_URL, headers={"User-Agent": "Mozilla/5.0 HydroSwift"})
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=timeout) as resp:
            wfs_data = json.loads(resp.read().decode())

        features = wfs_data.get("features", [])
        if max_reservoirs:
            features = features[:max_reservoirs]
        Console.info(f"Discovered {len(features)} reservoirs in GeoServer WFS layer.")

        results = []
        headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 HydroSwift"}

        for idx, f in enumerate(features, 1):
            props = f.get("properties", {})
            uid = props.get("reservoir_unique_id")
            name = props.get("reservoir_name")
            if not uid:
                continue

            payload = json.dumps({"reservoir_uid": uid}).encode("utf-8")
            req2 = urllib.request.Request(RSMS_DETAILS_API, data=payload, headers=headers)
            try:
                with urllib.request.urlopen(req2, context=_SSL_CTX, timeout=timeout) as resp2:
                    res = json.loads(resp2.read().decode())
                    items = res.get("result", [])
                    if items:
                        item = items[0]
                        results.append(
                            {
                                "reservoir_unique_id": uid,
                                "reservoir_name": item.get("reservoir_name") or name,
                                "entry_date": item.get("entry_date"),
                                "storage_bcm": float(item.get("storage_bcm", 0.0) or 0.0),
                                "live_cap_bcm": float(item.get("live_cap_bcm", 0.0) or 0.0),
                                "gross_cap_bcm": float(item.get("gross_cap_bcm", 0.0) or 0.0),
                                "cap_dsl_bcm": float(item.get("cap_dsl_bcm", 0.0) or 0.0),
                                "frl_meter": props.get("frl_meter"),
                                "dsl_mtr": props.get("dsl_mtr"),
                                "latitude": props.get("lattitude"),
                                "longitude": props.get("longitude"),
                            }
                        )
            except Exception as e:
                logger.debug("Failed fetching details for %s (%s): %s", uid, name, e)

        df_new = pd.DataFrame(results)
        Console.success(f"Successfully retrieved daily records for {len(df_new)} reservoirs.")

        if output_path:
            out_p = Path(output_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            if out_p.exists():
                try:
                    df_old = pd.read_csv(out_p)
                    combined = pd.concat([df_old, df_new]).drop_duplicates(
                        subset=["reservoir_unique_id", "entry_date"], keep="last"
                    )
                    combined.to_csv(out_p, index=False)
                    Console.info(f"Updated daily snapshot CSV -> {out_p} ({len(combined)} rows)")
                    return combined
                except Exception as e:
                    logger.warning("Error reading existing snapshot CSV: %s", e)
            df_new.to_csv(out_p, index=False)
            Console.info(f"Saved daily snapshot CSV -> {out_p}")

        return df_new

    def fetch_bulletin_catalog(
        self,
        from_date: str = "",
        to_date: str = "",
        pages: Tuple[int, ...] = (1, 2),
        cache_file: Optional[Union[str, Path]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query the RSMS bulletin report API to discover published weekly bulletin PDFs.

        Parameters
        ----------
        from_date : str, default ""
            Optional start date filter (YYYY-MM-DD).
        to_date : str, default ""
            Optional end date filter (YYYY-MM-DD).
        pages : tuple of int, default (1, 2)
            Pages of catalog to fetch.
        cache_file : str or Path, optional
            Path to cache the JSON catalog on disk.

        Returns
        -------
        list of dict
            List of bulletin objects with approval file paths and creation dates.
        """
        if cache_file and os.path.exists(cache_file) and os.path.getsize(cache_file) > 1000:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)

        bulletins = []
        for page in pages:
            for attempt in range(3):
                try:
                    req_data = encrypt_payload(
                        {"vchBulletinName": "", "from_date": from_date, "to_date": to_date},
                        key=self.key,
                        iv=self.iv,
                    )
                    token = hmac.new(
                        self.hmac_key.encode("utf-8"),
                        req_data.encode("utf-8"),
                        hashlib.sha256,
                    ).hexdigest()
                    payload = json.dumps({"REQUEST_DATA": req_data, "REQUEST_TOKEN": token}).encode("utf-8")
                    headers = {
                        "User-Agent": "Mozilla/5.0 HydroSwift",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    }
                    req = urllib.request.Request(
                        f"{RSMS_ADMIN_URL}/bulletin-report-page?page={page}&limit=50",
                        data=payload,
                        headers=headers,
                    )
                    with urllib.request.urlopen(req, context=_SSL_CTX, timeout=30) as resp:
                        res = json.loads(resp.read().decode())
                    dec = decrypt_payload(res["RESPONSE_DATA"], key=self.key, iv=self.iv)
                    items = dec.get("data", {}).get("data", [])
                    bulletins.extend(items)
                    break
                except Exception as e:
                    if attempt == 2:
                        logger.warning("Failed fetching catalog page %d: %s", page, e)
                    time.sleep(2)

        bulletins.sort(key=lambda x: x.get("dtmCreatedOn", ""))
        if cache_file and bulletins:
            Path(cache_file).parent.mkdir(parents=True, exist_ok=True)
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(bulletins, f, indent=2)

        return bulletins

    def download_bulletin_pdf(
        self,
        pdf_filename: str,
        output_dir: Union[str, Path] = "output/cwc/bulletins",
    ) -> Optional[Path]:
        """Download a bulletin PDF if not already present."""
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = out_dir / pdf_filename

        if pdf_path.exists() and pdf_path.stat().st_size > 1000:
            return pdf_path

        url = f"{RSMS_ADMIN_URL}/storage/bulletins/{pdf_filename}"
        cmd = ["curl", "-k", "-s", "-f", url, "-o", str(pdf_path)]
        try:
            res = subprocess.run(cmd, timeout=30)
            if res.returncode == 0 and pdf_path.exists() and pdf_path.stat().st_size > 1000:
                with open(pdf_path, "rb") as f:
                    if f.read(4) == b"%PDF":
                        return pdf_path
        except Exception as e:
            logger.debug("Download failed for %s: %s", pdf_filename, e)

        if pdf_path.exists():
            pdf_path.unlink()
        return None

    def parse_bulletin_pdf(
        self,
        pdf_path: Union[str, Path],
    ) -> List[Dict[str, Any]]:
        """
        Extract tabular reservoir observations from a CWC weekly bulletin PDF.

        Uses `pdftotext -layout` to preserve table columns and regex to parse:
        reservoir_name, frl_m, water_level_m, live_cap_bcm, current_storage_bcm, date.
        """
        p = Path(pdf_path)
        if not p.exists() or p.stat().st_size < 1000:
            return []

        txt_path = p.with_suffix(".txt")
        if not txt_path.exists() or txt_path.stat().st_size < 1000:
            res = subprocess.run(["pdftotext", "-layout", str(p), str(txt_path)], capture_output=True)
            if res.returncode != 0:
                logger.warning("pdftotext failed on %s", p.name)
                return []

        with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

        pages = text.split("\x0c")
        reservoirs = []
        row_re = re.compile(
            r"^\s*(\d+)\s+([A-Za-z0-9\s\.\-\/\(\)&]+?)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d{2}\.\d{2}\.\d{4})"
        )
        cont_re = re.compile(r"^\s{5,}([A-Za-z0-9\s\.\-\/\(\)&]+)\s*$")
        ignore_words = [
            "Region", "Pradesh", "Bengal", "Gujarat", "Maharashtra", "Odisha",
            "Tamil", "Kerala", "Karnataka", "Andhra", "Telangana", "Madhya",
            "Uttar", "Rajasthan", "Punjab", "Jharkhand", "Bihar", "Tripura",
            "Nagaland", "Uttarakhand", "Goa", "Chhattisgarh",
        ]

        for page in pages:
            if "REGION/STATE WISE WEEKLY REPORT" not in page:
                continue
            last_item = None
            for line in page.split("\n"):
                if any(h in line for h in ["SR.", "NO.", "LEVEL (M)", "BCM", "YEAR", "1   2   3"]):
                    continue
                m = row_re.match(line)
                if m:
                    sr, name, frl, level, cap, storage, dt = m.groups()
                    try:
                        dt_obj = datetime.strptime(dt, "%d.%m.%Y").strftime("%Y-%m-%d")
                    except Exception:
                        dt_obj = dt
                    last_item = {
                        "reservoir_name": name.strip(),
                        "frl_m": float(frl),
                        "water_level_m": float(level),
                        "live_cap_bcm": float(cap),
                        "current_storage_bcm": float(storage),
                        "date": dt_obj,
                        "bulletin_file": p.name,
                    }
                    reservoirs.append(last_item)
                elif last_item is not None and cont_re.match(line) and not any(r in line for r in ignore_words):
                    cont_name = cont_re.match(line).group(1).strip()
                    if cont_name not in [
                        "Northern Region", "Eastern Region", "Western Region",
                        "Central Region", "Southern Region"
                    ]:
                        last_item["reservoir_name"] += " " + cont_name
                        last_item = None
                else:
                    last_item = None

        return reservoirs

    def backfill_bulletins(
        self,
        start_date: str = "2025-05-15",
        end_date: Optional[str] = None,
        output_csv: Optional[Union[str, Path]] = None,
        bulletin_dir: Union[str, Path] = "output/cwc/bulletins",
    ) -> pd.DataFrame:
        """
        Download and parse CWC bulletins within a date range into a single tabular time series.

        Parameters
        ----------
        start_date : str, default '2025-05-15'
            Start date (YYYY-MM-DD).
        end_date : str, optional
            End date (YYYY-MM-DD).
        output_csv : str or Path, optional
            Path to write the combined bulletin observations CSV.
        bulletin_dir : str or Path
            Directory to store downloaded bulletin PDFs.

        Returns
        -------
        pd.DataFrame
            DataFrame of all parsed bulletin observations.
        """
        Console.section("CWC RSMS Bulletin Backfill")
        bulletins = self.fetch_bulletin_catalog()
        to_process = [b for b in bulletins if b.get("dtmCreatedOn", "") >= start_date]
        if end_date:
            to_process = [b for b in to_process if b.get("dtmCreatedOn", "") <= end_date]

        Console.info(f"Identified {len(to_process)} bulletin(s) matching date filter.")
        all_rows = []
        for idx, b in enumerate(to_process, 1):
            fname = b.get("vchApprovedFile")
            if not fname:
                continue
            pdf_path = self.download_bulletin_pdf(fname, output_dir=bulletin_dir)
            if pdf_path:
                rows = self.parse_bulletin_pdf(pdf_path)
                if rows:
                    all_rows.extend(rows)

        df = pd.DataFrame(all_rows)
        if not df.empty:
            Console.success(f"Parsed {len(df)} reservoir observations across {df['date'].nunique()} bulletin dates.")
            if output_csv:
                out_p = Path(output_csv)
                out_p.parent.mkdir(parents=True, exist_ok=True)
                df.to_csv(out_p, index=False)
                Console.info(f"Saved bulletin backfill dataset -> {out_p}")
        return df


# ──────────────────────────────────────────────────────────────────────
# UNIFIED RESERVOIR DATABASE BUILDER (SWOT + IN-SITU GAUGE)
# ──────────────────────────────────────────────────────────────────────
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
            import sqlite3
            con = sqlite3.connect(swot_observations)
            # Try observations table, else fallback to reading whole sqlite
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
            import sqlite3
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
