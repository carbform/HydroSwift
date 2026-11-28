"""Official India-WRIS OpenAPI 3.0 REST API catalog source adapter."""

from .client import WrisClient, WrisError, VARIABLE_ENDPOINTS, normalize_wris_variable

__all__ = ["WrisClient", "WrisError", "VARIABLE_ENDPOINTS", "normalize_wris_variable"]
