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
# UNIFIED RESERVOIR DATABASE BUILDER (SWOT + IN-SITU GAUGE) - Experimental
# ──────────────────────────────────────────────────────────────────────
from .experimental.swot import UnifiedReservoirBuilder, swot_reservoir_merge
