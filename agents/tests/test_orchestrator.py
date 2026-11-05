from sentinelai_agents.contracts.base import AgentInput, Workflow
from sentinelai_agents.orchestrator.graph import run_workflow


def test_vuln_route():
    out = run_workflow(AgentInput(run_id="1", workflow=Workflow.VULN))
    assert [o.agent for o in out] == ["detection", "prioritisation", "advisor", "report"]
