"""PatternScanAgent: step 1 of the code-review pipeline (candidate pattern scan).

Independently flags candidate vulnerability patterns -- command execution, insecure
deserialisation, weak cryptography, and injection via unsanitised concatenation (SQL,
path, or output/XSS) -- before CodeReviewAgent confirms each candidate and writes a fix.

Deliberately covers the same vulnerability scope as a single-shot review (an earlier
version scoped this narrower, excluding weak-crypto/XSS as "a different class"; that
silently broke the guardrail's full-defence guarantee on those CWE categories in Track D,
since a detection gap here is a detection gap everywhere downstream of it -- reverted).
"""
from __future__ import annotations

from app.ai.agents.base import BaseAgent
from app.ai.agents.config import AgentConfig
from app.ai.core.errors import LLMError
from app.ai.types.aliases import JSON
from app.ai.utils.json_parse import ask_json

_SYSTEM = "You are a code-security pattern scanner. Reply with JSON only."


class PatternScanAgent(BaseAgent):
    config = AgentConfig(
        id="pattern_scan",
        name="Pattern Scan Agent",
        description="Flags candidate dangerous-API-call vulnerability patterns before review.",
        version="1.0.0",
    )
    capabilities = ["scan_patterns"]
    dependencies: list[str] = []
    retryable_errors = (LLMError,)

    def execute(self, request: JSON) -> JSON:  # type: ignore[override]
        inp = request.inputs  # type: ignore[attr-defined]
        language = inp.get("language", "python")
        code = inp.get("code", "")
        prompt = (
            f"Scan this {language} code for candidate vulnerability patterns: command "
            "execution, insecure deserialisation, weak cryptography, and injection via "
            "unsanitised concatenation (SQL, path, or output/XSS). This is a first pass, "
            "independent of a final verdict. "
            'Reply with ONLY a JSON object: {"candidates": [{"cwe": "CWE-xx", '
            '"pattern": "...", "confidence": 0-1}]}.\n'
            f"```{language}\n{code}\n```"
        )
        data, _ = ask_json(self.generate, prompt, system=_SYSTEM)
        candidates = (data or {}).get("candidates") or []
        out = [
            {"cwe": str(c.get("cwe", "")), "pattern": str(c.get("pattern", "")),
             "confidence": max(0.0, min(1.0, float(c.get("confidence", 0.5) or 0.5)))}
            for c in candidates if isinstance(c, dict) and c.get("cwe")
        ]
        return {"candidates": out}
