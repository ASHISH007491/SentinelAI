"""Ollama-backed LLMProvider: lets the *live app* run the app/ai specialist agents on a
free local model (no API key). Implements the app/ai LLMProvider protocol directly over
Ollama's HTTP API, using only the stdlib.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from app.ai.models.messages import LLMRequest, LLMResponse, TokenUsage


class OllamaProvider:
    def __init__(self, model: str = "llama3.2", base_url: str = "http://localhost:11434",
                 *, timeout: float = 300.0) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @property
    def available(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=3):
                return True
        except OSError:
            return False

    def generate(self, request: LLMRequest) -> LLMResponse:
        prompt = "\n".join(m.content for m in request.messages)
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": request.temperature},
        }
        if request.system:
            payload["system"] = request.system
        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode())
        return LLMResponse(
            text=str(body.get("response", "")),
            usage=TokenUsage(
                prompt_tokens=int(body.get("prompt_eval_count", 0) or 0),
                completion_tokens=int(body.get("eval_count", 0) or 0),
            ),
            model=self.model,
        )


def make_llm_provider():
    """Pick the LLM provider for the live app: explicit setting, else API key, else a
    locally-running Ollama, else None (caller falls back to the offline/legacy path)."""
    from app.core.config import settings
    provider = (settings.llm_provider or "").lower()

    if provider == "ollama":
        model = settings.llm_model if ("llama" in settings.llm_model
                                       or "mistral" in settings.llm_model) else "llama3.2"
        return OllamaProvider(model=model,
                              base_url=settings.llm_base_url or "http://localhost:11434")
    if settings.llm_api_key:
        from app.ai.integration.llm_bridge import LLMClientProvider
        from app.core.llm_client import LLMClient
        return LLMClientProvider(LLMClient())
    # Auto-detect: use Ollama if it's up, otherwise signal offline (None).
    candidate = OllamaProvider(model="llama3.2",
                               base_url=settings.llm_base_url or "http://localhost:11434")
    return candidate if candidate.available else None
