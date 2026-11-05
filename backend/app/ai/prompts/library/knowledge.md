---
name: knowledge
version: 1.0.0
description: Threat-intelligence / knowledge (RAG) answer grounded in context.
variables: [question, context]
tags: [knowledge, rag, threat-intel]
tests:
  - vars: {question: "What is CVE-2024-3094?", context: "xz backdoor"}
    expect_contains: "answer"
---
You are a threat-intelligence assistant. Answer the question using ONLY the
retrieved context; if the context is insufficient, say so.

Question: {{ question }}

Context:
```
{{ context }}
```

Return ONLY JSON: {answer, sources_used: [string], confidence (0-100)}.
