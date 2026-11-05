"""IndicatorExtractionAgent: step 1 of the phishing pipeline (evidence extraction)."""
from __future__ import annotations

from app.ai.agents.base import BaseAgent
from app.ai.agents.config import AgentConfig
from app.ai.core.errors import LLMError
from app.ai.types.aliases import JSON
from app.ai.utils.json_parse import ask_json

_SYSTEM = "You are a phishing indicator extractor. Reply with JSON only."


class IndicatorExtractionAgent(BaseAgent):
    config = AgentConfig(
        id="indicator_extraction",
        name="Indicator Extraction Agent",
        description="Extracts structured phishing indicators from an email.",
        version="1.0.0",
    )
    capabilities = ["extract_indicators"]
    dependencies: list[str] = []
    retryable_errors = (LLMError,)

    def execute(self, request: JSON) -> JSON:  # type: ignore[override]
        inp = request.inputs  # type: ignore[attr-defined]
        prompt = (
            "Extract phishing indicators from this email. Reply with ONLY a JSON object with keys: "
            '"urls" (list), "sender_domain" (str), "auth_pass" (bool), "urgency" (bool), '
            '"credential_request" (bool), "signals" (list of short strings).\n'
            f"From: {inp.get('sender', '')}\n"
            f"Subject: {inp.get('subject', '')}\n"
            f"Headers: {inp.get('headers', {})}\n"
            f"Body: {inp.get('body', '')}"
        )
        data, _ = ask_json(self.generate, prompt, system=_SYSTEM)
        data = data or {}
        return {
            "urls": data.get("urls", []),
            "sender_domain": data.get("sender_domain", ""),
            "auth_pass": bool(data.get("auth_pass", False)),
            "urgency": bool(data.get("urgency", False)),
            "credential_request": bool(data.get("credential_request", False)),
            "signals": data.get("signals", []),
        }
