import sys
from pathlib import Path

# Ensure project root is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_import_package():
    """Test that the main package imports correctly."""
    import swift_app
    assert swift_app is not None


def test_cli_parser():
    """Test CLI parser builds successfully."""
    from swift_app.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["-b", "krishna", "-q"])

    assert args.basin == "krishna"
    assert args.q is True


def test_dataset_mapping():
    """Ensure dataset mapping exists."""
    from swift_app.cli import DATASETS

    assert "q" in DATASETS
    assert "rf" in DATASETS

def test_cli_parser_long_variable_aliases():
    """Long WRIS variable flags should map to existing short destinations."""
    from swift_app.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["-b", "krishna", "--discharge", "--rainfall"])

    assert args.q is True
    assert args.rf is True


def test_cli_parser_cwc_station_and_basin_aliases():
    """CWC station/basin aliases should parse to runtime fields used by downloader."""
    from swift_app.cli import build_parser

    parser = build_parser()
    args = parser.parse_args([
        "--station", "040-CDJAPR", "032-LGDHYD",
        "--cwc-basin", "Krishna", "Godavari",
    ])

    assert args.cwc_station == ["040-CDJAPR", "032-LGDHYD"]
    assert args.cwc_basin_filter == ["Krishna", "Godavari"]


def test_main_dispatches_cwc_when_only_cwc_basin_is_provided(monkeypatch):
    import swift_app.main as main_mod
    import importlib
    cwc_mod = importlib.import_module("swift_app.cwc")

    called = {}

    def fake_run_cwc_download(args):
        called["basins"] = args.cwc_basin_filter
        return 0

    monkeypatch.setattr(cwc_mod, "run_cwc_download", fake_run_cwc_download)
    monkeypatch.setattr(main_mod, "__name__", "swift_app.main")
    monkeypatch.setattr("sys.argv", ["swift", "--cwc-basin", "Krishna", "--quiet"])

    rc = main_mod.main()

    assert rc == 0
    assert called["basins"] == ["Krishna"]


def test_cli_parser_plot_quality_flags():
    """Plot quality flags should parse and expose expected fields."""
    from swift_app.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["--plot-only", "--input-dir", "output", "--plot-svg", "--plot-moving-average-window", "30"])

    assert args.plot_svg is True
    assert args.plot_moving_average_window == 30


def test_main_shows_banner_for_help_flag(monkeypatch, capsys):
    import swift_app.main as main_mod

    monkeypatch.setattr("sys.argv", ["hyswift", "--help"])

    try:
        main_mod.main()
    except SystemExit as exc:
        assert exc.code == 0

    out = capsys.readouterr().out
    assert "HYDROSWIFT" in out
    assert "usage:" in out


def test_main_shows_banner_for_version_flag(monkeypatch, capsys):
    import swift_app.main as main_mod

    monkeypatch.setattr("sys.argv", ["hyswift", "--version"])

    try:
        main_mod.main()
    except SystemExit as exc:
        assert exc.code == 0

    out = capsys.readouterr().out
    assert "HYDROSWIFT" in out
    assert "HydroSwift" in out


def test_main_shows_banner_for_empty_invocation(monkeypatch, capsys):
    import swift_app.main as main_mod

    monkeypatch.setattr("sys.argv", ["hyswift"])

    rc = main_mod.main()

    assert rc == 0
    out = capsys.readouterr().out
    assert "HYDROSWIFT" in out
    assert "usage:" in out


def test_main_shows_banner_for_cite_flag(monkeypatch, capsys):
    import swift_app.main as main_mod

    monkeypatch.setattr("sys.argv", ["hyswift", "--cite"])

    rc = main_mod.main()

    assert rc == 0
    out = capsys.readouterr().out
    assert "HYDROSWIFT" in out
    assert "If you use HydroSwift in your research" in out
