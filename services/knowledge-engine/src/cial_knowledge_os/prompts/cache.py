"""Small in-process cache for prompt file contents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CachedPrompt:
    """Cached prompt text with its source modification time."""

    text: str
    mtime_ns: int


class PromptCache:
    """Cache prompt files while still noticing local edits in development."""

    def __init__(self) -> None:
        self._items: dict[Path, CachedPrompt] = {}

    def get(self, path: Path) -> str:
        resolved = path.resolve()
        mtime_ns = resolved.stat().st_mtime_ns
        cached = self._items.get(resolved)
        if cached is not None and cached.mtime_ns == mtime_ns:
            return cached.text
        text = resolved.read_text(encoding="utf-8")
        self._items[resolved] = CachedPrompt(text=text, mtime_ns=mtime_ns)
        return text

    def clear(self) -> None:
        self._items.clear()
