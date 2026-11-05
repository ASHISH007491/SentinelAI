"""PromptExecutor: run an LLMRequest through cross-cutting concerns.

Applies (in order): cache lookup -> rate limit -> retry(timeout(provider)) ->
token/cost accounting -> cache store. Streaming bypasses caching.
"""
from __future__ import annotations

import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout

from app.ai.core.errors import AgentTimeoutError, LLMError, RateLimitError
from app.ai.core.logging import get_logger
from app.ai.interfaces.llm import LLMProvider
from app.ai.llm.service.cache import ResponseCache
from app.ai.llm.service.cost import CostTracker
from app.ai.llm.service.rate_limiter import RateLimiter
from app.ai.llm.service.token_counter import TokenCounter
from app.ai.models.messages import LLMRequest, LLMResponse, TokenUsage

logger = get_logger(__name__)

_JSON_INSTRUCTION = "Respond with valid JSON only. Do not include prose or code fences."


class PromptExecutor:
    def __init__(
        self,
        provider: LLMProvider,
        *,
        token_counter: TokenCounter | None = None,
        cache: ResponseCache | None = None,
        rate_limiter: RateLimiter | None = None,
        cost_tracker: CostTracker | None = None,
        timeout_s: float = 60.0,
        max_retries: int = 2,
        retry_backoff_s: float = 0.5,
    ) -> None:
        self.provider = provider
        self.tokens = token_counter or TokenCounter()
        self.cache = cache
        self.rate_limiter = rate_limiter
        self.cost = cost_tracker
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.retry_backoff_s = retry_backoff_s

    def execute(
        self, request: LLMRequest, *, use_cache: bool = True, json_output: bool = False
    ) -> LLMResponse:
        if json_output:
            request = self._with_json_system(request)

        if use_cache and self.cache is not None:
            cached = self.cache.get(request)
            if cached is not None:
                meta = {**cached.metadata, "cache_hit": True}
                return cached.model_copy(update={"metadata": meta})

        if self.rate_limiter is not None and not self.rate_limiter.try_acquire():
            raise RateLimitError("LLM rate limit exceeded")

        response = self._retry(request)
        self._account(request, response)

        if use_cache and self.cache is not None and request.temperature == 0:
            self.cache.set(request, response)
        return response

    def stream(self, request: LLMRequest) -> Iterator[str]:
        streamer = getattr(self.provider, "stream", None)
        if streamer is None:
            raise LLMError("provider does not support streaming")
        if self.rate_limiter is not None and not self.rate_limiter.try_acquire():
            raise RateLimitError("LLM rate limit exceeded")
        yield from streamer(request)

    # -- internals --
    def _with_json_system(self, request: LLMRequest) -> LLMRequest:
        system = (request.system + "\n\n" if request.system else "") + _JSON_INSTRUCTION
        return request.model_copy(update={"system": system})

    def _retry(self, request: LLMRequest) -> LLMResponse:
        attempts = max(1, self.max_retries + 1)
        last: Exception | None = None
        for attempt in range(attempts):
            try:
                return self._timeout(request)
            except (LLMError, AgentTimeoutError) as exc:
                last = exc
                logger.warning("llm retry %d/%d: %s", attempt + 1, attempts, exc)
                if attempt < attempts - 1:
                    time.sleep(self.retry_backoff_s * (attempt + 1))
        assert last is not None
        raise last

    def _timeout(self, request: LLMRequest) -> LLMResponse:
        if self.timeout_s <= 0:
            return self.provider.generate(request)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.provider.generate, request)
            try:
                return future.result(timeout=self.timeout_s)
            except FuturesTimeout as exc:
                raise AgentTimeoutError(f"LLM call exceeded {self.timeout_s}s") from exc

    def _account(self, request: LLMRequest, response: LLMResponse) -> None:
        # Fill usage if the provider didn't report it (e.g. offline/Ollama).
        if response.usage.total_tokens == 0:
            response.usage = TokenUsage(
                prompt_tokens=self.tokens.count_request(request),
                completion_tokens=self.tokens.count(response.text),
            )
        if self.cost is not None:
            cost = self.cost.record(response.model or request.model or "", response.usage)
            response.metadata = {**response.metadata, "cost_usd": round(cost, 6)}
