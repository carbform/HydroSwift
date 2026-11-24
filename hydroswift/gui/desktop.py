"""Desktop helpers for HydroSwift native OS interactions (e.g. folder selection dialog)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


class DesktopError(RuntimeError):
    """The folder dialog could not be opened."""


def choose_folder(start: str | Path = ".", title: str = "Select Download Folder") -> Optional[str]:
    """Open native operating system folder selection dialog.
    
    Tries Zenity first on Linux desktops, falls back to Tkinter in a standalone subprocess,
    and returns None if canceled or running in a headless environment.
    """
    start = Path(start).expanduser()
    initial = str(start.resolve() if start.is_dir() else (start.parent.resolve() if start.parent.is_dir() else Path.cwd()))

    # 1. Zenity on Linux with active display
    if sys.platform.startswith("linux") and shutil.which("zenity") and (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        try:
            cmd = ["zenity", "--file-selection", "--directory", f"--title={title}", f"--filename={initial}/"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if res.returncode == 0:
                chosen = res.stdout.strip()
                if chosen and Path(chosen).is_dir():
                    return chosen
            elif res.returncode == 1:
                # User pressed cancel
                return None
        except Exception:
            pass

    # 2. Tkinter in standalone subprocess
    tk_dialog = (
        "import sys, tkinter as tk\n"
        "from tkinter import filedialog\n"
        "try:\n"
        "    root = tk.Tk()\n"
        "    root.withdraw()\n"
        "    root.attributes('-topmost', True)\n"
        "    chosen = filedialog.askdirectory(initialdir=sys.argv[1], title=sys.argv[2], mustexist=True) or ''\n"
        "    print(chosen.strip())\n"
        "except Exception:\n"
        "    pass\n"
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-c", tk_dialog, initial, title],
            capture_output=True,
            text=True,
            timeout=120,
        )
        out = proc.stdout.strip()
        if out and Path(out).is_dir():
            return out
    except Exception:
        pass

    return None
