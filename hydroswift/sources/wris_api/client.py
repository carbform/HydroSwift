"""Client for the official India-WRIS OpenAPI 3.0 REST API catalog."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
import urllib3
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


VARIABLE_ENDPOINTS: Dict[str, str] = {
    "rainfall": "RainFall",
    "water_level": "River Water Level",
    "river_water_level": "River Water Level",
    "discharge": "River Water Discharge",
    "river_discharge": "River Water Discharge",
    "groundwater_level": "Ground Water Level",
    "groundwater": "Ground Water Level",
    "reservoir": "Reservoir",
    "reservoir_level": "Reservoir",
    "reservoir_storage": "Reservoir",
    "temperature": "Temperature",
    "humidity": "Relative Humidity",
    "relative_humidity": "Relative Humidity",
    "wind_direction": "Wind Direction",
    "wind_speed": "Wind Direction",
    "solar_radiation": "Solar Radiation",
    "solar": "Solar Radiation",
    "atm_pressure": "Atmospheric Pressure",
    "soil_moisture": "Soil Moisture",
    "evapotranspiration": "Evapo Transpiration",
    "evaporation": "Evapo Transpiration",
    "sediment": "Suspended Sediment ",
    "snowfall": "SnowFall",
}


def normalize_wris_variable(var_name: Optional[str]) -> Optional[str]:
    """Resolve user query string to official WRIS API endpoint dataset name."""
    if not var_name:
        return None
    cleaned = str(var_name).strip().lower().replace("-", "_").replace(" ", "_")
    if cleaned in VARIABLE_ENDPOINTS:
        return VARIABLE_ENDPOINTS[cleaned]
    for key, endpoint in VARIABLE_ENDPOINTS.items():
        if key in cleaned:
            return endpoint
    return None


class WrisError(RuntimeError):
    """The India-WRIS API could not be queried (distinct from "no data")."""


class WrisClient:
    """REST client for India-WRIS API catalog."""

    BASE_URL = "https://indiawris.gov.in"
    PAGE_SIZE = 1000   # server maximum
    MAX_PAGES = 500    # safety stop; reported as incomplete, never silent
    ATTEMPTS = 3       # per page; long date ranges need many pages and some time out

    def __init__(self, base_url: str = BASE_URL, verify: bool = False, timeout: int = 25):
        self.base_url = base_url.rstrip("/")
        self.verify = verify
        self.timeout = timeout
        self.last_fetch: Dict[str, Any] = {"complete": True, "error": None}
        self.session = requests.Session()
        self.session.verify = verify
        self.session.headers.update({
            "User-Agent": "HydroSwift/1.0",
            "Accept": "application/json",
        })

    def fetch_admin(
        self,
        variable: str,
        state_name: str,
        district_name: str,
        start_date: str,
        end_date: str,
        agency_name: str = "CWC",
        page: int = 0,
        size: int = 1000,
        cancel: Any = None,
        progress: Any = None,
    ) -> List[Dict[str, Any]]:
        """Fetch all observations via Administrative hierarchy (State / District).

        Follows every page. Returns [] when the server reports no data and
        raises :class:`WrisError` when the request fails.
        """
        ep = normalize_wris_variable(variable) or variable
        params = {
            "stateName": state_name,
            "districtName": district_name,
            "agencyName": agency_name,
            "startdate": start_date,
            "enddate": end_date,
            "download": "false",
        }
        return self._post_all(f"{self.base_url}/Dataset/{ep}", params, page, size, cancel, progress)

    def fetch_basin(
        self,
        variable: str,
        basin_name: str,
        tributary_name: str,
        start_date: str,
        end_date: str,
        agency_name: str = "CWC",
        page: int = 0,
        size: int = 1000,
        cancel: Any = None,
        progress: Any = None,
    ) -> List[Dict[str, Any]]:
        """Fetch all observations via Basin hierarchy (Major Basin / Tributary).

        Same paging and error behaviour as :meth:`fetch_admin`.
        """
        ep = normalize_wris_variable(variable) or variable
        params = {
            "basinName": basin_name,
            "tributaryName": tributary_name,
            "agencyName": agency_name,
            "startdate": start_date,
            "enddate": end_date,
            "download": "false",
        }
        return self._post_all(f"{self.base_url}/Dataset/Basin/{ep}", params, page, size, cancel, progress)

    def _post_page(self, url: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        try:
            r = self.session.post(url, params=params, timeout=self.timeout)
            if r.status_code != 200:
                raise WrisError(f"WRIS returned HTTP {r.status_code}: {r.text[:200]}")
            body = r.json()
        except WrisError:
            raise
        except Exception as e:
            raise WrisError(f"WRIS request failed: {e}") from e
        data = body.get("data") or []
        code = body.get("statusCode", 200)
        message = str(body.get("message") or "")
        # the server answers an empty result with statusCode 500 "No data found ..."
        if not data and code != 200 and "no data" not in message.lower():
            raise WrisError(f"WRIS error {code}: {message}")
        return data

    def _retry_page(self, url, params):
        for attempt in range(1, self.ATTEMPTS + 1):
            try:
                return self._post_page(url, params)
            except WrisError:
                if attempt == self.ATTEMPTS:
                    raise
                time.sleep(attempt)

    def _post_all(self, url, params, page, size, cancel, progress=None) -> List[Dict[str, Any]]:
        size = min(size, self.PAGE_SIZE)
        self.last_fetch = {"complete": True, "error": None}
        records: List[Dict[str, Any]] = []
        previous = None
        for number in range(page, page + self.MAX_PAGES):
            if cancel is not None and cancel.is_set():
                self.last_fetch = {"complete": False, "error": "cancelled", "cancelled": True}
                return records
            try:
                batch = self._retry_page(url, {**params, "page": number, "size": size})
            except WrisError as e:
                if not records:
                    raise
                self.last_fetch = {"complete": False, "error": f"truncated at page {number}: {e}"}
                return records
            if batch and batch == previous:
                self.last_fetch = {"complete": False, "error": "server repeated a page; listing may be truncated"}
                return records
            records.extend(batch)
            if progress is not None and batch:
                progress(len(records), None)
            if len(batch) < size:
                return records
            previous = batch
        self.last_fetch = {"complete": False, "error": f"stopped after {self.MAX_PAGES} pages"}
        return records
