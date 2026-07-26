"""Bounded in-memory cache for authorization-scoped retrieval results."""

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class RetrievalCacheEntry:
    payload: dict[str, Any]
    generation: int
    principal_id: str
    permission_boundary: str
    created_at: str


class RetrievalResultCache:
    """Cache retrieval candidates without caching answers or generation state."""

    def __init__(self, *, max_entries: int = 256) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries must be greater than zero.")
        self.max_entries = int(max_entries)
        self._entries: OrderedDict[str, RetrievalCacheEntry] = OrderedDict()
        self._permission_boundaries: dict[str, str] = {}
        self._generation = 0
        self._last_invalidation_reason: str | None = None
        self._lock = RLock()

    def activate_generation(self, generation: int) -> bool:
        """Invalidate all candidates when the published generation changes."""

        generation = int(generation)
        with self._lock:
            if generation == self._generation:
                return False
            had_state = bool(self._entries) or self._generation != 0
            self._entries.clear()
            self._generation = generation
            self._last_invalidation_reason = (
                "published_generation_changed" if had_state else None
            )
            return had_state

    def observe_permission_boundary(
        self,
        principal_id: str,
        permission_boundary: str,
    ) -> bool:
        """Remove one principal's entries when its resolved grants change."""

        with self._lock:
            previous = self._permission_boundaries.get(principal_id)
            self._permission_boundaries[principal_id] = permission_boundary
            if previous is None or previous == permission_boundary:
                return False
            stale = [
                key
                for key, entry in self._entries.items()
                if entry.principal_id == principal_id
            ]
            for key in stale:
                self._entries.pop(key, None)
            self._last_invalidation_reason = "permission_boundary_changed"
            return True

    def lookup(self, key: str) -> dict[str, Any]:
        """Return a defensive copy plus measured cache state."""

        with self._lock:
            entry = self._entries.get(key)
            if entry is None or entry.generation != self._generation:
                if entry is not None:
                    self._entries.pop(key, None)
                    self._last_invalidation_reason = (
                        "published_generation_changed"
                    )
                return {
                    "hit": False,
                    "cache_size": len(self._entries),
                    "invalidation_reason": self._last_invalidation_reason,
                }
            self._entries.move_to_end(key)
            return {
                "hit": True,
                **deepcopy(entry.payload),
                "generation": entry.generation,
                "created_at": entry.created_at,
                "cache_size": len(self._entries),
                "invalidation_reason": None,
            }

    def store(
        self,
        key: str,
        payload: Mapping[str, Any],
        *,
        generation: int,
        principal_id: str,
        permission_boundary: str,
    ) -> None:
        """Store only candidate data for the currently active generation."""

        generation = int(generation)
        with self._lock:
            if generation != self._generation:
                return
            self._entries[key] = RetrievalCacheEntry(
                payload=deepcopy(dict(payload)),
                generation=generation,
                principal_id=principal_id,
                permission_boundary=permission_boundary,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)

    def clear(self, *, reason: str = "service_shutdown") -> None:
        with self._lock:
            self._entries.clear()
            self._last_invalidation_reason = reason

    def diagnostics(self) -> dict[str, Any]:
        with self._lock:
            return {
                "retrieval_cache_size": len(self._entries),
                "retrieval_cache_max_entries": self.max_entries,
                "retrieval_cache_generation": self._generation,
                "retrieval_cache_invalidation_reason": (
                    self._last_invalidation_reason
                ),
            }
