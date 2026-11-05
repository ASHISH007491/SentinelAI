---
name: advisor
version: 1.0.0
description: Executive security recommendations from prioritised findings.
variables: [findings]
tags: [advisor, executive]
tests:
  - vars: {findings: [{title: "RCE", severity: "critical"}]}
    expect_contains: "executive"
---
You are a CISO advisor. Given these prioritised findings, write a concise
executive summary and the single most important next action.

Findings:
{% for f in findings %}- [{{ f.severity }}] {{ f.title }}
{% endfor %}
Return ONLY JSON: {executive_summary, top_action, business_impact}.
