"""Prompt templating, a simple registry, and the file-backed PromptManager."""
from app.ai.prompts.manager import DEFAULT_PROMPT_DIR, PromptManager
from app.ai.prompts.markdown import MarkdownPrompt, PromptMetadata, PromptTest, parse_markdown
from app.ai.prompts.registry import PromptRegistry, prompt_registry
from app.ai.prompts.renderer import referenced_variables, render_template
from app.ai.prompts.template import PromptTemplate

__all__ = [
    "PromptManager",
    "DEFAULT_PROMPT_DIR",
    "MarkdownPrompt",
    "PromptMetadata",
    "PromptTest",
    "parse_markdown",
    "render_template",
    "referenced_variables",
    "PromptTemplate",
    "PromptRegistry",
    "prompt_registry",
]
