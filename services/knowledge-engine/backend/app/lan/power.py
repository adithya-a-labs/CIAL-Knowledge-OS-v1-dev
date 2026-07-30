"""Process-scoped Windows system-sleep prevention."""

from __future__ import annotations

import ctypes
import os


ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


class KeepAwakeLease:
    def __init__(self) -> None:
        self.acquired = False

    def acquire(self) -> bool:
        if os.name != "nt":
            return False
        result = ctypes.windll.kernel32.SetThreadExecutionState(  # type: ignore[attr-defined]
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        )
        self.acquired = bool(result)
        return self.acquired

    def release(self) -> None:
        if self.acquired and os.name == "nt":
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)  # type: ignore[attr-defined]
        self.acquired = False

    def __enter__(self) -> "KeepAwakeLease":
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()

