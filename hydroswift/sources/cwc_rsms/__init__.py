"""CWC RSMS (Reservoir Storage Monitoring System) data source adapter."""

from .client import (
    CwcRsmsClient,
    clean_reservoir_name,
    encrypt_payload,
    decrypt_payload,
)
from hydroswift.experimental.swot import UnifiedReservoirBuilder, swot_reservoir_merge

ReservoirBulletinDownloader = CwcRsmsClient
ReservoirBulletinParser = CwcRsmsClient

__all__ = [
    "CwcRsmsClient",
    "ReservoirBulletinDownloader",
    "ReservoirBulletinParser",
    "UnifiedReservoirBuilder",
    "swot_reservoir_merge",
    "clean_reservoir_name",
    "encrypt_payload",
    "decrypt_payload",
]
