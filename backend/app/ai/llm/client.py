"""Provider-agnostic LLM client.

Implements the LLMProvider protocol. Supports:
  - Anthropic native (when api_key set and no base_url),
  - any OpenAI-compatible endpoint (Groq, Gemini-compat, OpenRouter, ...) when a
    base_url is configured — this is the path for free API tiers,
  - an offline mode (no key) that returns empty completions so callers fall back
    to deterministic behaviour. This keeps the whole platform runnable and testable
    without network access or paid keys.

Every call records token usage so the single choke point makes cost accounting fair
across all agents and the single-agent baseline.
"""
from __future__ import annotations

from app.ai.core.config import AIConfig, load_ai_config
from app.ai.core.errors import LLMError
from app.ai.core.logging import get_logger
from app.ai.models.messages import LLMRequest, LLMResponse, TokenUsage
from app.ai.types.enums import LLMRole, Provider

logger = get_logger(__name__)


class LLMClient:
    def __init__(self, config: AIConfig) -> None:
        self.config = config
        self._impl = None
        if config.provider is Provider.ANTHROPIC:
            self._impl = self._init_anthropic()
        elif config.provider is Provider.OPENAI_COMPATIBLE:
            self._impl = self._init_openai()

    # ---- provider initialisation (best-effort; falls back to offline) ----
    def _init_anthropic(self):
        try:
            import anthropic

            return anthropic.Anthropic(api_key=self.config.api_key)
        except Exception as exc:  # SDK missing / bad key
            logger.warning("anthropic unavailable (%s); offline fallback", exc)
            return None

    def _init_openai(self):
        try:
            from openai import OpenAI

            return OpenAI(api_key=self.config.api_key, base_url=self.config.base_url or None)
        except Exception as exc:
            logger.warning("openai-compatible client unavailable (%s); offline fallback", exc)
            return None

    @property
    def available(self) -> bool:
        return self._impl is not None

    # ---- generation ----
    def generate(self, request: LLMRequest) -> LLMResponse:
        if not self.available:
            return LLMResponse(text="", model="offline", finish_reason="offline")
        try:
            if self.config.provider is Provider.ANTHROPIC:
                return self._generate_anthropic(request)
            return self._generate_openai(request)
        except Exception as exc:  # normalise provider errors
            raise LLMError(f"generation failed: {exc}") from exc

    def _generate_anthropic(self, request: LLMRequest) -> LLMResponse:
        assert self._impl is not None  # guarded by `available` in generate()
        msg = self._impl.messages.create(
            model=request.model or self.config.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            system=request.system or "You are a precise assistant.",
            messages=[{"role": m.role.value, "content": m.content} for m in request.messages
                      if m.role is not LLMRole.SYSTEM],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        usage = TokenUsage(
            prompt_tokens=msg.usage.input_tokens,
            completion_tokens=msg.usage.output_tokens,
        )
        return LLMResponse(text=text, model=msg.model, usage=usage)

    def _generate_openai(self, request: LLMRequest) -> LLMResponse:
        assert self._impl is not None  # guarded by `available` in generate()
        msgs = []
        if request.system:
            msgs.append({"role": "system", "content": request.system})
        msgs += [{"role": m.role.value, "content": m.content} for m in request.messages]
        resp = self._impl.chat.completions.create(
            model=request.model or self.config.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            messages=msgs,
        )
        choice = resp.choices[0]
        usage = TokenUsage(
            prompt_tokens=getattr(resp.usage, "prompt_tokens", 0),
            completion_tokens=getattr(resp.usage, "completion_tokens", 0),
        )
        return LLMResponse(text=choice.message.content or "", model=resp.model, usage=usage,
                           finish_reason=choice.finish_reason or "stop")


def build_default_client() -> LLMClient:
    """Construct the client from process configuration."""
    return LLMClient(load_ai_config())
