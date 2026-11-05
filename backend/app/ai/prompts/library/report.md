---
name: report
version: 1.0.0
description: Compile a structured report from a completed run.
variables: [workflow, findings, total_findings]
tags: [report]
tests:
  - vars: {workflow: vuln, findings: [], total_findings: 0}
    expect_contains: "report"
---
Compile a security report for the **{{ workflow }}** run with
{{ total_findings }} finding(s).

{% for f in findings %}- {{ f.title }}
{% endfor %}
Return ONLY JSON representing the report: {title, summary, sections: [string]}.
