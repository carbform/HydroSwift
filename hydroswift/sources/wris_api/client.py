"""Client for the official India-WRIS OpenAPI 3.0 REST API catalog."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import urllib3
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)


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


class WrisClient:
    """REST client for India-WRIS API catalog."""

    BASE_URL = "https://indiawris.gov.in"

    def __init__(self, base_url: str = BASE_URL, verify: bool = False, timeout: int = 25):
        self.base_url = base_url.rstrip("/")
        self.verify = verify
        self.timeout = timeout
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
    ) -> List[Dict[str, Any]]:
        """Fetch observations via Administrative hierarchy (State / District)."""
        ep = normalize_wris_variable(variable) or variable
        url = f"{self.base_url}/Dataset/{ep}"
        params = {
            "stateName": state_name,
            "districtName": district_name,
            "agencyName": agency_name,
            "startdate": start_date,
            "enddate": end_date,
            "download": "false",
            "page": page,
            "size": min(size, 1000),
        }
        try:
            r = self.session.post(url, params=params, timeout=self.timeout)
            if r.status_code == 200:
                data = r.json()
                return data.get("data", []) or []
            logger.warning("WRIS admin request returned status %s: %s", r.status_code, r.text[:200])
        except Exception as e:
            logger.error("WRIS admin request error: %s", e)
        return []

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
    ) -> List[Dict[str, Any]]:
        """Fetch observations via Basin hierarchy (Major Basin / Tributary)."""
        ep = normalize_wris_variable(variable) or variable
        url = f"{self.base_url}/Dataset/Basin/{ep}"
        params = {
            "basinName": basin_name,
            "tributaryName": tributary_name,
            "agencyName": agency_name,
            "startdate": start_date,
            "enddate": end_date,
            "download": "false",
            "page": page,
            "size": min(size, 1000),
        }
        try:
            r = self.session.post(url, params=params, timeout=self.timeout)
            if r.status_code == 200:
                data = r.json()
                return data.get("data", []) or []
            logger.warning("WRIS basin request returned status %s: %s", r.status_code, r.text[:200])
        except Exception as e:
            logger.error("WRIS basin request error: %s", e)
        return []
