"""Small bounded in-process abuse limiter for authentication entry points.

The limiter intentionally stores only keyed hashes, never raw email addresses.
Deployments with multiple backend processes must use a shared limiter at the
gateway; the application check remains defense in depth.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import hashlib
import threading
import time


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int = 0


class AuthenticationRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    @staticmethod
    def _key(action: str, client_ip: str, account: str) -> str:
        material = f"{action}\0{client_ip}\0{account.strip().casefold()}".encode("utf-8")
        return hashlib.sha256(material).hexdigest()

    def check(self, *, action: str, client_ip: str, account: str) -> RateLimitDecision:
        if action == "signup":
            limit, window = 5, 60 * 60
        else:
            limit, window = 8, 5 * 60
        key = self._key(action, client_ip, account)
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            while events and events[0] <= now - window:
                events.popleft()
            if len(events) >= limit:
                retry_after = max(1, int(window - (now - events[0])))
                return RateLimitDecision(False, retry_after)
            events.append(now)
            return RateLimitDecision(True)

    def reset_for_tests(self) -> None:
        with self._lock:
            self._events.clear()


authentication_rate_limiter = AuthenticationRateLimiter()
