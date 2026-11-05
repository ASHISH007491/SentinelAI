"""In-memory TTL cache for deterministic (temperature 0) completions."""
from __future__ import annotations

import hashlib
import json
import time

from app.ai.models.messages import LLMRequest, LLMResponse


def request_key(request: LLMRequest) -> str:
    payload = {
        "model": request.model,
        "system": request.system,
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
        "messages": [(m.role.value, m.content) for m in request.messages],
    }
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


class ResponseCache:
    def __init__(self, maxsize: int = 256, ttl_s: float = 3600.0, clock=time.monotonic) -> None:
        self.maxsize = maxsize
        self.ttl_s = ttl_s
        self._clock = clock
        self._data: dict[str, tuple[float, LLMResponse]] = {}

    def get(self, request: LLMRequest) -> LLMResponse | None:
        key = request_key(request)
        item = self._data.get(key)
        if item is None:
            return None
        expires, response = item
        if self._clock() > expires:
            self._data.pop(key, None)
            return None
        return response

    def set(self, request: LLMRequest, response: LLMResponse) -> None:
        if len(self._data) >= self.maxsize:
            # Evict the soonest-to-expire entry.
            oldest = min(self._data, key=lambda k: self._data[k][0])
            self._data.pop(oldest, None)
        self._data[request_key(request)] = (self._clock() + self.ttl_s, response)

    def clear(self) -> None:
        self._data.clear()
