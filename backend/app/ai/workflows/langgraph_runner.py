"""LangGraph-backed workflow runner.

Imports LangGraph lazily so the rest of the platform (and its tests) runs without
the dependency installed. Provides the same Step/state semantics as
SequentialWorkflow but compiles to a LangGraph StateGraph, enabling branching,
checkpointing, and streaming when needed.
"""
from __future__ import annotations

from app.ai.core.errors import WorkflowError
from app.ai.interfaces.step import Step
from app.ai.state.base import BaseState


def build_state_graph(steps: list[Step]):
    """Compile an ordered list of Steps into a LangGraph StateGraph.

    Raises WorkflowError with a clear message if LangGraph is not installed.
    """
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:  # pragma: no cover - exercised only without dep
        raise WorkflowError(
            "LangGraph is not installed; use SequentialWorkflow or `pip install langgraph`"
        ) from exc

    graph: StateGraph = StateGraph(BaseState)
    previous = START
    for step in steps:
        node_name = step.name

        def _node(state: BaseState, _step: Step = step) -> BaseState:
            return _step.run(state)

        graph.add_node(node_name, _node)
        graph.add_edge(previous, node_name)
        previous = node_name
    graph.add_edge(previous, END)
    return graph.compile()
