"""Optional filesystem watcher for incremental Corpus synchronization."""

from __future__ import annotations

from pathlib import Path
from threading import Lock, Timer
from typing import Callable


class CorpusWatcher:
    def __init__(self, *, root: Path, sync_callback: Callable[[], object], debounce_seconds: float = 2.0) -> None:
        self.root = root
        self.sync_callback = sync_callback
        self.debounce_seconds = debounce_seconds
        self._observer = None
        self._timer: Timer | None = None
        self._lock = Lock()

    def start(self) -> None:
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"watchdog is unavailable: {exc}") from exc

        watcher = self

        class Handler(FileSystemEventHandler):
            def on_any_event(self, event):  # type: ignore[no-untyped-def]
                if not event.is_directory:
                    watcher._schedule_sync()
                else:
                    watcher._schedule_sync()

        self.root.mkdir(parents=True, exist_ok=True)
        self._observer = Observer()
        self._observer.schedule(Handler(), str(self.root), recursive=True)
        self._observer.start()

    def stop(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None

    def _schedule_sync(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = Timer(self.debounce_seconds, self._run_sync)
            self._timer.daemon = True
            self._timer.start()

    def _run_sync(self) -> None:
        with self._lock:
            self._timer = None
        self.sync_callback()

