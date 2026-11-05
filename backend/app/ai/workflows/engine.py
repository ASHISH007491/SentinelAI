"""LangGraph workflow engine.

A builder for directed workflow graphs with conditional routing, per-node retry,
error-recovery routing, execution monitoring, and Mermaid/LangGraph visualisation.

It executes on a built-in, dependency-free executor (so workflows run and are fully
testable without LangGraph), and can also compile to a real LangGraph StateGraph via
`to_langgraph()`. No agent logic lives here — nodes are arbitrary state functions.

State is a plain dict: a node receives the current state and returns a dict of
updates, which are merged in (the LangGraph partial-update convention).
"""
from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from app.ai.core.errors import WorkflowError
from app.ai.core.logging import get_logger

logger = get_logger(__name__)

END = "__end__"

State = dict
NodeFn = Callable[[State], Mapping | None]
Router = Callable[[State], str]


@dataclass
class Node:
    name: str
    fn: NodeFn
    retries: int = 0
    retry_backoff_s: float = 0.0
    on_error: str | None = None  # node to route to if this node fails after retries
    timeout_s: float = 0.0  # per-attempt soft timeout; <=0 disables


class NodeEvent(BaseModel):
    node: str
    attempt: int
    status: Literal["success", "retried", "failed"]
    latency_ms: float = 0.0
    error: str | None = None


class WorkflowRunResult(BaseModel):
    workflow: str
    status: Literal["completed", "failed"]
    state: State = Field(default_factory=dict)
    events: list[NodeEvent] = Field(default_factory=list)
    error: str | None = None
    steps: int = 0


class ExecutionMonitor:
    """Collects node events and forwards them to an optional live callback."""

    def __init__(self, on_event: Callable[[NodeEvent], None] | None = None) -> None:
        self.events: list[NodeEvent] = []
        self._on_event = on_event

    def handle(self, event: NodeEvent) -> None:
        self.events.append(event)
        if self._on_event:
            self._on_event(event)


class CompiledWorkflow:
    def __init__(self, name: str, nodes: dict[str, Node], edges: dict[str, str],
                 conditionals: dict[str, tuple[Router, dict[str, str] | None]], entry: str) -> None:
        self.name = name
        self._nodes = nodes
        self._edges = edges
        self._conditionals = conditionals
        self._entry = entry

    # -- execution -----------------------------------------------------------
    def run(self, state: State | None = None, *, monitor: ExecutionMonitor | None = None,
            max_steps: int = 100) -> WorkflowRunResult:
        state = dict(state or {})
        events: list[NodeEvent] = []
        current = self._entry
        steps = 0

        while current != END and steps < max_steps:
            steps += 1
            node = self._nodes[current]
            ok, error = self._execute_node(node, state, events, monitor)
            if ok:
                current = self._route(current, state)
            elif node.on_error:
                logger.info("node '%s' failed; recovering via '%s'", node.name, node.on_error)
                current = node.on_error
            else:
                return WorkflowRunResult(workflow=self.name, status="failed", state=state,
                                         events=events, error=error, steps=steps)

        if current != END:
            return WorkflowRunResult(
                workflow=self.name, status="failed", state=state, events=events,
                error=f"exceeded max_steps={max_steps}", steps=steps,
            )
        return WorkflowRunResult(workflow=self.name, status="completed", state=state,
                                 events=events, steps=steps)

    def _execute_node(self, node: Node, state: State, events: list[NodeEvent],
                      monitor: ExecutionMonitor | None) -> tuple[bool, str | None]:
        attempts = node.retries + 1
        for attempt in range(1, attempts + 1):
            started = time.perf_counter()
            try:
                updates = self._call(node, state)
                if updates:
                    state.update(dict(updates))
                self._emit(events, monitor, NodeEvent(
                    node=node.name, attempt=attempt, status="success",
                    latency_ms=round((time.perf_counter() - started) * 1000, 2)))
                return True, None
            except Exception as exc:  # node failure -> retry or fail
                last = attempt == attempts
                self._emit(events, monitor, NodeEvent(
                    node=node.name, attempt=attempt, status="failed" if last else "retried",
                    latency_ms=round((time.perf_counter() - started) * 1000, 2), error=str(exc)))
                if last:
                    return False, str(exc)
                if node.retry_backoff_s:
                    time.sleep(node.retry_backoff_s * attempt)
        return False, "unreachable"

    def _route(self, current: str, state: State) -> str:
        if current in self._conditionals:
            router, mapping = self._conditionals[current]
            key = router(state)
            nxt = mapping[key] if mapping else key
            return nxt
        return self._edges.get(current, END)

    @staticmethod
    def _call(node: Node, state: State) -> Mapping | None:
        if node.timeout_s <= 0:
            return node.fn(state)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(node.fn, state)
            try:
                return future.result(timeout=node.timeout_s)
            except FuturesTimeout as exc:
                raise TimeoutError(
                    f"node '{node.name}' exceeded {node.timeout_s}s"
                ) from exc

    @staticmethod
    def _emit(events: list[NodeEvent], monitor: ExecutionMonitor | None, event: NodeEvent) -> None:
        events.append(event)
        if monitor:
            monitor.handle(event)

    # -- visualisation -------------------------------------------------------
    def to_mermaid(self, result: WorkflowRunResult | None = None) -> str:
        """Render the graph. If a run result is passed, highlight the executed path
        and colour nodes by their final status (executed / failed)."""
        return _mermaid(self._nodes, self._edges, self._conditionals, self._entry, result)

    def to_langgraph(self):
        """Compile to a real LangGraph StateGraph (requires `langgraph`)."""
        try:
            from langgraph.graph import END as LG_END
            from langgraph.graph import START, StateGraph
        except ImportError as exc:  # pragma: no cover
            raise WorkflowError("LangGraph is not installed") from exc

        graph: StateGraph = StateGraph(dict)
        for name, node in self._nodes.items():
            def _wrap(state: State, _node: Node = node) -> dict:
                # Return the merged full state so untyped dict channels don't overwrite.
                return {**state, **dict(_node.fn(state) or {})}
            graph.add_node(name, _wrap)
        graph.add_edge(START, self._entry)
        for src, dst in self._edges.items():
            graph.add_edge(src, LG_END if dst == END else dst)
        for src, (router, mapping) in self._conditionals.items():
            graph.add_conditional_edges(src, router, mapping)
        return graph.compile()


class WorkflowBuilder:
    """Fluent builder for a workflow graph."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._nodes: dict[str, Node] = {}
        self._edges: dict[str, str] = {}
        self._conditionals: dict[str, tuple[Router, dict[str, str] | None]] = {}
        self._entry: str | None = None

    def add_node(self, name: str, fn: NodeFn, *, retries: int = 0,
                 retry_backoff_s: float = 0.0, on_error: str | None = None,
                 timeout_s: float = 0.0) -> WorkflowBuilder:
        if name in (END,):
            raise WorkflowError(f"'{name}' is reserved")
        if name in self._nodes:
            raise WorkflowError(f"Node '{name}' already registered")
        self._nodes[name] = Node(name, fn, retries=retries,
                                 retry_backoff_s=retry_backoff_s, on_error=on_error,
                                 timeout_s=timeout_s)
        return self

    def set_entry(self, name: str) -> WorkflowBuilder:
        self._entry = name
        return self

    def add_edge(self, source: str, dest: str) -> WorkflowBuilder:
        self._edges[source] = dest
        return self

    def add_conditional_edges(self, source: str, router: Router,
                              mapping: dict[str, str] | None = None) -> WorkflowBuilder:
        self._conditionals[source] = (router, mapping)
        return self

    def to_mermaid(self) -> str:
        return _mermaid(self._nodes, self._edges, self._conditionals, self._entry or "")

    def build(self) -> CompiledWorkflow:
        if not self._nodes:
            raise WorkflowError("Workflow has no nodes")
        if self._entry is None:
            raise WorkflowError("Workflow entry node is not set")
        if self._entry not in self._nodes:
            raise WorkflowError(f"Entry node '{self._entry}' is not registered")
        self._validate_targets()
        return CompiledWorkflow(self.name, dict(self._nodes), dict(self._edges),
                                dict(self._conditionals), self._entry)

    def _validate_targets(self) -> None:
        def check(target: str) -> None:
            if target != END and target not in self._nodes:
                raise WorkflowError(f"Edge target '{target}' is not a registered node")
        for dst in self._edges.values():
            check(dst)
        for _router, mapping in self._conditionals.values():
            for target in (mapping or {}).values():
                check(target)
        for node in self._nodes.values():
            if node.on_error is not None:
                check(node.on_error)


def _mermaid(nodes, edges, conditionals, entry: str,
             result: WorkflowRunResult | None = None) -> str:
    lines = ["flowchart TD", "    START([start])", "    END([end])"]
    if entry:
        lines.append(f"    START --> {entry}")
    for name in nodes:
        lines.append(f"    {name}[{name}]")
    for src, dst in edges.items():
        target = "END" if dst == END else dst
        lines.append(f"    {src} --> {target}")
    for src, (_router, mapping) in conditionals.items():
        if mapping:
            for key, target in mapping.items():
                tgt = "END" if target == END else target
                lines.append(f"    {src} -. {key} .-> {tgt}")
        else:
            lines.append(f"    {src} -. condition .-> END")
    for node in nodes.values():
        if node.on_error:
            tgt = "END" if node.on_error == END else node.on_error
            lines.append(f"    {node.name} -. on_error .-> {tgt}")

    if result is not None:
        final: dict[str, str] = {}
        for ev in result.events:
            final[ev.node] = ev.status  # last status per node wins
        executed = [n for n, s in final.items() if s != "failed"]
        failed = [n for n, s in final.items() if s == "failed"]
        if executed:
            lines.append("    classDef executed fill:#dcfce7,stroke:#16a34a,color:#14532d;")
            lines.append(f"    class {','.join(executed)} executed;")
        if failed:
            lines.append("    classDef failed fill:#fee2e2,stroke:#dc2626,color:#7f1d1d;")
            lines.append(f"    class {','.join(failed)} failed;")
    return "\n".join(lines)
