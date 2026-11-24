"""Backward compatibility forwarding to hydroswift.api."""
import sys
import hydroswift.api as _impl

# Forward everything and replace sys.modules so monkeypatching hits the authoritative implementation
sys.modules[__name__] = _impl
