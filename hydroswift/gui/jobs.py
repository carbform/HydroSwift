"""A download running in a background thread, so the dashboard can show progress and cancel it.

No Streamlit calls here: the worker thread only updates plain attributes.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Optional

import pandas as pd


class DownloadJob:
    def __init__(self, table: pd.DataFrame, *, fetch: Callable, **fetch_kwargs: Any):
        self.table = table
        self.total = len(table)
        self.done = 0
        self.latest = "Starting…"
        self.pages = {}  # item id -> text, for items still being read
        self.result: Optional[pd.DataFrame] = None
        self.error: Optional[str] = None
        self.started = time.monotonic()
        self._cancel = threading.Event()
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, args=(fetch, fetch_kwargs), daemon=True)

    def start(self) -> "DownloadJob":
        self._thread.start()
        return self

    def _run(self, fetch, kwargs):
        try:
            self.result = fetch(self.table, progress=self._on_event, cancel=self._cancel, **kwargs)
        except Exception as e:  # shown to the user by the dashboard
            self.error = str(e)

    def _on_event(self, event: dict):
        kind, key = event.get("event"), (event.get("source"), event.get("id"))
        title = event.get("title") or event.get("id")
        with self._lock:
            if kind == "page":
                total = event.get("total")
                self.pages[key] = f"{title}: {event.get('read'):,} records read" + (f" of {total:,}" if total else "")
            elif kind == "item_done":
                self.done += 1
                self.pages.pop(key, None)
                self.latest = f"{title}: {event.get('status')}"

    def cancel(self):
        self._cancel.set()

    def join(self, timeout=None):
        self._thread.join(timeout)

    @property
    def cancelling(self) -> bool:
        return self._cancel.is_set()

    @property
    def running(self) -> bool:
        return self._thread.is_alive()

    def snapshot(self) -> dict:
        with self._lock:
            return {"done": self.done, "total": self.total, "latest": self.latest,
                    "pages": list(self.pages.values()), "seconds": int(time.monotonic() - self.started)}
