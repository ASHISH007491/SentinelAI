# SentinelAI Agents

Multi-agent system (LangGraph orchestrator + five MVP agents) and the single-agent
baseline, sharing one toolkit and one I/O contract.

- `orchestrator/` — LangGraph state graph, routing, tracing
- `agents/` — detection, prioritisation, phishing_detection, code_review, advisor, report
- `baseline/` — single-agent control for the evaluation
- `toolkit/` — shared parsers + knowledge-base lookups (used by both architectures)
- `contracts/` — typed AgentInput/AgentOutput schemas
