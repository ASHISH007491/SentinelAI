"""LLMService: the single entry point agents use to talk to a model.

Composes ModelManager (which model for which agent, env-driven), LLMFactory (build
the provider), and a shared PromptExecutor stack (cache, rate limiter, cost tracker,
token counter). Contains no agent logic.
"""
from __future__ import annotations

from collections.abc import Iterator

from app.ai.llm.service.cache import ResponseCache
from app.ai.llm.service.cost import CostTracker
from app.ai.llm.service.executor import PromptExecutor
from app.ai.llm.service.factory import LLMFactory
from app.ai.llm.service.model_manager import ModelManager, ModelSpec
from app.ai.llm.service.rate_limiter import RateLimiter
from app.ai.llm.service.token_counter import TokenCounter
from app.ai.models.messages import LLMMessage, LLMRequest, LLMResponse
from app.ai.types.aliases import JSON
from app.ai.types.enums import LLMRole
from app.ai.utils.json_parse import extract_json


class LLMService:
    def __init__(
        self,
        *,
        model_manager: ModelManager | None = None,
        cache: ResponseCache | None = None,
        rate_limiter: RateLimiter | None = None,
        cost_tracker: CostTracker | None = None,
        timeout_s: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        self.models = model_manager or ModelManager()
        self.cache = cache if cache is not None else ResponseCache()
        self.rate_limiter = rate_limiter
        self.cost = cost_tracker if cost_tracker is not None else CostTracker()
        self.timeout_s = timeout_s
        self.max_retries = max_retries

    def _build_request(self, spec: ModelSpec, prompt: str, system: str | None,
                       temperature: float | None, max_tokens: int) -> LLMRequest:
        return LLMRequest(
            messages=[LLMMessage(role=LLMRole.USER, content=prompt)],
            system=system,
            model=spec.model,
            temperature=spec.temperature if temperature is None else temperature,
            max_tokens=max_tokens,
        )

    def _executor(self, spec: ModelSpec) -> PromptExecutor:
        provider = LLMFactory.create(spec)
        return PromptExecutor(
            provider,
            token_counter=TokenCounter(spec.model),
            cache=self.cache,
            rate_limiter=self.rate_limiter,
            cost_tracker=self.cost,
            timeout_s=self.timeout_s,
            max_retries=self.max_retries,
        )

    def complete(
        self,
        prompt: str,
        *,
        agent_id: str | None = None,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int = 1024,
        json_output: bool = False,
        use_cache: bool = True,
    ) -> LLMResponse:
        spec = self.models.resolve(agent_id)
        request = self._build_request(spec, prompt, system, temperature, max_tokens)
        return self._executor(spec).execute(request, use_cache=use_cache, json_output=json_output)

    def complete_json(self, prompt: str, **kwargs) -> JSON:
        """Convenience: request JSON output and parse it."""
        kwargs["json_output"] = True
        response = self.complete(prompt, **kwargs)
        return extract_json(response.text)

    def stream(self, prompt: str, *, agent_id: str | None = None, system: str | None = None,
               temperature: float | None = None, max_tokens: int = 1024) -> Iterator[str]:
        spec = self.models.resolve(agent_id)
        request = self._build_request(spec, prompt, system, temperature, max_tokens)
        return self._executor(spec).stream(request)

    @property
    def total_cost_usd(self) -> float:
        return round(self.cost.total_cost, 6)
