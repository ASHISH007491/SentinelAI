"""Robust JSON extraction from noisy LLM output."""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Protocol

from app.ai.core.errors import ParsingError


class _GenerateResponse(Protocol):
    text: str


def extract_json(text: str) -> Any:
    """Parse the first JSON object/array found in `text`.

    Tolerates surrounding prose and ```json fences. Raises ParsingError on failure.
    """
    if not text or not text.strip():
        raise ParsingError("Empty text; no JSON to parse")

    candidate = text.strip()
    if "```" in candidate:
        # Strip a fenced block if present.
        parts = candidate.split("```")
        for part in parts:
            p = part.removeprefix("json").strip()
            if p.startswith(("{", "[")):
                candidate = p
                break

    # Narrow to the outermost JSON span.
    starts = [i for i in (candidate.find("{"), candidate.find("[")) if i != -1]
    ends = [candidate.rfind("}"), candidate.rfind("]")]
    if not starts or max(ends) == -1:
        raise ParsingError("No JSON object or array found")
    span = candidate[min(starts) : max(ends) + 1]
    try:
        return json.loads(span)
    except json.JSONDecodeError as exc:
        raise ParsingError(f"Invalid JSON: {exc}") from exc


def ask_json(
    generate: Callable[..., _GenerateResponse],
    prompt: str,
    *,
    system: str | None = None,
    max_attempts: int = 2,
) -> tuple[Any | None, str]:
    """Call `generate` for a JSON reply, retrying the same prompt if parsing fails.

    Returns `(parsed, raw)`. If every attempt yields unparsable text, `parsed` is
    None and `raw` is the last raw reply, so callers can fall back to a lightweight
    heuristic (`infer_positive`) instead of failing outright.

    Every caller expects a JSON *object*. A model that returns a bare JSON array (a
    common llama-family failure mode) is therefore treated as a parse miss so the
    caller's dict-shaped fallback runs instead of crashing on ``list.get``.
    """
    raw = ""
    for _ in range(max(1, max_attempts)):
        raw = generate(prompt, system=system).text
        try:
            parsed = extract_json(raw)
        except ParsingError:
            continue
        if isinstance(parsed, dict):
            return parsed, raw
        # Parsed, but not an object (e.g. a top-level list) -> retry, then fall back.
    return None, raw


def infer_positive(raw: str, keyword: str) -> bool:
    """Best-effort textual guess when every JSON-parsing attempt has failed.

    Looks for `keyword` in the unstructured reply and checks nearby words for an
    affirmative/negative signal. Low-confidence by design — callers using this
    should report reduced confidence alongside it.
    """
    text = (raw or "").lower()
    idx = text.find(keyword.lower())
    if idx == -1:
        return False
    window = text[max(0, idx - 20) : idx + 40]
    negative = any(tok in window for tok in ("not ", "no ", "false", "isn't", "n't"))
    positive = any(tok in window for tok in ("true", "yes", "confirmed", "detected"))
    return positive and not negative
