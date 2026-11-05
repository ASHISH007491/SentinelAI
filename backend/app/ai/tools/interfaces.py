"""Interface-only stubs for the future tools.

These declare each tool's identity and validated input schema so they're
discoverable through the ToolManager (metadata), but contain NO functionality —
`_run` raises NotImplementedError. They are registered DISABLED by default. The
cybersecurity behaviour is implemented in a later phase.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.ai.tools.base import BaseTool
from app.ai.types.aliases import JSON


class _Interface(BaseTool):
    """Base for not-yet-implemented tools."""

    def _run(self, params: BaseModel) -> JSON:  # noqa: ARG002
        raise NotImplementedError(f"Tool '{self.name}' is an interface; not implemented yet")


class DatabaseTool(_Interface):
    name = "database"
    description = "Run a parameterised, read-only query against an internal datastore."
    tags = ["data"]

    class Input(BaseModel):
        query: str
        params: dict = Field(default_factory=dict)
        limit: int = 100


class FilesystemTool(_Interface):
    name = "filesystem"
    description = "Read files from a sandboxed workspace."
    tags = ["data", "files"]

    class Input(BaseModel):
        path: str
        mode: str = "read"  # read | list | stat


class ThreatIntelTool(_Interface):
    name = "threat_intel"
    description = "Look up an indicator (IP, domain, hash) in threat-intelligence feeds."
    tags = ["security", "intel"]

    class Input(BaseModel):
        indicator: str
        indicator_type: str = "auto"  # ip | domain | hash | auto


class CveSearchTool(_Interface):
    name = "cve_search"
    description = "Search CVE records by keyword, vendor, or identifier."
    tags = ["security", "vulnerability"]

    class Input(BaseModel):
        query: str
        max_results: int = 10


class KnowledgeSearchTool(_Interface):
    name = "knowledge_search"
    description = "Retrieve passages from the security knowledge base (RAG)."
    tags = ["security", "knowledge", "rag"]

    class Input(BaseModel):
        query: str
        top_k: int = 5


# All future-tool interface classes, in registration order.
BUILTIN_INTERFACES: list[type[_Interface]] = [
    DatabaseTool,
    FilesystemTool,
    ThreatIntelTool,
    CveSearchTool,
    KnowledgeSearchTool,
]


def register_builtin_interfaces(manager, *, enabled: bool = False) -> None:
    """Register the future-tool interfaces (disabled by default — not implemented)."""
    for cls in BUILTIN_INTERFACES:
        manager.register(cls(), enabled=enabled, replace=True)
