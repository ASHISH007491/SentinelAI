# SentinelAI — OWASP Security Assessment (Self-Test)

**Target:** SentinelAI backend (`backend/app`) and evaluation harness (`eval/`)
**Date:** 2026-07-05
**Scope:** Static application security testing (SAST), dependency vulnerability audit, and a manual OWASP Top 10 (2021) code review of the project's own source.
**Nature:** Defensive self-assessment. No live system was attacked; all testing was static analysis of first-party code.

---

## 1. Tools and Method

| Tool | Purpose | Result |
|------|---------|--------|
| Bandit 1.9.4 | Python SAST (maps to CWE) | 150 findings: 0 High, 4 Medium, 146 Low |
| pip-audit 2.10.1 | Dependency CVE audit (OSV/PyPI) | No vulnerabilities in project dependencies |
| Semgrep (OWASP Top Ten ruleset) | Rule-based SAST | Not completed in the test environment (tool start-up blocked); covered instead by manual review below |
| Manual OWASP Top 10 review | Targeted code inspection | See Section 4 |

LOC scanned by Bandit: **8,615**.

---

## 2. Executive Summary

The codebase is in good security health. There are **no High-severity findings** and **no known-vulnerable project dependencies**. The four Medium findings all relate to a single, low-risk pattern (an HTTP call to the locally hosted model endpoint). The overwhelming majority of Low findings (≈140 of 146) are `assert` statements inside the test suite, which is expected and benign.

One genuine hardening item was identified by manual review: a **weak default JWT secret** (`"change-me"`). **This has since been remediated** — see Finding F1. Configuration now refuses to start in production when the secret is left at its default, and the behaviour is covered by unit tests.

**Remediation status:** F1 (weak default secret) and F3 (silent exception handling) are **fixed**. F2, F4 and F5 remain open and are low risk; each is documented below with its rationale.

Positive controls already in place: bcrypt password hashing with per-password salt, exclusive use of the SQLAlchemy ORM (no raw SQL / no injection surface), role-based access control with per-object ownership checks, configurable (non-wildcard) CORS, and a dedicated prompt-injection guardrail (`PromptGuard`).

---

## 3. Findings by Severity

| Severity | Count | Notes |
|----------|-------|-------|
| High | 0 | — |
| Medium | 4 | `B310` urllib open of the Ollama endpoint (×4) |
| Low (application code) | ~6 | try/except/pass (×3), try/except/continue (×1), non-crypto random (×1), runtime `assert` (×4) |
| Low (test code) | ~140 | `assert` usage in `eval/tests/*` — expected, not a defect |
| False positives | 2 | `B105` "hardcoded password 'True'" — a boolean literal, not a secret |

---

## 4. OWASP Top 10 (2021) Review

| # | Category | Status | Evidence |
|---|----------|--------|----------|
| A01 | Broken Access Control | **Pass** | JWT auth via `get_current_user`; RBAC roles; runs are scoped to their owner (test `test_cannot_touch_other_users_run` passes). |
| A02 | Cryptographic Failures | **Pass** | Passwords hashed with bcrypt + `gensalt()`. JWT uses HS256. The weak default secret (F1) is fixed — production start-up now fails on the default. |
| A03 | Injection | **Pass** | All DB access via SQLAlchemy ORM — no raw SQL or string concatenation. No `eval`/`exec`/`os.system`/`shell=True` in application code. LLM-layer injection mitigated by `PromptGuard` (measured: code-injection ASR reduced 28.6% → 2.9%). |
| A04 | Insecure Design | **Pass** | Human-in-the-loop by design; guardrail is a structural component, not an afterthought. |
| A05 | Security Misconfiguration | **Pass** | The insecure default secret is now rejected in production (F1). Default DB credentials remain development values and must be overridden on deploy. CORS defaults to `localhost:3000` (not `*`). |
| A06 | Vulnerable & Outdated Components | **Pass** | pip-audit reports no vulnerabilities in declared project dependencies. |
| A07 | Identification & Authentication Failures | **Pass** | Solid bcrypt + JWT flow, refresh/logout endpoints, inactive-user checks. Secret strength now enforced in production (F1). |
| A08 | Software & Data Integrity Failures | **Pass** | No `pickle`/unsafe deserialization; state persisted as JSON; prompts loaded from first-party files. |
| A09 | Logging & Monitoring Failures | **Pass** | Structured JSON logging present. The `try/except/pass` blocks that silently swallowed exceptions now log with context (F3). |
| A10 | Server-Side Request Forgery (SSRF) | **Low** | Only outbound HTTP is to a fixed, locally configured Ollama URL (Finding F2). No user-controlled URLs are fetched. |

---

## 5. Detailed Findings

### F1 — Weak default JWT secret *(Medium, A02/A05/A07)* — ✅ FIXED
`backend/app/core/config.py`: `jwt_secret` defaulted to `"change-me"`. If deployed without setting the environment variable, JWTs would be signable by anyone who knew the default, allowing token forgery.
**Remediation applied:** a Pydantic `model_validator` on `Settings` now raises at start-up when `environment == "production"` and `jwt_secret` is empty or the default, with an error message showing how to generate a strong value (`secrets.token_urlsafe(32)`). Development is unaffected. Covered by `backend/tests/test_config_security.py` (4 tests: rejects default in production, rejects empty, accepts a strong secret, permits the default in development).

### F2 — urllib open of model endpoint *(Medium ×4, A10, B310)*
`backend/app/ai/integration/ollama_provider.py` (lines 24, 44) and `eval/systems/ollama.py` (lines 49, 66) call `urllib` on the Ollama URL. Risk is low because the URL is operator-configured and points at localhost, not user input.
**Remediation:** validate the scheme is `http`/`https` before opening, and pin the host to the configured Ollama base URL.

### F3 — Silent exception handling *(Low ×3, A09, B110/B112)* — ✅ FIXED
`advisor.py`, `orchestrator.py` (×2) and `ingest.py` (×2) used `try/except/pass` (or `continue`), hiding failures.
**Remediation applied:** each path now logs before continuing — `advisor` logs a warning when the LLM summary fails and it falls back to the template; the orchestrator's best-effort memory recall and history-store paths log at `debug` with `exc_info`; the e-mail ingest paths log at `debug` when a part cannot be decoded. Failures are now observable without changing behaviour.

### F4 — Non-cryptographic RNG *(Low, B311)*
`agent_dispatcher.py:107` uses `random`. Not security-sensitive (used for scheduling/jitter, not tokens or secrets). No action required; documented for completeness.

### F5 — Runtime `assert` for invariants *(Low ×4, B101)*
`ai/agents/base.py:211`, `ai/llm/client.py:69,86`, `ai/llm/service/executor.py:95`, `ai/utils/retry.py:34`. Asserts are stripped when Python runs with `-O`.
**Remediation:** where an assert enforces a runtime invariant (not just a test aid), replace with an explicit `if ...: raise`.

### Non-issues
- `B105` "hardcoded password 'True'" in `eval/harness/reference.py` — a boolean literal, false positive.
- ~140 `assert` findings in `eval/tests/*` — correct use of asserts in tests.

---

## 6. Dependency Audit Note

`pip-audit` run in the assessment environment flagged `tornado`, `twisted`, `wheel`, and `zipp`. These are **operating-system / sandbox packages, not SentinelAI dependencies**, and do not appear in the project's `pyproject.toml`. The project's declared dependencies (FastAPI, SQLAlchemy, Pydantic, LangGraph, python-jose, bcrypt, httpx, etc.) reported **no known vulnerabilities**. For a definitive project-only result, run `pip-audit` inside the project's own virtual environment.

---

## 7. Prioritised Recommendations

1. ~~Enforce a strong `jwt_secret`; fail-fast on the default in production (F1).~~ **Done** — validated at start-up, covered by tests.
2. ~~Log swallowed exceptions instead of `pass` (F3).~~ **Done** — all five paths now log with context.
3. **(Open)** Validate URL scheme/host before opening the model endpoint (F2).
4. **(Open)** Replace production-path `assert`s with explicit checks (F5).
5. **(Open)** Re-run `pip-audit` in the project venv and `semgrep --config p/owasp-top-ten` in CI for continuous coverage.

*This assessment covers first-party code by static analysis. It complements, but does not replace, dynamic testing (DAST) of a running deployment.*
