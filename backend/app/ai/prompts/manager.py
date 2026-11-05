"""PromptManager: file-backed prompt store with versioning, validation, testing.

Loads Markdown prompts (YAML frontmatter + Jinja2 body) from a directory, renders
them with variables, validates that declared variables match what the template
uses, runs embedded render tests, and keeps a version history when prompts change.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from app.ai.core.errors import PromptError, PromptValidationError
from app.ai.core.logging import get_logger
from app.ai.prompts.markdown import MarkdownPrompt, parse_markdown
from app.ai.prompts.renderer import referenced_variables, render_template
from app.ai.types.aliases import PromptVariables

logger = get_logger(__name__)

# Default location of the bundled agent prompts.
DEFAULT_PROMPT_DIR = Path(__file__).parent / "library"


class PromptManager:
    def __init__(self, directory: Path | str | None = None) -> None:
        self.directory = Path(directory) if directory else DEFAULT_PROMPT_DIR
        self.history_dir = self.directory / ".history"
        self._cache: dict[str, MarkdownPrompt] = {}

    # -- loading -------------------------------------------------------------
    def _path(self, name: str) -> Path:
        return self.directory / f"{name}.md"

    def load(
        self, name: str, *, version: str | None = None, use_cache: bool = True
    ) -> MarkdownPrompt:
        if version is not None:
            return self._load_version(name, version)
        if use_cache and name in self._cache:
            return self._cache[name]
        path = self._path(name)
        if not path.exists():
            raise PromptError(f"Prompt '{name}' not found at {path}")
        prompt = parse_markdown(path.read_text(encoding="utf-8"))
        self._cache[name] = prompt
        return prompt

    def names(self) -> list[str]:
        return sorted(p.stem for p in self.directory.glob("*.md"))

    def metadata(self, name: str) -> dict:
        return self.load(name).metadata.model_dump()

    # -- rendering -----------------------------------------------------------
    def render(
        self, name: str, variables: PromptVariables | None = None, *, version: str | None = None
    ) -> str:
        prompt = self.load(name, version=version)
        return render_template(prompt.body, variables or {})

    # -- validation ----------------------------------------------------------
    def validate(self, name: str) -> None:
        """Raise PromptValidationError if declared variables don't cover usage."""
        prompt = self.load(name, use_cache=False)
        used = referenced_variables(prompt.body)
        declared = set(prompt.metadata.variables)
        undeclared = used - declared
        if undeclared:
            raise PromptValidationError(
                f"Prompt '{name}' uses undeclared variables: {sorted(undeclared)}"
            )

    def validate_all(self) -> None:
        for name in self.names():
            self.validate(name)

    # -- testing -------------------------------------------------------------
    def test(self, name: str) -> int:
        """Run a prompt's embedded render tests. Returns the count; raises on failure."""
        prompt = self.load(name, use_cache=False)
        for i, case in enumerate(prompt.metadata.tests):
            output = render_template(prompt.body, case.vars)
            if case.expect_contains and case.expect_contains not in output:
                raise PromptValidationError(
                    f"Prompt '{name}' test #{i} expected to contain "
                    f"{case.expect_contains!r} but it did not"
                )
        return len(prompt.metadata.tests)

    # -- versioning / history ------------------------------------------------
    def versions(self, name: str) -> list[str]:
        """Current version first, then archived versions (newest archived order)."""
        current = self.load(name).metadata.version
        archived = sorted(p.stem for p in (self.history_dir / name).glob("*.md")) if (
            self.history_dir / name
        ).exists() else []
        return [current, *[v for v in archived if v != current]]

    def _load_version(self, name: str, version: str) -> MarkdownPrompt:
        current = self.load(name)
        if current.metadata.version == version:
            return current
        archived = self.history_dir / name / f"{version}.md"
        if not archived.exists():
            raise PromptError(f"Version '{version}' of prompt '{name}' not found")
        return parse_markdown(archived.read_text(encoding="utf-8"))

    def save(self, name: str, content: str) -> MarkdownPrompt:
        """Write a new version of a prompt, archiving the previous one to history."""
        new_prompt = parse_markdown(content)  # validates structure
        path = self._path(name)
        if path.exists():
            old = parse_markdown(path.read_text(encoding="utf-8"))
            if old.metadata.version != new_prompt.metadata.version:
                dest_dir = self.history_dir / name
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, dest_dir / f"{old.metadata.version}.md")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        self._cache[name] = new_prompt
        logger.info("saved prompt name=%s version=%s", name, new_prompt.metadata.version)
        return new_prompt
