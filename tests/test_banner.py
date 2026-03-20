import types

from swift_app.banner import _plain_banner, print_wish_banner


def test_plain_banner_mentions_hydroswift_and_contains_gradient_escape_codes():
    out = _plain_banner()
    assert "HYDROSWIFT" in out
    assert "\033[38;5;" in out


def test_print_wish_banner_falls_back_without_rich(monkeypatch, capsys):
    real_import_module = __import__("importlib").import_module

    def fake_import_module(name, package=None):
        if name.startswith("rich"):
            raise ImportError
        return real_import_module(name, package)

    monkeypatch.setattr("swift_app.banner.importlib.import_module", fake_import_module)

    print_wish_banner()
    captured = capsys.readouterr().out
    assert "HYDROSWIFT" in captured
    assert "\033[38;5;" in captured


def test_print_wish_banner_uses_rich_gradient_title(monkeypatch):
    recorded = []

    class DummyConsole:
        def print(self, value=""):
            recorded.append(value)

    class DummyText:
        def __init__(self, text, style=None):
            self.text = text
            self.style = style

    rich_console = types.SimpleNamespace(Console=DummyConsole)
    rich_text = types.SimpleNamespace(Text=DummyText)

    def fake_import_module(name, package=None):
        if name == "rich.console":
            return rich_console
        if name == "rich.text":
            return rich_text
        raise ImportError(name)

    monkeypatch.setattr("swift_app.banner.importlib.import_module", fake_import_module)

    print_wish_banner()

    title = next(item for item in recorded if isinstance(item, DummyText) and "HYDROSWIFT" in item.text)
    assert title.style == "bold #36cfff"
