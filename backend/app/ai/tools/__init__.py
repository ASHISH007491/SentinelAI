"""Tool framework: safe, validated, logged tool execution for agents."""
from app.ai.tools.base import BaseTool
from app.ai.tools.interfaces import (
    CveSearchTool,
    DatabaseTool,
    FilesystemTool,
    KnowledgeSearchTool,
    ThreatIntelTool,
    register_builtin_interfaces,
)
from app.ai.tools.manager import ToolManager, get_tool_manager
from app.ai.tools.models import ToolExecution, ToolMetadata, ToolResult

__all__ = [
    "BaseTool",
    "ToolManager",
    "get_tool_manager",
    "ToolResult",
    "ToolMetadata",
    "ToolExecution",
    "DatabaseTool",
    "FilesystemTool",
    "ThreatIntelTool",
    "CveSearchTool",
    "KnowledgeSearchTool",
    "register_builtin_interfaces",
]
