"""Deterministic content hashing for corpus documents."""

from __future__ import annotations

import hashlib
from pathlib import Path


def hash_file(path: Path, *, algorithm: str = "sha256", chunk_size: int = 1024 * 1024) -> str:
    try:
        hasher = hashlib.new(algorithm)
    except ValueError as exc:
        raise ValueError(f"Unsupported corpus hash algorithm: {algorithm}") from exc

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

