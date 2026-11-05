"""PhishingVerdictAgent: step 2 of the phishing pipeline (extract -> verdict)."""
from __future__ import annotations

from app.ai.agents.base import BaseAgent
from app.ai.agents.config import AgentConfig
from app.ai.core.errors import LLMError
from app.ai.types.aliases import JSON
from app.ai.utils.json_parse import ask_json, infer_positive

_SYSTEM = "You are a phishing analyst. Reply with JSON only."


class PhishingVerdictAgent(BaseAgent):
    config = AgentConfig(
        id="phishing_verdict",
        name="Phishing Verdict Agent",
        description="Classifies an email as phish/legit from extracted indicators.",
        version="1.0.0",
    )
    capabilities = ["phishing_verdict"]
    dependencies = ["indicator_extraction"]
    retryable_errors = (LLMError,)

    def execute(self, request: JSON) -> JSON:  # type: ignore[override]
        inp = request.inputs  # type: ignore[attr-defined]
        prompt = (
            "Given these phishing indicators, classify the email. "
            'Reply with ONLY a JSON object: {"label": "phish|legit", "confidence": 0-1, '
            '"rationale": "..."}.\n'
            f"Indicators: {inp.get('indicators', {})}\n"
            f"Subject: {inp.get('subject', '')}\nSender: {inp.get('sender', '')}"
        )
        data, raw = ask_json(self.generate, prompt, system=_SYSTEM)
        if data is not None:
            label = str(data.get("label", "legit")).strip().lower()
            is_phish = label == "phish"
            confidence = max(0.0, min(1.0, float(data.get("confidence", 0.0) or 0.0)))
            rationale = str(data.get("rationale", ""))
        else:
            is_phish = infer_positive(raw, "phish")
            label = "phish" if is_phish else "legit"
            confidence = 0.3
            rationale = "inferred from unstructured reply"
        return {"label": label, "is_phish": is_phish,
                "confidence": confidence, "rationale": rationale}
