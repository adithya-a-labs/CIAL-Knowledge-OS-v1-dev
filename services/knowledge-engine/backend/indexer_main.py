"""Production entrypoint for the standalone CIAL continuous indexer."""

from __future__ import annotations

import logging
from pathlib import Path
import signal
import sys

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from backend.app.core.logging import configure_logging
from backend.app.services.continuous_indexer import ContinuousIndexer


def main() -> int:
    configure_logging()
    logger = logging.getLogger("cial-indexer")
    indexer = ContinuousIndexer()

    def stop(_signum, _frame) -> None:  # type: ignore[no-untyped-def]
        logger.info("indexer_shutdown_requested")
        indexer.stop()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, stop)
    try:
        indexer.run()
    except Exception:
        logger.exception("indexer_fatal_error")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
