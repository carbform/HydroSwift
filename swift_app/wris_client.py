"""WRIS API client used by SWIFT."""

from __future__ import annotations

import ssl
import time

import requests
import urllib3


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


BASE = "https://indiawris.gov.in"

TRIB_API = BASE + "/masterTributary/getMasterTributary"
RIVER_API = BASE + "/masterRiver/getMasterRiverData"
AGENCY_API = BASE + "/masterAgency/AgencyListInAnyCase"
STATION_API = BASE + "/masterStationDS/stationDSList"
META_API = BASE + "/stationMaster/getMasterStationsList"
TS_API = BASE + "/CommonDataSetMasterAPI/getCommonDataSetByStationCode"
BASIN_API = BASE + "/basin/getMasterBasin"

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://indiawris.gov.in",
    "Referer": "https://indiawris.gov.in/wris/",
    "User-Agent": "Mozilla/5.0",
}


from .base_client import BaseHydrologyClient

class WrisClient(BaseHydrologyClient):
    """Thin API client for WRIS browser endpoints."""

    def __init__(self, delay: float = 0.25):
        self.delay = delay
        self.session = requests.Session()
        # WRIS uses a broken SSL chain, so we disabled verification; also 
        # when using a proxy or VPN, 
        # the cert may not be valid for the client system.
        self.session.verify = False
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "connection": "keep-alive"
        })
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=20,
            pool_maxsize=20,
        )

        self.session.mount("https://", adapter)

    def post(self, url: str, payload: dict, retries: int = 3):
        """POST helper with retry and better diagnostics."""
        for attempt in range(retries):
            try:
                response = self.session.post(
                    url,
                    json=payload,
                    headers=HEADERS,
                    timeout=60,
                    verify=False,
                )

                if response.status_code == 200:
                    data = response.json()
                    time.sleep(self.delay)
                    return data

                else:
                    print("WRIS API returned:", response.status_code)
                    print(response.text[:300])

            except Exception as e:
                # Keep retry messaging user-friendly for transient WRIS/API issues.
                if attempt < retries - 1:
                    print(
                        "WRIS API is busy right now... hang on, retrying "
                        f"({attempt + 1}/{retries})"
                    )
                else:
                    print("WRIS API request failed after retries.")

            time.sleep(2)

        return None

    def check_api(self) -> bool:


        try:
            response = self.session.post(
                BASIN_API,
                json={"datasetcode": "DISCHARG"},
                headers=HEADERS,
                timeout=10,
                verify=False,
            )

            if response.status_code == 200:
                return True

        except Exception:
            pass

        print("\nERROR: Unable to reach WRIS API.")
        print("WRIS may be down or your system is not connected to the internet.")
        return False

    def get_basin_code(self, basin_name: str) -> str:
        """Resolve basin name to basin code."""
        response = self.post(BASIN_API, {"datasetcode": "DISCHARG"})
        if not response or "data" not in response:
            raise RuntimeError("Failed to fetch basin list from WRIS")

        for item in response["data"]:
            if item.get("basin", "").lower() == basin_name.lower():
                return item["basincode"]

        raise ValueError(f"Basin not found: {basin_name}")

    def get_tributaries(self, basin_code: str, dataset_code: str) -> list[dict]:
        response = self.post(
            TRIB_API, {"basincode": basin_code, "datasetcode": dataset_code}
        )
        return response.get("data", []) if response else []

    def get_rivers(self, tributary_id: str, dataset_code: str) -> list[dict]:
        response = self.post(
            RIVER_API, {"tributaryid": str(tributary_id), "datasetcode": dataset_code}
        )
        return response.get("data", []) if response else []

    def get_agencies(
        self, tributary_id: str, localriver_id: str, dataset_code: str
    ) -> list[dict]:
        response = self.post(
            AGENCY_API,
            {
                "district_id": 0,
                "datasetcode": dataset_code,
                "localriverid": localriver_id,
                "tributaryid": str(tributary_id),
            },
        )
        return response.get("data", []) if response else []

    def get_stations(
        self, tributary_id: str, localriver_id: str, agency_id: str, dataset_code: str
    ) -> list[dict]:
        stations: list[dict] = []

        telemetric = self.post(
            STATION_API,
            {
                "tributaryid": str(tributary_id),
                "agencyid": str(agency_id),
                "localriverid": localriver_id,
                "datasetcode": dataset_code,
                "telemetric": "true",
            },
        )
        if telemetric and telemetric.get("data"):
            stations.extend(telemetric["data"])

        manual = self.post(
            STATION_API,
            {
                "tributaryid": str(tributary_id),
                "agencyid": str(agency_id),
                "localriverid": localriver_id,
                "datasetcode": dataset_code,
                "telemetric": "false",
            },
        )
        if manual and manual.get("data"):
            stations.extend(manual["data"])

        return stations

    def get_metadata(self, station_code: str, dataset_code: str):
        response = self.post(
            META_API, {"stationcode": station_code, "datasetcode": dataset_code}
        )
        if response and response.get("data"):
            return response["data"][0]
        return None

    def get_timeseries(
        self, station_code: str, dataset_code: str, start_date: str, end_date: str
    ):
        """Fetch station timeseries and normalize column names."""
        import pandas as pd

        for _ in range(3):
            response = self.session.post(
                TS_API,
                json={
                    "station_code": station_code,
                    "starttime": start_date,
                    "endtime": end_date,
                    "dataset": dataset_code,
                },
                headers=HEADERS,
                timeout=60,
                verify=False # Wris may not be having a valid certifciate (if using a proxy or VPN)
            )

            if response.status_code == 200:
                data = response.json().get("data", [])
                if data:
                    frame = pd.DataFrame(data)
                    frame.rename(
                        columns={
                            "dataTime": "time",
                            "dataValue": "value",
                            "datatypeDescription": "type",
                            "unitCode": "unit",
                        },
                        inplace=True,
                    )
                    return frame
            time.sleep(2)

        return None
