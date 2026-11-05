"""IntentClassifier: turn a request into a structured Intent.

Explicit routing (agents/capabilities/workflow on the request) wins. Otherwise, if a
free-text query is present and the LLM service is available, ask it to map the query
to capability tags drawn from the registry. Falls back to an empty intent offline.
No domain logic — capability tags are generic strings.
"""
from __future__ import annotations

from app.ai.core.logging import get_logger
from app.ai.orchestrator.models import Intent, OrchestratorRequest

logger = get_logger(__name__)


class IntentClassifier:
    def __init__(self, llm_service=None, registry=None) -> None:
        self._llm = llm_service
        self._registry = registry

    def classify(self, request: OrchestratorRequest) -> Intent:
        # 1) Explicit selection wins — deterministic, no LLM.
        if request.agents or request.capabilities or request.workflow:
            caps = list(request.capabilities)
            if request.workflow:
                caps = caps or [request.workflow]
            return Intent(workflow=request.workflow or "", capabilities=caps,
                          confidence=1.0, source="explicit")

        # 2) LLM classification over the available capability vocabulary.
        has_llm = self._llm is not None and getattr(self._llm, "models", None) is not None
        if request.query and has_llm:
            intent = self._classify_with_llm(request)
            if intent is not None:
                return intent

        # 3) Offline fallback.
        return Intent(workflow="", capabilities=[], confidence=0.0, source="fallback")

    def _classify_with_llm(self, request: OrchestratorRequest) -> Intent | None:
        vocab = self._capability_vocab()
        if not vocab:
            return None
        prompt = (
            "Map the user request to the most relevant capability tags from this list: "
            f"{vocab}. Return ONLY a JSON object {{\"capabilities\": [..], \"confidence\": 0-1}}. "
            f"Request: {request.query[:2000]}"
        )
        try:
            data = self._llm.complete_json(prompt, agent_id="orchestrator")
            caps = [c for c in data.get("capabilities", []) if c in vocab]
            return Intent(workflow="", capabilities=caps,
                          confidence=float(data.get("confidence", 0.0)), source="llm")
        except Exception as exc:  # offline/parse failure -> fall back
            logger.warning("intent llm classification failed: %s", exc)
            return None

    def _capability_vocab(self) -> list[str]:
        if self._registry is None:
            return []
        vocab: set[str] = set()
        for name in self._registry.names():
            vocab.update(self._registry.descriptor(name).capabilities)
        return sorted(vocab)
