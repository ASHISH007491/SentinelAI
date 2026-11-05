# SentinelAI — Prompt Management System (Phase 2, Prompt 014)

Every agent owns its prompt as a Markdown file (YAML frontmatter + Jinja2 body).
The `PromptManager` loads, renders, validates, tests, versions, and keeps history.
Lives at `backend/app/ai/prompts/`; prompt files in `backend/app/ai/prompts/library/`.

## Prompt file format

```markdown
---
name: vulnerability
version: 1.0.0
description: Detect and describe security vulnerabilities.
variables: [artefact_text, max_findings]
tags: [security, vulnerability]
model: null
tests:
  - vars: {artefact_text: "os.system(cmd)", max_findings: 5}
    expect_contains: "JSON"
---
You are a senior application-security analyst...
Artefact:
```
{{ artefact_text }}
```
Return up to {{ max_findings }} findings as JSON.
```

- **Frontmatter** = metadata (`PromptMetadata`): name, version, description,
  declared `variables`, tags, optional `model`, and embedded `tests`.
- **Body** = a **Jinja2** template (loops, conditionals, expressions) rendered with
  `StrictUndefined` — a missing variable is an error, not a silent blank.

## Bundled agent prompts (`library/`)

`orchestrator`, `vulnerability`, `phishing`, `code_review`, `advisor`, `report`,
`knowledge` — one per agent in the system.

## PromptManager

```python
from app.ai.prompts import PromptManager

pm = PromptManager()                              # defaults to the bundled library
pm.names()                                        # ['advisor', 'code_review', ...]
text = pm.render("vulnerability",
                 {"artefact_text": code, "max_findings": 5})
pm.metadata("vulnerability")                      # frontmatter as a dict
```

| Capability | Method |
|------------|--------|
| Loading | `load(name, *, version=None)`, `names()`, `metadata(name)` |
| Template rendering (Jinja2) | `render(name, variables, *, version=None)` |
| Validation | `validate(name)` / `validate_all()` — declared variables must cover template usage |
| Testing | `test(name)` — runs the prompt's embedded `tests` (render + `expect_contains`) |
| Versioning + history | `save(name, content)` archives the previous version; `versions(name)`; `load(name, version=...)` |

### Validation

`validate()` parses the Jinja2 body, computes the variables it actually references,
and raises `PromptValidationError` if any are **not declared** in frontmatter —
keeping metadata and template in sync.

### Versioning & history

`save()` writes a new prompt; if the version changed, the previous file is archived
to `library/.history/<name>/<old_version>.md`. `versions()` lists current + archived,
and any archived version can be loaded or rendered with `version=`.

## Tests

`backend/tests/ai/test_prompt_manager.py` — 13 tests: frontmatter parsing, round-trip
serialisation, rendering + missing-variable errors, validation (declared vs. used),
embedded test execution + failure, save/archive/version load, and a check that all 7
bundled prompts validate and pass their tests.

```
cd backend && pytest tests/ai/test_prompt_manager.py -q
```

## Notes

- Requires `jinja2` and `pyyaml` (added to backend deps; `start-all.ps1` auto-installs).
- History is file-based on disk; for multi-node deployments back it with object
  storage or a DB if you need shared history.
- Coexists with the lightweight `PromptTemplate`/`PromptRegistry` (str.format-based)
  from Prompt 011 — `PromptManager` is the file-backed, Jinja2 system.
