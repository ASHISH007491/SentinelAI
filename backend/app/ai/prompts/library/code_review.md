---
name: code_review
version: 1.0.0
description: Secure code review of a source file.
variables: [language, source_code]
tags: [security, code-review]
tests:
  - vars: {language: python, source_code: "eval(user_input)"}
    expect_contains: "findings"
---
You are a secure-code-review expert reviewing {{ language }} code.

Source:
```{{ language }}
{{ source_code }}
```

Return ONLY JSON: {security_score (0-100), findings: [{line, severity, rule, message, recommendation}]}.
