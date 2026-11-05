"""Tests for the LLMService facade."""
from app.ai.llm.service import LLMService, ModelManager, ModelSpec


def _offline_service():
    mm = ModelManager()
    mm.register("agentA", ModelSpec(provider="offline", model="model-a"))
    mm.register("agentB", ModelSpec(provider="offline", model="model-b", temperature=0.9))
    return LLMService(model_manager=mm), mm


def test_service_complete_routes_per_agent():
    svc, _ = _offline_service()
    a = svc.complete("hello", agent_id="agentA")
    b = svc.complete("hello", agent_id="agentB")
    assert "model-a" in a.text and "model-b" in b.text  # offline echoes model name


def test_service_complete_json_parses():
    # Offline echoes the prompt; feed it JSON so complete_json round-trips.
    svc, _ = _offline_service()
    out = svc.complete_json('{"k": 1}', agent_id="agentA")
    assert out == {"k": 1}


def test_service_tracks_cost_total():
    svc, _ = _offline_service()
    svc.complete("hi", agent_id="agentA")
    assert svc.total_cost_usd >= 0.0


def test_service_streaming():
    svc, _ = _offline_service()
    text = "".join(svc.stream("a b c", agent_id="agentA"))
    assert text.strip().endswith("c")
