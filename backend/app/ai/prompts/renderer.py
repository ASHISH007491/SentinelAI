"""Jinja2 rendering for prompts, with strict undefined-variable handling."""
from __future__ import annotations

from jinja2 import Environment, StrictUndefined, TemplateError, meta

from app.ai.core.errors import PromptError
from app.ai.types.aliases import PromptVariables

# Shared, autoescape-off environment (prompts are plain text, not HTML).
_env = Environment(
    undefined=StrictUndefined,
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)


def referenced_variables(source: str) -> set[str]:
    """Return the set of variables a Jinja2 template references."""
    try:
        ast = _env.parse(source)
    except TemplateError as exc:
        raise PromptError(f"Template parse error: {exc}") from exc
    return set(meta.find_undeclared_variables(ast))


def render_template(source: str, variables: PromptVariables) -> str:
    """Render a Jinja2 template. Missing variables raise PromptError."""
    try:
        return _env.from_string(source).render(**variables)
    except TemplateError as exc:
        raise PromptError(f"Render error: {exc}") from exc
