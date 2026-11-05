"""Tests for intent detection."""
from app.ai.agents import AgentConfig, AgentRegistry, BaseAgent
from app.ai.orchestrator.intent_detection import (
    DEFAULT_DEFINITIONS,
    IntentDefinition,
    IntentDetector,
    IntentType,
)


def _detector(**kw):
    return IntentDetector(**kw)


# --- single intents per supported type ---
def test_upload_scan_by_keyword_and_file():
    r = _detector().detect("run a vulnerability scan", files=["app.sarif"])
    assert r.primary.type is IntentType.UPLOAD_SCAN
    assert r.primary.workflow == "vuln"
    assert ".sarif" in r.primary.matched


def test_upload_email():
    r = _detector().detect("is this phishing?", files=["suspicious.eml"])
    assert r.primary.type is IntentType.UPLOAD_EMAIL
    assert r.primary.capabilities == ["phishing"]


def test_upload_source_code():
    r = _detector().detect("review this source code", files=["main.py"])
    assert r.primary.type is IntentType.UPLOAD_SOURCE_CODE


def test_generate_report():
    r = _detector().detect("generate an executive report")
    assert r.primary.type is IntentType.GENERATE_REPORT


def test_view_dashboard():
    r = _detector().detect("show me the security dashboard")
    assert r.primary.type is IntentType.VIEW_DASHBOARD


def test_security_question():
    r = _detector().detect("what should I do about weak passwords?")
    assert any(i.type is IntentType.SECURITY_QUESTION for i in r.intents)


def test_threat_intelligence():
    r = _detector().detect("any intel on this MITRE technique and IOC?")
    assert r.primary.type is IntentType.THREAT_INTELLIGENCE


# --- multiple intents ---
def test_multiple_intents_detected_and_ordered():
    r = _detector().detect("scan this sbom and generate a report", files=["x.sbom"])
    assert r.multiple is True
    types = [i.type for i in r.intents]
    assert IntentType.UPLOAD_SCAN in types and IntentType.GENERATE_REPORT in types
    # ordered by confidence (the file-backed scan should outrank the report keyword)
    assert r.intents[0].confidence >= r.intents[1].confidence


# --- confidence + output contract ---
def test_confidence_and_json():
    r = _detector().detect("vulnerability scan", files=["a.sarif", "b.sarif"])
    top = r.primary
    assert 0.0 < top.confidence <= 1.0
    j = r.to_json()
    assert j["intents"][0]["type"] == "upload_scan"
    assert "confidence" in j["intents"][0]


# --- unknown when nothing matches ---
def test_unknown_when_no_signal():
    r = _detector().detect("xyzzy plugh")
    assert r.primary.type is IntentType.UNKNOWN and r.primary.confidence == 0.0


# --- explicit workflow strongly boosts ---
def test_explicit_workflow_dominates():
    r = _detector().detect("", explicit_workflow="phishing")
    assert r.primary.type is IntentType.UPLOAD_EMAIL


# --- required agents resolved via registry ---
def test_required_agents_resolved_from_registry():
    reg = AgentRegistry()
    cls = type("Det", (BaseAgent,), {
        "config": AgentConfig(id="detection", name="d"),
        "capabilities": ["scan"], "execute": lambda self, r: {}})
    reg.register(cls)
    r = _detector(registry=reg).detect("scan", files=["x.sarif"])
    assert "detection" in r.primary.required_agents


# --- future intent registration ---
def test_register_extends_or_overrides_definition():
    # Registering a definition for an existing type overrides it (extensibility):
    det = _detector()
    det.register(IntentDefinition(type=IntentType.SECURITY_QUESTION,
                                  keywords=["compliance"], capabilities=["advise"],
                                  workflow="advisor"))
    r = det.detect("a compliance query")
    assert r.primary.type is IntentType.SECURITY_QUESTION
    assert "compliance" in r.primary.matched


def test_all_supported_intents_have_definitions():
    types = {d.type for d in DEFAULT_DEFINITIONS}
    expected = {
        IntentType.UPLOAD_SCAN, IntentType.UPLOAD_EMAIL, IntentType.UPLOAD_SOURCE_CODE,
        IntentType.GENERATE_REPORT, IntentType.VIEW_DASHBOARD,
        IntentType.SECURITY_QUESTION, IntentType.THREAT_INTELLIGENCE,
    }
    assert expected <= types


# --- word-boundary matching avoids substring false positives ---
def test_word_boundary_no_substring_false_positives():
    det = _detector()
    # 'scandalous' must not trigger 'scan'; 'whatever' must not trigger 'what'
    r = det.detect("this is scandalous whatever")
    assert r.primary.type is IntentType.UNKNOWN
    # but the real words do match
    assert _detector().detect("run a scan").primary.type is IntentType.UPLOAD_SCAN


# --- LLM refinement actually runs and boosts/adds intents ---
class _FakeLLMService:
    """Mimics LLMService.complete_json for intent refinement."""
    def __init__(self, intents):
        self._intents = intents
        self.called = False

    def complete_json(self, prompt, **kw):
        self.called = True
        return {"intents": self._intents}


def test_llm_refinement_boosts_confirmed_intent():
    llm = _FakeLLMService(["upload_scan"])
    det = _detector(llm_service=llm)
    base = _detector().detect("run a scan").primary.confidence
    r = det.detect("run a scan")
    assert llm.called is True
    top = r.primary
    assert top.type is IntentType.UPLOAD_SCAN
    assert top.confidence > base          # boosted by LLM confirmation
    assert "llm" in top.matched


def test_llm_refinement_adds_llm_only_intent():
    # rules see only 'scan'; the LLM additionally asserts a report intent
    llm = _FakeLLMService(["generate_report"])
    det = _detector(llm_service=llm)
    r = det.detect("run a scan")
    types = {i.type for i in r.intents}
    assert IntentType.UPLOAD_SCAN in types
    assert IntentType.GENERATE_REPORT in types   # added by the LLM


def test_llm_failure_falls_back_to_rules():
    class _BadLLM:
        def complete_json(self, prompt, **kw):
            raise RuntimeError("offline")
    det = _detector(llm_service=_BadLLM())
    r = det.detect("run a scan")            # must still work via rules
    assert r.primary.type is IntentType.UPLOAD_SCAN
