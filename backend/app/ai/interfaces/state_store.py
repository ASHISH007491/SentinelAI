"""State persistence contract."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.ai.types.aliases import JSON


@runtime_checkable
class StateStore(Protocol):
    def get(self, key: str) -> JSON | None: ...
    def set(self, key: str, value: JSON) -> None: ...
    def delete(self, key: str) -> None: ...
