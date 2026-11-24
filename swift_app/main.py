"""Console entry point: ``hyswift`` / ``python -m hydroswift``."""

from __future__ import annotations


def main(argv=None) -> int:
    from .cli import main as _main
    return _main(argv)
