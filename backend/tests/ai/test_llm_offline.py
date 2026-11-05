from app.ai.core.config import AIConfig
from app.ai.llm import LLMClient
from app.ai.models.messages import LLMMessage, LLMRequest
from app.ai.types.enums import LLMRole, Provider


def test_offline_client_returns_empty_and_unavailable():
    cfg = AIConfig(provider=Provider.OFFLINE, model="m")
    client = LLMClient(cfg)
    assert client.available is False
    resp = client.generate(LLMRequest(messages=[LLMMessage(role=LLMRole.USER, content="hi")]))
    assert resp.text == "" and resp.finish_reason == "offline"


# --- OpenAI-compatible path with a fake client (no network) ---
from types import SimpleNamespace  # noqa: E402


class _FakeOpenAI:
    """Mimics the openai SDK surface used by LLMClient._generate_openai."""
    def __init__(self):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.captured = None

    def _create(self, **kwargs):
        self.captured = kwargs
        return SimpleNamespace(
            model=kwargs["model"],
            choices=[SimpleNamespace(
                message=SimpleNamespace(content="hello from groq"),
                finish_reason="stop",
            )],
            usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7),
        )


def test_openai_compatible_generate_maps_response():
    cfg = AIConfig(provider=Provider.OPENAI_COMPATIBLE, model="llama-3.1-8b-instant",
                   api_key="k", base_url="https://api.groq.com/openai/v1")
    client = LLMClient.__new__(LLMClient)   # bypass real SDK init
    client.config = cfg
    client._impl = _FakeOpenAI()

    assert client.available is True
    resp = client.generate(LLMRequest(
        messages=[LLMMessage(role=LLMRole.USER, content="hi")], system="be brief",
    ))
    assert resp.text == "hello from groq"
    assert resp.usage.prompt_tokens == 11 and resp.usage.completion_tokens == 7
    # system prompt + user message were forwarded
    sent = client._impl.captured["messages"]
    assert sent[0]["role"] == "system" and sent[-1]["content"] == "hi"
