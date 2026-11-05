"""Offline tests for the Ollama client (HTTP layer mocked — no server needed)."""
import json

import pytest
from eval.systems.ollama import OllamaError, OllamaLLM


class _FakeResp:
    def __init__(self, payload: dict) -> None:
        self._b = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_complete_parses_text_and_token_counts(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode())
        return _FakeResp({"response": "verdict", "prompt_eval_count": 42, "eval_count": 7})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    r = OllamaLLM(model="mistral").complete("classify", system="be terse")
    assert r.text == "verdict" and r.prompt_tokens == 42 and r.completion_tokens == 7
    assert captured["url"].endswith("/api/generate")
    assert captured["body"]["model"] == "mistral"
    assert captured["body"]["system"] == "be terse"
    assert captured["body"]["options"]["temperature"] == 0.0
    assert captured["body"]["stream"] is False


def test_missing_token_counts_default_to_zero(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout=0: _FakeResp({"response": "ok"}))
    r = OllamaLLM().complete("hi")
    assert r.text == "ok" and r.prompt_tokens == 0 and r.completion_tokens == 0


def test_unreachable_raises_friendly_error(monkeypatch):
    import urllib.error

    def boom(req, timeout=0):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", boom)
    with pytest.raises(OllamaError, match="cannot reach Ollama"):
        OllamaLLM().complete("hi")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
