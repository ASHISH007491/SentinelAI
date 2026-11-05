"""Offline tests for the single-LLM baseline + structured-output helper (FakeLLM)."""
import json

import pytest
from eval.datasets.loaders import load_code, load_cves, load_emails
from eval.systems.baseline import SingleLLMBaseline
from eval.systems.contracts import Ranking, SystemUnderTest, Usage, Verdict
from eval.systems.llm import FakeLLM
from eval.systems.structured import (
    StructuredOutputError,
    extract,
    parse_json_block,
)
from pydantic import BaseModel


# --- structured output -------------------------------------------------------
def test_parse_json_block_handles_fences_and_prose():
    assert parse_json_block('here:\n```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_block('noise {"b": 2} trailing') == {"b": 2}
    with pytest.raises(ValueError):
        parse_json_block("no json here")


class _Schema(BaseModel):
    label: str
    confidence: float = 0.0


def test_extract_retries_then_succeeds():
    # first reply invalid, second valid -> 2 attempts, both responses recorded
    llm = FakeLLM(["not json at all", '{"label": "phish", "confidence": 0.9}'])
    ex = extract(llm, "classify", _Schema, retries=2)
    assert ex.value.label == "phish" and ex.attempts == 2
    assert len(ex.responses) == 2
    assert "not valid" in llm.prompts[1]  # error fed back into the re-ask


def test_extract_gives_up_after_budget():
    llm = FakeLLM(["nope", "still nope", "nope again"])
    with pytest.raises(StructuredOutputError):
        extract(llm, "classify", _Schema, retries=2)


# --- baseline: three tracks --------------------------------------------------
def test_baseline_is_a_system_under_test():
    assert isinstance(SingleLLMBaseline(FakeLLM(["{}"])), SystemUnderTest)


def test_prioritise_normalises_to_valid_permutation():
    cves = load_cves()[:5]
    ids = [c.cve_id for c in cves]
    # model returns a partial + one bogus id; baseline must repair to a full permutation
    reply = json.dumps({"order": [ids[2], ids[0], "CVE-9999-0000"], "rationale": {}})
    base = SingleLLMBaseline(FakeLLM([reply]))
    rk = base.prioritise(cves)
    assert isinstance(rk, Ranking)
    assert sorted(rk.order) == sorted(ids)          # valid permutation
    assert rk.order[:2] == [ids[2], ids[0]]         # model's order respected
    assert rk.usage.agents_invoked == 1 and rk.usage.total_tokens > 0


def test_investigate_email_maps_label_to_positive():
    email = load_emails()[0]
    phish = SingleLLMBaseline(FakeLLM(['{"label":"phish","confidence":0.8,"rationale":"x"}']))
    legit = SingleLLMBaseline(FakeLLM(['{"label":"legit","confidence":0.7,"rationale":"y"}']))
    assert phish.investigate_email(email).positive is True
    assert legit.investigate_email(email).positive is False


def test_review_code_maps_label_to_positive_and_clamps_conf():
    code = load_code()[0]
    reply = '{"label":"vulnerable","confidence":1.5,"rationale":"sqli"}'
    base = SingleLLMBaseline(FakeLLM([reply]))
    v = base.review_code(code)
    assert isinstance(v, Verdict)
    assert v.positive is True and v.confidence == 1.0   # clamped to [0,1]


def test_usage_addition():
    a = Usage(prompt_tokens=10, completion_tokens=5, llm_calls=1, agents_invoked=1)
    b = Usage(prompt_tokens=3, completion_tokens=2, llm_calls=1, agents_invoked=2)
    s = a + b
    assert s.total_tokens == 20 and s.llm_calls == 2 and s.agents_invoked == 3


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
