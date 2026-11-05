from app.ai.models.messages import LLMMessage, LLMRequest, LLMResponse, TokenUsage
from app.ai.models.results import StepResult, WorkflowResult
from app.ai.types.enums import LLMRole, Provider, StepStatus


def test_token_usage_add_and_total():
    u = TokenUsage(prompt_tokens=10, completion_tokens=5) + TokenUsage(
        prompt_tokens=2, completion_tokens=3
    )
    assert u.total_tokens == 20


def test_request_response_models():
    req = LLMRequest(messages=[LLMMessage(role=LLMRole.USER, content="hi")], system="sys")
    assert req.messages[0].role is LLMRole.USER
    resp = LLMResponse(text="ok", usage=TokenUsage(completion_tokens=4))
    assert resp.usage.total_tokens == 4


def test_workflow_result_total_usage():
    wr = WorkflowResult(workflow="w", steps=[
        StepResult(name="a", usage=TokenUsage(completion_tokens=3)),
        StepResult(name="b", usage=TokenUsage(prompt_tokens=2)),
    ])
    assert wr.total_usage.total_tokens == 5
    assert Provider.OFFLINE.value == "offline" and StepStatus.COMPLETED.value == "completed"
