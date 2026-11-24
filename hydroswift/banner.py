"""Banner output for HydroSwift CLI."""

from __future__ import annotations

import importlib

from . import APP_NAME, APP_ORG, APP_TAGLINE, VERSION_FULL

BORDER = "=" * 68
BANNER_LINES = [
    "██╗  ██╗██╗   ██╗██████╗ ██████╗  ██████╗ ███████╗██╗    ██╗██╗███████╗████████╗",
    "██║  ██║╚██╗ ██╔╝██╔══██╗██╔══██╗██╔═══██╗██╔════╝██║    ██║██║██╔════╝╚══██╔══╝",
    "███████║ ╚████╔╝ ██║  ██║██████╔╝██║   ██║███████╗██║ █╗ ██║██║█████╗     ██║   ",
    "██╔══██║  ╚██╔╝  ██║  ██║██╔══██╗██║   ██║╚════██║██║███╗██║██║██╔══╝     ██║   ",
    "██║  ██║   ██║   ██████╔╝██║  ██║╚██████╔╝███████║╚███╔███╔╝██║██║        ██║   ",
    "╚═╝  ╚═╝   ╚═╝   ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝ ╚══╝╚══╝ ╚═╝╚═╝        ╚═╝   ",
]
GRADIENT_HEX = ["#36cfff", "#27b8ff", "#1f9eff", "#8b5cf6", "#d946ef", "#f59e0b"]
GRADIENT_ANSI = [51, 45, 39, 99, 201, 220]
RESET = "[0m"
BOLD = "[1m"


def _plain_gradient_line(line: str, color_code: int) -> str:
    return f"[38;5;{color_code}m{line}{RESET}"


def _plain_banner() -> str:
    lines = [
        f"{BOLD}{BORDER}{RESET}",
        _plain_gradient_line(f"{APP_NAME.upper()} ⚡", GRADIENT_ANSI[0]),
        _plain_gradient_line(APP_TAGLINE, GRADIENT_ANSI[1]),
        _plain_gradient_line(APP_ORG, GRADIENT_ANSI[3]),
        f"Version: {VERSION_FULL}",
        "",
    ]
    lines.extend(_plain_gradient_line(line, color) for line, color in zip(BANNER_LINES, GRADIENT_ANSI))
    lines.append("")
    lines.append(f"{BOLD}{BORDER}{RESET}")
    return "\n".join(lines)


def print_wish_banner() -> None:
    """Render a HydroSWIFT startup banner with gradient styling when possible."""
    try:
        Console = importlib.import_module("rich.console").Console
        Text = importlib.import_module("rich.text").Text

        console = Console()
        console.print(f"[bold]{BORDER}[/bold]")

        title = Text(f"{APP_NAME.upper()} ⚡", style=f"bold {GRADIENT_HEX[0]}")
        tagline = Text(APP_TAGLINE, style=f"bold {GRADIENT_HEX[1]}")
        org = Text(APP_ORG, style=f"bold {GRADIENT_HEX[3]}")
        version = Text(f"Version: {VERSION_FULL}", style="bold white")

        console.print(title)
        console.print(tagline)
        console.print(org)
        console.print(version)
        console.print()

        for line, color in zip(BANNER_LINES, GRADIENT_HEX):
            console.print(Text(line, style=f"bold {color}"))

        console.print(f"[bold]{BORDER}[/bold]")
    except ImportError:
        print(_plain_banner())
