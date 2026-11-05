"""Unit tests for the BaseAgent framework."""
import time

from app.ai.agents import AgentConfig, AgentRequest, BaseAgent, ToolRegistry
from app.ai.core.errors import LLMError, ValidationError
from app.ai.models.messages import LLMResponse, TokenUsage
from app.ai.prompts.registry import PromptRegistry
from app.ai.types.enums import StepStatus


# --- test doubles -----------------------------------------------------------
class FakeLLM:
    """An injectable LLMProvider returning a fixed response with usage."""
    def __init__(self, text="ok", tokens=5):
        self._text, self._tokens = text, tokens
        self.calls = 0

    @property
    def available(self):
        return True

    def generate(self, request):
        self.calls += 1
        return LLMResponse(text=self._text, model="fake",
                           usage=TokenUsage(completion_tokens=self._tokens))


class EchoAgent(BaseAgent):
    config = AgentConfig(
        id="echo", name="Echo Agent", description="returns its inputs", version="2.1.0"
    )

    def execute(self, request: AgentRequest):
        return {"echo": request.inputs}


class LLMAgent(BaseAgent):
    config = AgentConfig(id="llm", name="LLM Agent")

    def execute(self, request: AgentRequest):
        resp = self.generate("hello", system="be brief")
        return {"text": resp.text}


class StrictAgent(BaseAgent):
    config = AgentConfig(id="strict", name="Strict")

    def validate(self, request):
        super().validate(request)
        if "name" not in request.inputs:
            raise ValidationError("missing 'name'")

    def execute(self, request):
        return {"hi": request.inputs["name"]}


# --- tests ------------------------------------------------------------------
def _req(**inputs):
    return AgentRequest(run_id="r1", inputs=inputs)


def test_happy_path_returns_completed_json():
    result = EchoAgent(llm=FakeLLM()).run(_req(a=1))
    assert result.status is StepStatus.COMPLETED
    assert result.output == {"echo": {"a": 1}}
    assert result.agent_name == "Echo Agent" and result.version == "2.1.0"
    # JSON-only contract
    j = result.to_json()
    assert isinstance(j, dict) and j["status"] == "completed"


def test_metrics_track_tokens_from_llm():
    agent = LLMAgent(llm=FakeLLM(tokens=8))
    result = agent.run(_req())
    assert result.output["text"] == "ok"
    assert result.metrics.tokens.total_tokens == 8
    assert result.metrics.latency_ms >= 0


def test_validation_error_is_handled_as_json():
    result = StrictAgent(llm=FakeLLM()).run(_req())  # no 'name'
    assert result.status is StepStatus.FAILED
    assert result.error.code == "ai_validation_error"
    assert result.error.type == "ValidationError"


def test_model_selection_passed_through():
    cfg = AgentConfig(id="m", name="M", model="llama-3.1-8b-instant")
    captured = {}

    class _LLM(FakeLLM):
        def generate(self, request):
            captured["model"] = request.model
            return super().generate(request)

    class A(BaseAgent):
        config = cfg
        def execute(self, request):
            self.generate("x")
            return {}

    A(llm=_LLM()).run(_req())
    assert captured["model"] == "llama-3.1-8b-instant"


def test_retry_on_transient_then_success():
    class Flaky(BaseAgent):
        config = AgentConfig(id="flaky", name="Flaky", max_retries=2, retry_backoff_s=0)
        def __init__(self, **kw):
            super().__init__(**kw)
            self.n = 0
        def execute(self, request):
            self.n += 1
            if self.n < 3:
                raise LLMError("transient")
            return {"n": self.n}

    result = Flaky(llm=FakeLLM()).run(_req())
    assert result.status is StepStatus.COMPLETED
    assert result.output == {"n": 3}
    assert result.metrics.retries == 2


def test_validation_error_is_not_retried():
    class V(BaseAgent):
        config = AgentConfig(id="v", name="V", max_retries=3, retry_backoff_s=0)
        def __init__(self, **kw):
            super().__init__(**kw)
            self.n = 0
        def execute(self, request):
            self.n += 1
            raise ValidationError("bad")

    result = V(llm=FakeLLM()).run(_req())
    assert result.status is StepStatus.FAILED
    assert result.metrics.retries == 0  # validation never retries


def test_timeout_produces_failed_result():
    class Slow(BaseAgent):
        config = AgentConfig(id="slow", name="Slow", timeout_s=0.1, max_retries=0)
        def execute(self, request):
            time.sleep(0.5)
            return {}

    result = Slow(llm=FakeLLM()).run(_req())
    assert result.status is StepStatus.FAILED
    assert result.error.code == "ai_agent_timeout"


def test_tool_registration_and_use():
    class UpperTool:
        name = "upper"
        def run(self, text=""):
            return {"value": text.upper()}

    registry = ToolRegistry()
    registry.register(UpperTool())

    class T(BaseAgent):
        config = AgentConfig(id="t", name="T")
        def execute(self, request):
            return self.use_tool("upper", text="hello")

    result = T(llm=FakeLLM(), tools=registry).run(_req())
    assert result.output == {"value": "HELLO"}
    assert result.metrics.tool_calls == 1


def test_prompt_loading_via_injected_registry():
    reg = PromptRegistry()
    reg.register("greet", "Hi {name}")

    class P(BaseAgent):
        config = AgentConfig(id="p", name="P", prompt_names=["greet"])
        def execute(self, request):
            return {"prompt": self.render_prompt("greet", {"name": "Sam"})}

    result = P(llm=FakeLLM(), prompts=reg).run(_req())
    assert result.output == {"prompt": "Hi Sam"}


def test_missing_declared_prompt_fails_initialize():
    class P(BaseAgent):
        config = AgentConfig(id="p2", name="P2", prompt_names=["nope"])
        def execute(self, request):
            return {}

    result = P(llm=FakeLLM(), prompts=PromptRegistry()).run(_req())
    assert result.status is StepStatus.FAILED
    assert result.error.code == "ai_configuration_error"


def test_lifecycle_hooks_called_in_order():
    calls = []

    class L(BaseAgent):
        config = AgentConfig(id="l", name="L", timeout_s=0)
        def initialize(self):
            calls.append("initialize")

        def validate(self, request):
            calls.append("validate")

        def execute(self, request):
            calls.append("execute")
            return {}

        def post_process(self, output):
            calls.append("post")
            return output

        def cleanup(self):
            calls.append("cleanup")

    L(llm=FakeLLM()).run(_req())
    assert calls == ["initialize", "validate", "execute", "post", "cleanup"]


def test_direct_llm_call_still_accumulates_tokens():
    """Tokens are counted even when a subclass bypasses self.generate()."""
    from app.ai.models.messages import LLMMessage, LLMRequest
    from app.ai.types.enums import LLMRole

    class Direct(BaseAgent):
        config = AgentConfig(id="direct", name="Direct")

        def execute(self, request):
            # Call the (wrapped) provider directly — metering must still apply.
            self.llm.generate(LLMRequest(messages=[LLMMessage(role=LLMRole.USER, content="x")]))
            self.llm.generate(LLMRequest(messages=[LLMMessage(role=LLMRole.USER, content="y")]))
            return {}

    result = Direct(llm=FakeLLM(tokens=4)).run(_req())
    assert result.metrics.tokens.total_tokens == 8  # 2 calls x 4 tokens


def test_baseagent_satisfies_agent_protocol():
    from app.ai.interfaces import Agent
    agent = EchoAgent(llm=FakeLLM())
    assert isinstance(agent, Agent)
