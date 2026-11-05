import pytest

from app.ai.core.errors import AIError, LLMError, ParsingError


def test_error_hierarchy_and_codes():
    assert issubclass(LLMError, AIError)
    with pytest.raises(AIError):
        raise ParsingError("bad")
    assert ParsingError("x").code == "ai_parsing_error"
    assert AIError("y", code="custom").code == "custom"
