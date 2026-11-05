"""A small context manager for measuring elapsed wall-clock time."""
from __future__ import annotations

import time


class Timer:
    def __enter__(self) -> Timer:
        self._start = time.perf_counter()
        self.elapsed_ms = 0.0
        return self

    def __exit__(self, *_exc: object) -> None:
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000
