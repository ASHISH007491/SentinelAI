"""Bridge: drive app/ai agents with the evaluation LLM seam.

The app/ai BaseAgent expects an ``LLMProvider`` (``.available`` + ``.generate(LLMRequest)``);
the harness speaks the simpler eval ``LLMClient`` (``.complete(prompt)``). EvalLLMProvider
adapts one to the other so the multi-agent system and the single-LLM baseline run on the
*exact same* injected LLM — holding the model constant and varying only the architecture.

A small path shim puts ``backend/`` on sys.path so the repo-root eval package can import
``app.ai`` without an editable install.
"""
from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[2] / "backend"
if _BACKEND.is_dir() and str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from eval.systems.llm import LLMClient  # noqa: E402

from app.ai.guardrail import PromptGuard as PromptGuard  # noqa: E402,F401 re-export
from app.ai.models.messages import LLMRequest, LLMResponse, TokenUsage  # noqa: E402


class EvalLLMProvider:
    """Implements app/ai's LLMProvider structural protocol over an eval LLMClient."""

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    @property
    def available(self) -> bool:
        return True

    def generate(self, request: LLMRequest) -> LLMResponse:
        prompt = "\n".join(m.content for m in request.messages)
        resp = self._client.complete(prompt, system=request.system)
        return LLMResponse(
            text=resp.text,
            usage=TokenUsage(
                prompt_tokens=resp.prompt_tokens,
                completion_tokens=resp.completion_tokens,
            ),
        )
