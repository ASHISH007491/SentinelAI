"""CodeReviewAgent: secure-code review for a single snippet."""
from __future__ import annotations

from app.ai.agents.base import BaseAgent
from app.ai.agents.config import AgentConfig
from app.ai.core.errors import LLMError
from app.ai.types.aliases import JSON
from app.ai.utils.json_parse import ask_json, infer_positive

_SYSTEM = "You are a secure-code reviewer. Reply with JSON only."


class CodeReviewAgent(BaseAgent):
    config = AgentConfig(
        id="code_review",
        name="Secure Code Review Agent",
        description="Flags vulnerable code by CWE with a fix suggestion.",
        version="1.0.0",
    )
    capabilities = ["code_review"]
    dependencies: list[str] = []
    retryable_errors = (LLMError,)

    def execute(self, request: JSON) -> JSON:  # type: ignore[override]
        inp = request.inputs  # type: ignore[attr-defined]
        language = inp.get("language", "python")
        code = inp.get("code", "")
        # Optional pre-flagged candidates from an upstream PatternScanAgent: [{cwe,
        # pattern, confidence}]. When present, review is decomposed (scan, then confirm
        # + fix); when absent, this collapses to the original single-shot review prompt.
        candidates = inp.get("candidates")  # type: ignore[attr-defined]
        if candidates is not None:   # decomposed caller: use "is not None" so an empty
                                      # scan result (no candidates found) still takes this
                                      # branch instead of silently falling back to the
                                      # broader single-shot prompt below
            listing = "\n".join(
                f"- {c.get('cwe')}: {c.get('pattern')} (confidence {c.get('confidence')})"
                for c in candidates if isinstance(c, dict)
            )
            prompt = (
                f"Confirm or reject each candidate vulnerability pattern below using the "
                f"{language} code, and write a fix for any confirmed. "
                'Reply with ONLY a JSON object: {"vulnerable": true|false, "cwe": "CWE-xx|null", '
                '"confidence": 0-1, "rationale": "...", "fix": "..."}.\n'
                f"Candidate patterns:\n{listing}\n\n"
                f"```{language}\n{code}\n```"
            )
        else:
            prompt = (
                f"Review this {language} code for security vulnerabilities. "
                'Reply with ONLY a JSON object: {"vulnerable": true|false, "cwe": "CWE-xx|null", '
                '"confidence": 0-1, "rationale": "...", "fix": "..."}.\n'
                f"```{language}\n{code}\n```"
            )
        data, raw = ask_json(self.generate, prompt, system=_SYSTEM)
        if data is not None:
            vulnerable = bool(data.get("vulnerable", False))
            cwe = data.get("cwe")
            cwe = cwe if cwe and str(cwe).lower() != "null" else None
            confidence = max(0.0, min(1.0, float(data.get("confidence", 0.0) or 0.0)))
            rationale = str(data.get("rationale", ""))
            fix = str(data.get("fix", ""))
        else:
            vulnerable = infer_positive(raw, "vulnerable")
            cwe = None
            confidence = 0.3
            rationale = "inferred from unstructured reply"
            fix = ""
        return {"vulnerable": vulnerable, "cwe": cwe, "confidence": confidence,
                "rationale": rationale, "fix": fix}
