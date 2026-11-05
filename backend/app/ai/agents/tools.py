"""Tool registration for agents.

A Tool is any named callable an agent may invoke during execution. The registry
is per-agent (injected or created), supporting future expansion to many tools.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.ai.core.errors import AgentError
from app.ai.types.aliases import JSON


@runtime_checkable
class Tool(Protocol):
    name: str

    def run(self, **kwargs) -> JSON: ...


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise AgentError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise AgentError(f"Unknown tool '{name}'")
        return self._tools[name]

    def names(self) -> list[str]:
        return sorted(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
