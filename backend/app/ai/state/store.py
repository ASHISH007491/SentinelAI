"""In-memory StateStore implementation (process-local).

Implements the StateStore protocol. Swap for a Redis- or DB-backed store later
without changing callers — the contract is in ai/interfaces/state_store.py.
"""
from __future__ import annotations

from app.ai.types.aliases import JSON


class InMemoryStateStore:
    def __init__(self) -> None:
        self._data: dict[str, JSON] = {}

    def get(self, key: str) -> JSON | None:
        return self._data.get(key)

    def set(self, key: str, value: JSON) -> None:
        self._data[key] = value

    def delete(self, key: str) -> None:
        self._data.pop(key, None)
