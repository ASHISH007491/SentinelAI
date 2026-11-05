"""Type aliases used across the AI platform."""
from __future__ import annotations

from typing import Any

# A JSON-serialisable value.
JSON = dict[str, Any]
# Free-form metadata bag attached to messages, results, and state.
Metadata = dict[str, Any]
# Variables substituted into a prompt template.
PromptVariables = dict[str, Any]
