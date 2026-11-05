"""Simple synchronous retry decorator with linear backoff."""
from __future__ import annotations

import time
from collections.abc import Callable
from functools import wraps
from typing import TypeVar

from app.ai.core.logging import get_logger

T = TypeVar("T")
logger = get_logger(__name__)


def retry(
    attempts: int = 3,
    delay_s: float = 0.5,
    exceptions: tuple[type[Exception], ...] = (Exception,),
):
    """Retry the wrapped callable up to `attempts` times on `exceptions`."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last: Exception | None = None
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:  # noqa: PERF203
                    last = exc
                    logger.warning("retry %d/%d after error: %s", attempt, attempts, exc)
                    if attempt < attempts:
                        time.sleep(delay_s * attempt)
            assert last is not None
            raise last

        return wrapper

    return decorator
