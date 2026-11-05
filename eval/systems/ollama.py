"""OllamaLLM: drive the evaluation with a free, local model via the Ollama HTTP API.

Implements the eval LLMClient protocol over http://localhost:11434, using only the
stdlib (no extra deps). Temperature defaults to 0 for as-reproducible-as-possible runs,
and real token counts come straight from Ollama's response. Inject this into both the
baseline and the multi-agent system to produce the dissertation's real numbers.

Prereqs (on your machine):
    1. Install Ollama       -> https://ollama.com/download
    2. Pull a model         -> `ollama pull llama3`   (or `mistral`)
    3. Make sure it's up    -> `ollama serve` (the desktop app does this automatically)
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from eval.systems.llm import LLMResponse


class OllamaError(RuntimeError):
    """Raised when the local Ollama server cannot be reached or errors."""


class OllamaLLM:
    def __init__(self, model: str = "llama3", host: str = "http://localhost:11434",
                 *, temperature: float = 0.0, timeout: float = 120.0) -> None:
        self.model = model
        self.host = host.rstrip("/")
        self.temperature = temperature
        self.timeout = timeout

    def complete(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": self.temperature},
        }
        if system:
            payload["system"] = system
        req = urllib.request.Request(
            f"{self.host}/api/generate",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode())
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise OllamaError(
                f"cannot reach Ollama at {self.host} (is `ollama serve` running "
                f"and `{self.model}` pulled?): {exc}"
            ) from exc
        text = str(body.get("response", ""))
        return LLMResponse(
            text=text,
            prompt_tokens=int(body.get("prompt_eval_count", 0) or 0),
            completion_tokens=int(body.get("eval_count", 0) or 0),
        )

    def ping(self) -> bool:
        """Best-effort reachability check for a friendly pre-run error."""
        try:
            with urllib.request.urlopen(f"{self.host}/api/tags", timeout=5):
                return True
        except OSError:
            return False
