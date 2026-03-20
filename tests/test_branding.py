import hydroswift
from swift_app.cli import build_parser


def test_hydroswift_import_alias_exposes_public_api():
    assert hasattr(hydroswift, "wris")
    assert hasattr(hydroswift, "cwc")
    assert hasattr(hydroswift, "fetch")


def test_cli_help_uses_hydroswift_branding():
    parser = build_parser()
    help_text = parser.format_help()
    assert "HydroSwift - Fast, unified workflows for hydrological data" in help_text
    assert parser.prog == "hyswift"


def test_hydroswift_submodule_imports_work():
    import hydroswift.api as api_mod
    import hydroswift.main as main_mod

    assert hasattr(api_mod, "fetch")
    assert callable(main_mod.main)
