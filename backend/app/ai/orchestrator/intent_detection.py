"""Intent detection — understand what a user request is asking for.

Rule-based core (keywords + uploaded file extensions + explicit hints), optionally
refined by an LLM. Supports multiple simultaneous intents and is extensible to future
intents via `register`. Produces, per intent: type, confidence, required capabilities
(resolved to concrete agents when a registry is provided), and the target workflow.

No domain logic — capabilities/workflows are generic strings.
"""
from __future__ import annotations

import enum
import re

from pydantic import BaseModel, Field

from app.ai.core.logging import get_logger

logger = get_logger(__name__)


class IntentType(str, enum.Enum):
    UPLOAD_SCAN = "upload_scan"
    UPLOAD_EMAIL = "upload_email"
    UPLOAD_SOURCE_CODE = "upload_source_code"
    GENERATE_REPORT = "generate_report"
    VIEW_DASHBOARD = "view_dashboard"
    SECURITY_QUESTION = "security_question"
    THREAT_INTELLIGENCE = "threat_intelligence"
    UNKNOWN = "unknown"


class IntentDefinition(BaseModel):
    """Declarative, registerable definition for one intent (extensible)."""
    type: IntentType
    keywords: list[str] = Field(default_factory=list)
    file_extensions: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    workflow: str = ""


class DetectedIntent(BaseModel):
    type: IntentType
    confidence: float
    capabilities: list[str] = Field(default_factory=list)
    required_agents: list[str] = Field(default_factory=list)
    workflow: str = ""
    matched: list[str] = Field(default_factory=list)  # signals that fired


class IntentDetectionResult(BaseModel):
    intents: list[DetectedIntent] = Field(default_factory=list)
    multiple: bool = False

    @property
    def primary(self) -> DetectedIntent | None:
        return self.intents[0] if self.intents else None

    def to_json(self) -> dict:
        return self.model_dump(mode="json")


# Default, overridable intent vocabulary.
DEFAULT_DEFINITIONS: list[IntentDefinition] = [
    IntentDefinition(type=IntentType.UPLOAD_SCAN,
                     keywords=["scan", "vulnerability", "vuln", "sbom", "sarif", "dependency"],
                     file_extensions=[".sarif", ".sbom"],
                     capabilities=["scan", "vuln"], workflow="vuln"),
    IntentDefinition(type=IntentType.UPLOAD_EMAIL,
                     keywords=["email", "phishing", "spam", "inbox", "sender", "spoof"],
                     file_extensions=[".eml", ".msg"],
                     capabilities=["phishing"], workflow="phishing"),
    IntentDefinition(type=IntentType.UPLOAD_SOURCE_CODE,
                     keywords=["code", "source", "review", "repository", "function", "snippet"],
                     file_extensions=[".py", ".js", ".ts", ".java", ".go", ".rb", ".c", ".cpp"],
                     capabilities=["code_review"], workflow="code_review"),
    IntentDefinition(type=IntentType.GENERATE_REPORT,
                     keywords=["report", "summary", "export", "executive", "pdf", "generate"],
                     capabilities=["report"], workflow="report"),
    IntentDefinition(type=IntentType.VIEW_DASHBOARD,
                     keywords=["dashboard", "overview", "status", "metrics", "home", "posture"],
                     capabilities=[], workflow="dashboard"),
    IntentDefinition(type=IntentType.SECURITY_QUESTION,
                     keywords=["how", "what", "why", "explain", "question", "advice",
                               "recommend", "should"],
                     capabilities=["advise"], workflow="advisor"),
    IntentDefinition(type=IntentType.THREAT_INTELLIGENCE,
                     keywords=["threat", "intel", "cve", "mitre", "ioc", "indicator",
                               "feed", "actor"],
                     capabilities=["knowledge", "threat_intel"], workflow="knowledge"),
]


class IntentDetector:
    def __init__(self, *, registry=None, llm_service=None, min_confidence: float = 0.3) -> None:
        self._defs: dict[IntentType, IntentDefinition] = {}
        self._registry = registry
        self._llm = llm_service
        self._min_conf = min_confidence
        for d in DEFAULT_DEFINITIONS:
            self.register(d)

    def register(self, definition: IntentDefinition) -> None:
        """Add or replace an intent definition (supports future intents)."""
        self._defs[definition.type] = definition

    def definitions(self) -> list[IntentType]:
        return sorted(self._defs, key=lambda t: t.value)

    def detect(self, text: str = "", *, files: list[str] | None = None,
               explicit_workflow: str | None = None) -> IntentDetectionResult:
        text_l = (text or "").lower()
        files = files or []
        exts = [self._ext(f) for f in files]

        scored: list[DetectedIntent] = []
        for definition in self._defs.values():
            score, matched = self._score(definition, text_l, exts, explicit_workflow)
            if score <= 0:
                continue
            confidence = min(1.0, 0.25 + 0.2 * score)
            scored.append(DetectedIntent(
                type=definition.type, confidence=round(confidence, 3),
                capabilities=list(definition.capabilities),
                required_agents=self._agents_for(definition.capabilities),
                workflow=definition.workflow, matched=matched,
            ))

        if text_l and self._llm is not None:
            scored = self._refine_with_llm(text, scored)

        scored.sort(key=lambda i: i.confidence, reverse=True)
        if not scored:
            scored = [DetectedIntent(type=IntentType.UNKNOWN, confidence=0.0)]

        kept = [i for i in scored if i.confidence >= self._min_conf] or scored[:1]
        return IntentDetectionResult(intents=kept, multiple=len(kept) > 1)

    # -- optional LLM refinement --------------------------------------------
    def _refine_with_llm(self, text: str, scored: list[DetectedIntent]) -> list[DetectedIntent]:
        """Ask the LLM which intent types apply and blend its choice with the rules.

        Best-effort: any failure (offline, parse error) leaves the rule-based result
        untouched. The LLM can only confirm/boost or add a known intent type — it never
        invents one outside the registered vocabulary.
        """
        vocab = [t.value for t in self.definitions() if t is not IntentType.UNKNOWN]
        prompt = (
            "Classify the security request into intent types from this list: "
            f"{vocab}. Return ONLY JSON {{\"intents\": [type, ...]}}. Request: {text[:1000]}"
        )
        try:
            data = self._llm.complete_json(prompt, agent_id="intent")
            chosen = {str(x) for x in data.get("intents", [])}
        except Exception as exc:  # offline / parse failure -> keep rules
            logger.warning("intent llm refinement failed: %s", exc)
            return scored

        by_type = {i.type.value: i for i in scored}
        for value in chosen:
            try:
                itype = IntentType(value)
            except ValueError:
                continue  # ignore anything outside the vocabulary
            if value in by_type:
                # Confirmed by both rules and LLM -> boost confidence.
                existing = by_type[value]
                existing.confidence = round(min(1.0, existing.confidence + 0.2), 3)
                if "llm" not in existing.matched:
                    existing.matched.append("llm")
            else:
                # LLM-only intent -> add with a moderate confidence.
                definition = self._defs[itype]
                scored.append(DetectedIntent(
                    type=itype, confidence=0.5, capabilities=list(definition.capabilities),
                    required_agents=self._agents_for(definition.capabilities),
                    workflow=definition.workflow, matched=["llm"],
                ))
        return scored

    # -- scoring -------------------------------------------------------------
    @staticmethod
    def _ext(filename: str) -> str:
        name = filename.lower()
        return name[name.rfind("."):] if "." in name else ""

    @staticmethod
    def _score(definition: IntentDefinition, text: str, exts: list[str],
               explicit_workflow: str | None) -> tuple[float, list[str]]:
        score = 0.0
        matched: list[str] = []
        for kw in definition.keywords:
            if re.search(rf"\b{re.escape(kw)}\b", text):
                score += 1
                matched.append(kw)
        for ext in definition.file_extensions:
            if ext in exts:
                score += 2  # a matching file is a strong signal
                matched.append(ext)
        if explicit_workflow and explicit_workflow == definition.workflow:
            score += 4
            matched.append(f"workflow:{explicit_workflow}")
        return score, matched

    def _agents_for(self, capabilities: list[str]) -> list[str]:
        if self._registry is None or not capabilities:
            return []
        agents: set[str] = set()
        for cap in capabilities:
            agents.update(self._registry.find_by_capability(cap))
        return sorted(agents)
