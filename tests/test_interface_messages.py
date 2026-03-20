from types import SimpleNamespace

from swift_app.utils import coffee_tip, overwrite_tip


def test_overwrite_tip_uses_cli_wording_for_cli_interface():
    args = SimpleNamespace(interface="cli")
    assert overwrite_tip(args) == "Tip: re-run with --overwrite to refresh data."


def test_overwrite_tip_uses_python_wording_for_python_interface():
    args = SimpleNamespace(interface="python")
    assert overwrite_tip(args) == "Tip: call with overwrite=True to refresh data."


def test_coffee_tip_uses_cli_wording_for_cli_interface():
    args = SimpleNamespace(interface="cli")
    assert coffee_tip(args) == "Tip: enable --coffee mode for long runs ☕"


def test_coffee_tip_uses_python_wording_for_python_interface():
    args = SimpleNamespace(interface="python")
    assert coffee_tip(args) == "Tip: call hydroswift.coffee() before a long run ☕"
