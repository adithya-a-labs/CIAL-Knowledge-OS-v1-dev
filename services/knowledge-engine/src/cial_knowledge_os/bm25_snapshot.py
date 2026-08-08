"""Atomic, versioned BM25 source snapshots shared by indexer and API."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Callable, Iterable


SNAPSHOT_VERSION = 1


@dataclass(frozen=True, slots=True)
class BM25Snapshot:
    generation: int
    chunks: tuple[dict[str, Any], ...]


def write_bm25_snapshot(
    path: Path,
    *,
    generation: int,
    chunks: Iterable[dict[str, Any]],
    progress_callback: Callable[[], None] | None = None,
) -> Path:
    """Write a complete generation and atomically publish it with ``os.replace``."""

    target = path.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            if progress_callback is not None:
                progress_callback()
            handle.write(
                '{"version":'
                + str(SNAPSHOT_VERSION)
                + ',"generation":'
                + str(int(generation))
                + ',"chunks":['
            )
            first = True
            last_progress = time.monotonic()
            for chunk in chunks:
                if not first:
                    handle.write(",")
                json.dump(chunk, handle, ensure_ascii=False, separators=(",", ":"))
                first = False
                if (
                    progress_callback is not None
                    and time.monotonic() - last_progress >= 5
                ):
                    progress_callback()
                    last_progress = time.monotonic()
            handle.write("]}")
            if progress_callback is not None:
                progress_callback()
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return target


def load_bm25_snapshot(path: Path) -> BM25Snapshot | None:
    target = path.expanduser().resolve()
    if not target.is_file():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("version") != SNAPSHOT_VERSION:
        return None
    chunks = payload.get("chunks")
    generation = payload.get("generation")
    if not isinstance(chunks, list) or not isinstance(generation, int):
        return None
    normalized = tuple(item for item in chunks if isinstance(item, dict))
    if len(normalized) != len(chunks):
        return None
    return BM25Snapshot(generation=generation, chunks=normalized)
