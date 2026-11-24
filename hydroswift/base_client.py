"""Base classes for hydrological data clients to ensure a standardized interface."""

from abc import ABC, abstractmethod

class BaseHydrologyClient(ABC):
    """
    Abstract Base Class defining the expected interface for 
    any data source integrated into SWIFT.
    
    By adhering to this base class, future modules (e.g., for state-level portals 
    or international databases) can be seamlessly integrated into the SWIFT CLI 
    and unified public Python API.
    """

    @abstractmethod
    def check_api(self) -> bool:
        """Ping the service or check endpoint availability."""
        pass

    @abstractmethod
    def get_stations(self, *args, **kwargs) -> list[dict]:
        """Discover and return a list of available observation stations."""
        pass

    @abstractmethod
    def get_timeseries(self, station_code: str, dataset_code: str, start_date: str, end_date: str):
        """Fetch the timeseries data for a given station and dataset as a DataFrame."""
        pass
