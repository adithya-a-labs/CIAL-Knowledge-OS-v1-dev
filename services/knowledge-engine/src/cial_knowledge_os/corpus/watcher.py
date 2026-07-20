"""Optional filesystem watcher for incremental Corpus synchronization."""

from __future__ import annotations

from pathlib import Path
from threading import Lock, Timer
from typing import Callable
import logging
import time

from .scanner import is_ignored_managed_path

logger = logging.getLogger(__name__)


class CorpusWatcher:
    def __init__(self, *, root: Path, sync_callback: Callable[[], object], debounce_seconds: float = 2.0) -> None:
        self.root = root
        self.sync_callback = sync_callback
        self.debounce_seconds = debounce_seconds
        self._observer = None
        self._timer: Timer | None = None
        self._lock = Lock()
        self.ready = False
        self.last_error: str | None = None
        self.last_event_at: float | None = None

    def start(self) -> None:
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"watchdog is unavailable: {exc}") from exc

        watcher = self

        class Handler(FileSystemEventHandler):
            def on_any_event(self, event):  # type: ignore[no-untyped-def]
                paths = [Path(event.src_path)]
                destination = getattr(event, "dest_path", None)
                if destination:
                    paths.append(Path(destination))
                if all(is_ignored_managed_path(path, watcher.root) for path in paths):
                    return
                logger.info("file_detected", extra={"event": "file_detected", "filename": paths[-1].name})
                watcher._schedule_sync(paths)

        self.root.mkdir(parents=True, exist_ok=True)
        self._observer = Observer()
        self._observer.schedule(Handler(), str(self.root), recursive=True)
        self._observer.start()
        self.ready = True

    def stop(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
        self.ready = False

    def _schedule_sync(self, paths: list[Path] | None = None) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = Timer(self.debounce_seconds, self._run_sync, args=(paths or [],))
            self._timer.daemon = True
            self._timer.start()

    def _run_sync(self, paths: list[Path]) -> None:
        with self._lock:
            self._timer = None
        try:
            for path in paths:
                if path.is_file() and not self._wait_until_stable(path):
                    logger.warning("file_stability_timeout", extra={"event": "file_stable", "filename": path.name})
                    return
            self.sync_callback()
            logger.info("metadata_synced", extra={"event": "metadata_synced", "outcome": "success"})
            self.last_event_at = time.time()
            self.last_error = None
        except Exception as exc:  # noqa: BLE001 - watcher must remain alive.
            self.last_error = type(exc).__name__
            logger.exception("corpus_watcher_sync_failed")

    @staticmethod
    def _wait_until_stable(path: Path, attempts: int = 5, interval: float = 0.2) -> bool:
        previous: tuple[int, int] | None = None
        for _ in range(attempts):
            try:
                stat = path.stat()
            except FileNotFoundError:
                return True
            current = (stat.st_size, stat.st_mtime_ns)
            if current == previous:
                logger.info("file_stable", extra={"event": "file_stable", "filename": path.name})
                return True
            previous = current
            time.sleep(interval)
        return False
