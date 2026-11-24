"""Backward compatibility forwarding to hydroswift.sources.nwdp.client."""
import sys
import hydroswift.sources.nwdp.client as _impl

sys.modules[__name__] = _impl
