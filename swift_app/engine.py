"""Backward compatibility forwarding to hydroswift.core.engine."""

from hydroswift.core.engine import *
from hydroswift.core.engine import (
    _now,
    _slug,
    _nwdp_time_span,
    _iso,
    _has_rc,
    _overlaps,
    parse_name_period,
    NwdpAdapter,
    CwcAdapter,
    RsmsAdapter,
    WrisAdapter,
)
