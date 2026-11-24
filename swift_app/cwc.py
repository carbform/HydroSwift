"""Backward compatibility forwarding to hydroswift.sources.cwc_ffs.client."""

import sys
import hydroswift.sources.cwc_ffs.client as _impl

# Forward everything and replace sys.modules so monkeypatching hits the authoritative implementation
sys.modules[__name__] = _impl
