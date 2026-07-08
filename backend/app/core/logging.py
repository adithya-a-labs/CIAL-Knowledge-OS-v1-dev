"""Structured logging setup for the development API."""

from __future__ import annotations

import logging
import sys


def configure_logging() -> None:
    """Configure concise process-wide logging once."""

    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
        )
    )
    root.addHandler(handler)
    root.setLevel(logging.INFO)
