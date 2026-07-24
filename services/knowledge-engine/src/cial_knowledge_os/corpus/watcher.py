"""Filesystem watcher feeding standalone incremental Corpus reconciliation."""

from __future__ import annotations

from pathlib import Path
from threading import Lock, Timer
from typing import Callable
import logging
import time

from .scanner import is_ignored_managed_path
from cial_knowledge_os.file_formats import is_supported_file

logger = logging.getLogger(__name__)


class CorpusWatcher:
    def __init__(
        self,
        *,
        root: Path,
        sync_callback: Callable[[list[Path]], object],
        debounce_seconds: float = 2.0,
        stability_attempts: int = 5,
        stability_interval: float = 0.2,
    ) -> None:
        self.root = root.resolve()
        self.sync_callback = sync_callback
        self.debounce_seconds = debounce_seconds
        self.stability_attempts = stability_attempts
        self.stability_interval = stability_interval
        self._observer = None
        self._timer: Timer | None = None
        self._pending_paths: set[Path] = set()
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
                paths = [Path(event.src_path).resolve()]
                destination = getattr(event, "dest_path", None)
                if destination:
                    paths.append(Path(destination).resolve())
                if any(
                    path != watcher.root and watcher.root not in path.parents
                    for path in paths
                ):
                    logger.warning("watcher_path_escape_rejected")
                    return
                if all(is_ignored_managed_path(path, watcher.root) for path in paths):
                    return
                if (
                    not bool(getattr(event, "is_directory", False))
                    and all(not is_supported_file(path.name) for path in paths)
                ):
                    return
                logger.info(
                    "file_detected",
                    extra={
                        "event": "file_detected",
                        "file_name": paths[-1].name,
                        "change_type": getattr(event, "event_type", "unknown"),
                        "is_directory": bool(getattr(event, "is_directory", False)),
                    },
                )
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
            self._pending_paths.clear()
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
        self.ready = False

    def _schedule_sync(self, paths: list[Path] | None = None) -> None:
        with self._lock:
            self._pending_paths.update(paths or [])
            if self._timer is not None:
                self._timer.cancel()
            self._timer = Timer(self.debounce_seconds, self._run_sync)
            self._timer.daemon = True
            self._timer.start()

    def _run_sync(self, explicit_paths: list[Path] | None = None) -> None:
        with self._lock:
            self._timer = None
            paths = list(self._pending_paths)
            paths.extend(explicit_paths or [])
            self._pending_paths.clear()
        try:
            for path in paths:
                if path.is_file() and not self._wait_until_stable(
                    path,
                    attempts=self.stability_attempts,
                    interval=self.stability_interval,
                ):
                    logger.warning("file_stability_timeout", extra={"event": "file_stable", "file_name": path.name})
                    self.last_error = "file_stability_timeout"
                    self.last_event_at = time.time()
                    return
            self.sync_callback(paths)
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
                try:
                    with path.open("rb"):
                        pass
                except OSError:
                    time.sleep(interval)
                    continue
                logger.info("file_stable", extra={"event": "file_stable", "file_name": path.name})
                return True
            previous = current
            time.sleep(interval)
        return False
