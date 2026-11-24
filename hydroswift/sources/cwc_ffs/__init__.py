"""CWC Flood Forecasting System (FFS) data source adapter."""

from .client import (
    load_station_table,
    download_station_detail,
    download_station,
    fetch_cwc_station_metadata,
    repopulate_cwc_metadata_from_name_code,
    _rc_discharge_value,
    _get_rc_row,
)

load_station_metadata = load_station_table
refresh_packaged_station_metadata = repopulate_cwc_metadata_from_name_code
calculate_discharge_from_stage = _rc_discharge_value

__all__ = [
    "load_station_table",
    "load_station_metadata",
    "download_station_detail",
    "download_station",
    "fetch_cwc_station_metadata",
    "refresh_packaged_station_metadata",
    "calculate_discharge_from_stage",
    "_get_rc_row",
]
