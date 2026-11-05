"""Unit tests for the LLM Service components (offline / deterministic)."""
import itertools

import pytest

from app.ai.core.errors import ConfigurationError, RateLimitError
from app.ai.llm.service import (
    CostTracker,
    LLMFactory,
    ModelManager,
    ModelSpec,
    OfflineProvider,
    PromptExecutor,
    RateLimiter,
    ResponseCache,
    TokenCounter,
)
from app.ai.llm.service.cache import request_key
from app.ai.models.messages import LLMMessage, LLMRequest, LLMResponse, TokenUsage
from app.ai.types.enums import LLMRole


def _req(content="hello world", model="m", temperature=0.0):
    return LLMRequest(messages=[LLMMessage(role=LLMRole.USER, content=content)],
                      model=model, temperature=temperature)


# --- TokenCounter ---
def test_token_counter_counts_request():
    tc = TokenCounter()
    n = tc.count_request(_req(content="abcdefgh"))
    assert n >= 1


# --- Cache ---
def test_cache_hit_and_ttl():
    clock = itertools.count(0, 1)  # 0,1,2,...
    cache = ResponseCache(ttl_s=5, clock=lambda: next(clock))
    req = _req()
    resp = LLMResponse(text="x", model="m")
    cache.set(req, resp)            # stored at t=0, expires t=5
    assert cache.get(req) is not None  # t=1
    for _ in range(6):
        next(clock)
    assert cache.get(req) is None   # expired


def test_cache_key_stable():
    assert request_key(_req()) == request_key(_req())
    assert request_key(_req("a")) != request_key(_req("b"))


# --- RateLimiter ---
def test_rate_limiter_blocks_when_empty():
    rl = RateLimiter(rate_per_sec=1, capacity=1, clock=lambda: 0.0)
    assert rl.try_acquire() is True   # uses the one token
    assert rl.try_acquire() is False  # empty, clock frozen
    assert RateLimiter(rate_per_sec=0).try_acquire() is True  # disabled


# --- CostTracker ---
def test_cost_tracker_accumulates():
    ct = CostTracker(prices={"gpt-4o": (1.0, 2.0)})
    cost = ct.record("gpt-4o", TokenUsage(prompt_tokens=1000, completion_tokens=1000))
    assert cost == pytest.approx(3.0)
    ct.record("gpt-4o", TokenUsage(prompt_tokens=1000, completion_tokens=0))
    assert ct.total_cost == pytest.approx(4.0)
    assert ct.record("unknown-model", TokenUsage(prompt_tokens=1000)) == 0.0


# --- Factory ---
def test_factory_creates_providers_and_rejects_unknown():
    assert isinstance(LLMFactory.create(ModelSpec(provider="offline", model="m")), OfflineProvider)
    with pytest.raises(ConfigurationError):
        LLMFactory.create(ModelSpec(provider="nope", model="m"))


# --- ModelManager (env + per-agent) ---
def test_model_manager_per_agent_env_override(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "llm_provider", "offline", raising=False)
    monkeypatch.setattr(settings, "llm_model", "default-model", raising=False)
    mm = ModelManager()
    assert mm.resolve("nobody").model == "default-model"
    monkeypatch.setenv("LLM_MODEL__DETECTION", "special-model")
    monkeypatch.setenv("LLM_TEMPERATURE__DETECTION", "0.7")
    spec = mm.resolve("detection")
    assert spec.model == "special-model" and spec.temperature == 0.7


def test_model_manager_programmatic_override():
    mm = ModelManager()
    mm.register("vuln", ModelSpec(provider="ollama", model="llama3", temperature=0.2))
    assert mm.resolve("vuln").model == "llama3"


# --- PromptExecutor ---
def test_executor_offline_fills_usage_and_cost():
    ex = PromptExecutor(OfflineProvider(), cost_tracker=CostTracker(prices={"m": (1.0, 1.0)}),
                        cache=ResponseCache(), timeout_s=0)
    resp = ex.execute(_req(content="alpha beta"))
    assert resp.usage.total_tokens > 0          # filled by token counter
    assert "cost_usd" in resp.metadata


def test_executor_cache_hit_second_call():
    cache = ResponseCache()
    ex = PromptExecutor(OfflineProvider(), cache=cache, timeout_s=0)
    first = ex.execute(_req())
    second = ex.execute(_req())
    assert first.metadata.get("cache_hit") is None
    assert second.metadata.get("cache_hit") is True


def test_executor_rate_limit_raises():
    rl = RateLimiter(rate_per_sec=1, capacity=1, clock=lambda: 0.0)
    ex = PromptExecutor(OfflineProvider(), rate_limiter=rl, cache=None, timeout_s=0)
    ex.execute(_req(temperature=0.5))   # consumes the token (no cache for temp>0)
    with pytest.raises(RateLimitError):
        ex.execute(_req(content="other", temperature=0.5))


def test_executor_json_output_adds_instruction():
    captured = {}

    class _P(OfflineProvider):
        def generate(self, request):
            captured["system"] = request.system
            return super().generate(request)

    PromptExecutor(_P(), timeout_s=0).execute(_req(), json_output=True)
    assert "JSON" in (captured["system"] or "")


def test_offline_streaming_yields_chunks():
    chunks = list(OfflineProvider().stream(_req(content="one two three")))
    assert "".join(chunks).strip().endswith("three")
