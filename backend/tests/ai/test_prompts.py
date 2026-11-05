import pytest

from app.ai.core.errors import PromptError
from app.ai.prompts import PromptRegistry, PromptTemplate


def test_template_render_and_vars():
    tpl = PromptTemplate("Hello {name}, you have {count} alerts", name="greet")
    assert tpl.variables == {"name", "count"}
    assert tpl.render({"name": "Sam", "count": 3}) == "Hello Sam, you have 3 alerts"


def test_template_missing_variable_raises():
    tpl = PromptTemplate("Hi {name}")
    with pytest.raises(PromptError):
        tpl.render({})


def test_registry_register_get_duplicate():
    reg = PromptRegistry()
    reg.register("a", "x {y}")
    assert reg.get("a").render({"y": 1}) == "x 1"
    with pytest.raises(PromptError):
        reg.register("a", "dup")
    with pytest.raises(PromptError):
        reg.get("missing")
