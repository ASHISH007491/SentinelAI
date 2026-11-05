import pytest

from app.ai.core.errors import ParsingError
from app.ai.models.messages import TokenUsage
from app.ai.state import BaseState, InMemoryStateStore
from app.ai.utils import Timer, estimate_tokens, extract_json, retry


def test_base_state_trace_and_usage():
    s = BaseState(run_id="r1")
    s.note("started")
    s.add_usage(TokenUsage(completion_tokens=7))
    assert s.trace == ["started"] and s.usage.total_tokens == 7


def test_state_store_roundtrip():
    store = InMemoryStateStore()
    store.set("k", {"a": 1})
    assert store.get("k") == {"a": 1}
    store.delete("k")
    assert store.get("k") is None


def test_extract_json_from_noise():
    assert extract_json('prefix ```json\n{"a": 1}\n``` suffix') == {"a": 1}
    assert extract_json("[1, 2, 3]") == [1, 2, 3]
    with pytest.raises(ParsingError):
        extract_json("no json here")


def test_estimate_tokens_and_timer():
    assert estimate_tokens("abcdefgh") == 2
    with Timer() as t:
        pass
    assert t.elapsed_ms >= 0


def test_retry_succeeds_after_failures():
    calls = {"n": 0}

    @retry(attempts=3, delay_s=0)
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("nope")
        return "ok"

    assert flaky() == "ok" and calls["n"] == 3
