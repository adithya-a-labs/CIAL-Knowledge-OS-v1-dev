"""Structured logging setup for the development API."""

from __future__ import annotations

import logging
import sys
from threading import Lock


class SuccessfulPollingAccessFilter(logging.Filter):
    """Keep polling failures and sample repetitive successful poll access logs."""

    def __init__(self, sample_every: int = 20) -> None:
        super().__init__()
        self.sample_every = max(1, sample_every)
        self._counts: dict[str, int] = {}
        self._lock = Lock()

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if not isinstance(args, tuple) or len(args) < 5:
            return True
        path = str(args[2])
        try:
            status = int(args[4])
        except (TypeError, ValueError):
            return True
        polling = path.endswith("/status") or "/analysis?" in path
        if not polling or status >= 400:
            return True
        key = path.split("?", 1)[0]
        with self._lock:
            count = self._counts.get(key, 0) + 1
            self._counts[key] = count
        return count == 1 or count % self.sample_every == 0


def configure_logging() -> None:
    """Configure concise process-wide logging once."""

    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s",
            )
        )
        root.addHandler(handler)
        root.setLevel(logging.INFO)
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(value, SuccessfulPollingAccessFilter) for value in access.filters):
        access.addFilter(SuccessfulPollingAccessFilter())
