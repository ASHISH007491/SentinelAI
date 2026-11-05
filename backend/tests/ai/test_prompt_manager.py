"""Unit tests for the Prompt Management System."""
import pytest

from app.ai.core.errors import PromptError, PromptValidationError
from app.ai.prompts import PromptManager, parse_markdown
from app.ai.prompts.markdown import to_markdown

PROMPT_V1 = """---
name: greet
version: 1.0.0
description: greeting
variables: [name]
tags: [demo]
tests:
  - vars: {name: Sam}
    expect_contains: Hello Sam
---
Hello {{ name }}, welcome to {{ "SentinelAI" }}.
"""

PROMPT_V2 = """---
name: greet
version: 2.0.0
description: greeting v2
variables: [name, count]
---
Hello {{ name }}, you have {{ count }} alerts.
"""

UNDECLARED = """---
name: bad
version: 1.0.0
variables: [a]
---
{{ a }} and {{ b }}
"""


@pytest.fixture()
def manager(tmp_path):
    (tmp_path / "greet.md").write_text(PROMPT_V1, encoding="utf-8")
    return PromptManager(tmp_path)


# --- parsing / metadata ---
def test_parse_markdown_frontmatter():
    p = parse_markdown(PROMPT_V1)
    assert p.metadata.name == "greet" and p.metadata.variables == ["name"]
    assert "Hello {{ name }}" in p.body


def test_missing_frontmatter_raises():
    with pytest.raises(PromptError):
        parse_markdown("no frontmatter here")


def test_roundtrip_to_markdown():
    p = parse_markdown(PROMPT_V1)
    assert parse_markdown(to_markdown(p)).metadata.name == "greet"


# --- rendering (Jinja2 + variables) ---
def test_render_with_variables(manager):
    assert manager.render("greet", {"name": "Sam"}) == "Hello Sam, welcome to SentinelAI.\n"


def test_render_missing_variable_raises(manager):
    with pytest.raises(PromptError):
        manager.render("greet", {})  # StrictUndefined


def test_load_unknown_prompt_raises(manager):
    with pytest.raises(PromptError):
        manager.load("nope")


# --- validation ---
def test_validate_passes(manager):
    manager.validate("greet")  # name is declared


def test_validate_detects_undeclared(tmp_path):
    (tmp_path / "bad.md").write_text(UNDECLARED, encoding="utf-8")
    with pytest.raises(PromptValidationError):
        PromptManager(tmp_path).validate("bad")


# --- embedded testing ---
def test_run_embedded_tests(manager):
    assert manager.test("greet") == 1


def test_embedded_test_failure(tmp_path):
    bad = PROMPT_V1.replace("Hello Sam", "Goodbye Sam")
    (tmp_path / "greet.md").write_text(bad, encoding="utf-8")
    with pytest.raises(PromptValidationError):
        PromptManager(tmp_path).test("greet")


# --- versioning + history ---
def test_save_archives_previous_version(manager):
    manager.save("greet", PROMPT_V2)
    assert manager.load("greet").metadata.version == "2.0.0"
    versions = manager.versions("greet")
    assert versions[0] == "2.0.0" and "1.0.0" in versions
    # the old version is retrievable from history
    old = manager.load("greet", version="1.0.0")
    assert old.metadata.version == "1.0.0"
    assert manager.render("greet", {"name": "X", "count": 2}, version="2.0.0").startswith("Hello X")


def test_load_unknown_version_raises(manager):
    with pytest.raises(PromptError):
        manager.load("greet", version="9.9.9")


# --- bundled library ---
def test_bundled_library_all_valid_and_tested():
    pm = PromptManager()  # default library dir
    names = pm.names()
    assert {"orchestrator", "vulnerability", "phishing", "code_review",
            "advisor", "report", "knowledge"} <= set(names)
    pm.validate_all()
    for name in names:
        pm.test(name)
