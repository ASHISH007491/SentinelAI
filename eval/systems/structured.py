"""Validate-and-retry structured output: turn free-text LLM replies into typed models.

This is the contract that separates a demo ('the LLM usually returns JSON') from an
evaluable system: parse the reply, validate it against a Pydantic schema, and on
failure re-ask the model with the validation error appended — up to ``retries`` times.
Reused by both the baseline and the multi-agent agents.
"""
from __future__ import annotations

import json
import re
from typing import TypeVar

from eval.systems.llm import LLMClient, LLMResponse
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class StructuredOutputError(ValueError):
    """Raised when the model never produced schema-valid JSON within the retry budget."""


def parse_json_block(text: str) -> dict:
    """Extract the first JSON object from an LLM reply (handles ``` fences + prose)."""
    fenced = _FENCE.search(text)
    candidate = fenced.group(1) if fenced else text
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object found in reply")
    snippet = candidate[start : end + 1]
    try:
        data = json.loads(snippet)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("top-level JSON is not an object")
    return data


class Extraction(BaseModel):
    """The validated value plus every LLM response spent obtaining it (for cost)."""

    model_config = {"arbitrary_types_allowed": True}

    value: BaseModel
    responses: list[LLMResponse]
    attempts: int


def extract(
    llm: LLMClient,
    prompt: str,
    schema: type[T],
    *,
    system: str | None = None,
    retries: int = 2,
) -> Extraction:
    """Ask the LLM for JSON matching ``schema``; re-ask on parse/validation failure."""
    responses: list[LLMResponse] = []
    current = prompt
    last_error = ""
    for attempt in range(1, retries + 2):
        resp = llm.complete(current, system=system)
        responses.append(resp)
        try:
            data = parse_json_block(resp.text)
            value = schema.model_validate(data)
            return Extraction(value=value, responses=responses, attempts=attempt)
        except (ValueError, ValidationError) as exc:
            last_error = str(exc)
            current = (
                f"{prompt}\n\nYour previous reply was not valid: {last_error}\n"
                f"Reply with ONLY a JSON object matching the required fields."
            )
    raise StructuredOutputError(
        f"no valid output after {retries + 1} attempts; last error: {last_error}"
    )


# Stems used to infer a verdict from prose when the model won't emit JSON.
_LABEL_STEMS = {"phish": ("phish", "legit"), "vulnerable": ("vulnerab", "safe")}


def infer_positive(text: str, positive_label: str) -> bool:
    """Best-effort label from free text: True if the positive stem appears first."""
    pos, neg = _LABEL_STEMS.get(positive_label, (positive_label, ""))
    t = (text or "").lower()
    pi = t.find(pos)
    ni = t.find(neg) if neg else -1
    if pi == -1:
        return False
    if ni == -1:
        return True
    return pi < ni


def extract_soft(
    llm: LLMClient,
    prompt: str,
    schema: type[T],
    *,
    system: str | None = None,
    retries: int = 2,
) -> tuple[T | None, list[LLMResponse], str]:
    """Like ``extract`` but returns (value_or_None, responses, last_text) instead of
    raising — so a single unparseable reply degrades gracefully rather than aborting a run."""
    responses: list[LLMResponse] = []
    current = prompt
    last_text = ""
    for _ in range(retries + 1):
        resp = llm.complete(current, system=system)
        responses.append(resp)
        last_text = resp.text
        try:
            data = parse_json_block(resp.text)
            return schema.model_validate(data), responses, last_text
        except (ValueError, ValidationError):
            current = (f"{prompt}\n\nIMPORTANT: reply with ONLY a single JSON object and "
                       f"no other text, for example {{\"label\": \"...\"}}.")
    return None, responses, last_text
