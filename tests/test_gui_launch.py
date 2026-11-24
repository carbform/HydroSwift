"""Unit tests for the modern HydroSwift GUI launcher."""
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from hydroswift.gui import app
from hydroswift.cli import build_parser, main as cli_main


def test_gui_script_exists():
    web_script = Path(app.__file__).parent / "web.py"
    assert web_script.exists()
    assert web_script.is_file()


def test_gui_app_main_invokes_streamlit(monkeypatch):
    mock_stcli = MagicMock()
    mock_stcli.main.return_value = 0
    monkeypatch.setattr("streamlit.web.cli.main", mock_stcli.main)

    with patch("sys.exit") as mock_exit:
        app.run_web()
        mock_exit.assert_called_once()


def test_cli_gui_command_routes_to_run_web(monkeypatch):
    called = []
    def fake_run_web():
        called.append(True)

    monkeypatch.setattr("hydroswift.gui.app.run_web", fake_run_web)
    p = build_parser()
    args = p.parse_args(["gui"])
    assert args.command == "gui"
    ret = cli_main(["gui"])
    assert ret == 0
    assert len(called) == 1
